"""Xem hội thoại ẩn danh cho quản trị viên (FR20) — phần NHẠY CẢM về quyền riêng tư.

- Bí danh phiên: HMAC-SHA256(SECRET_KEY, "conv-alias:" + session_id), 8 ký tự hex → "Phiên #A3F91C0B". Không đảo
  ngược được, không lưu. KHÔNG bao giờ trả email, tên, user_id hay title của phiên.
- Chỉ hiện NGÀY tạo phiên (giờ Việt Nam), số tin nhắn và thứ tự tin nhắn — không giờ phút giây.
- Nội dung chỉ trả qua view(): đã che bằng services/redaction.py; mỗi lần xem ghi audit (bí danh, số tin nhắn,
  lý do ĐÃ CHE) và bị giới hạn số lần mỗi ngày (đếm từ audit, khoá advisory theo admin).
- Cờ là HEURISTIC do code gắn từ dữ liệu đã lưu (không phải đánh giá chất lượng):
  khong_nguon (ồn: nhiều phiên bình thường cũng có), noi_chua_co_du_lieu, chu_de_y_te.
- Không ghi nội dung tin nhắn hay lý do xem vào log.
"""
from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.config import settings
from models.admin_audit_log import AdminAuditLog
from models.chat import ChatMessage, ChatSession
from services.foods.normalize import normalize_search
from services.meals import VN_OFFSET, today_vn
from services.redaction import redact

ALIAS_PREFIX = "Phiên #"
ALIAS_HEX = 8
STATS_DAYS = (7, 30, 90)
DEFAULT_LIST_DAYS = 30
MAX_LIST_DAYS = 90
MAX_PAGE_SIZE = 20
REASON_MIN, REASON_MAX = 10, 200
ACTION_VIEW = "conversation.view"
TARGET = "chat_session"

FLAG_NO_SOURCE = "khong_nguon"
FLAG_NO_DATA = "noi_chua_co_du_lieu"
FLAG_MEDICAL = "chu_de_y_te"
FLAGS = (FLAG_NO_SOURCE, FLAG_NO_DATA, FLAG_MEDICAL)
FLAG_LABELS = {
    FLAG_NO_SOURCE: "Không có nguồn (nhiều phiên bình thường cũng có)",
    FLAG_NO_DATA: "Trợ lý nói chưa có dữ liệu",
    FLAG_MEDICAL: "Chủ đề y tế",
}
FLAG_DESCRIPTIONS = {
    FLAG_NO_SOURCE: "Heuristic, ồn: có ít nhất một tin nhắn trợ lý không kèm nguồn (câu chào, câu tính chỉ số "
                    "hay hỏi lại cũng không có nguồn).",
    FLAG_NO_DATA: "Heuristic: tin nhắn trợ lý chứa một trong các cụm như \"chưa có tài liệu đủ tin cậy\", "
                  "\"không có số liệu\", \"chưa có thông tin\"…",
    FLAG_MEDICAL: "Heuristic: tin nhắn người dùng chứa từ khoá y tế (bệnh, bác sĩ, huyết áp…), so khớp không dấu "
                  "theo nguyên từ.",
}

# So khớp sau normalize_search (không dấu, viết thường, chỉ chữ/số) và theo NGUYÊN TỪ
NO_DATA_PHRASES = (
    "chua co tai lieu du tin cay", "khong co so lieu", "chua co so lieu", "chua co thong tin",
    "chua co du lieu", "khong co du lieu", "chua du du lieu", "khong tim thay", "khong co muc nao",
    "tam thoi khong kha dung", "tam thoi khong truy cap duoc", "chua ho tro",
)
# Tránh từ đơn trùng khi bỏ dấu (thuoc ~ thuộc, dau ~ đậu/đầu, da day ~ da dày)
MEDICAL_KEYWORDS = (
    "benh", "bac si", "benh vien", "trieu chung", "chan doan", "don thuoc", "uong thuoc", "khang sinh",
    "tieu duong", "huyet ap", "tim mach", "ung thu", "mang thai", "cho con bu", "suy than", "gan nhiem mo",
    "chan thuong", "tram cam", "roi loan an uong", "mo mau", "dau nguc", "kho tho", "chong mat", "ngat", "di ung",
)


class ConversationNotFoundError(LookupError):
    pass


class ViewLimitError(Exception):
    pass


# ── Hàm thuần ────────────────────────────────────────────────────────────────
def alias(session_id: uuid.UUID | str) -> str:
    digest = hmac.new(settings.SECRET_KEY.encode("utf-8"), f"conv-alias:{session_id}".encode("utf-8"),
                      hashlib.sha256).hexdigest()
    return ALIAS_PREFIX + digest[:ALIAS_HEX].upper()


def vn_date(moment: datetime) -> date:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (moment.astimezone(timezone.utc) + VN_OFFSET).date()


def vn_day_start(day: date) -> datetime:
    """Thời điểm UTC của 00:00 giờ Việt Nam ngày `day`."""
    return datetime.combine(day, time.min, tzinfo=timezone.utc) - VN_OFFSET


def _has_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    padded = f" {normalize_search(text or '')} "
    return any(f" {p} " in padded for p in phrases)


def message_flags(role: str, content: str, sources) -> set[str]:
    flags = set()
    if role == "assistant":
        if not sources:
            flags.add(FLAG_NO_SOURCE)
        if _has_phrase(content, NO_DATA_PHRASES):
            flags.add(FLAG_NO_DATA)
    elif role == "user" and _has_phrase(content, MEDICAL_KEYWORDS):
        flags.add(FLAG_MEDICAL)
    return flags


def ordered(messages: list[ChatMessage]) -> list[ChatMessage]:
    """Tin nhắn người dùng và trợ lý lưu cùng transaction có cùng created_at: người dùng trước, trợ lý sau."""
    return sorted(messages, key=lambda m: (m.created_at, 0 if m.role == "user" else 1))


@dataclass
class SessionSummary:
    id: uuid.UUID
    alias: str
    day: date
    messages_count: int
    flags: list[str]
    user_id: uuid.UUID          # chỉ dùng để ĐẾM người dùng khác nhau; không bao giờ trả ra
    assistant_total: int = 0
    assistant_with_sources: int = 0
    message_days: list[date] = field(default_factory=list)


def summarize(session: ChatSession) -> SessionSummary:
    flags: set[str] = set()
    msgs = session.messages
    for m in msgs:
        flags |= message_flags(m.role, m.content, m.sources)
    assistant = [m for m in msgs if m.role == "assistant"]
    return SessionSummary(
        id=session.id, alias=alias(session.id), day=vn_date(session.created_at), messages_count=len(msgs),
        flags=[f for f in FLAGS if f in flags], user_id=session.user_id, assistant_total=len(assistant),
        assistant_with_sources=sum(1 for m in assistant if m.sources), message_days=[vn_date(m.created_at) for m in msgs],
    )


# ── Truy vấn ────────────────────────────────────────────────────────────────
async def sessions_between(db: AsyncSession, start: date, end: date) -> list[SessionSummary]:
    """Phiên tạo trong [start, end] (ngày giờ VN), mới nhất trước; cờ tính trong Python, nội dung không trả ra."""
    stmt = (select(ChatSession).options(selectinload(ChatSession.messages))
            .where(ChatSession.created_at >= vn_day_start(start), ChatSession.created_at < vn_day_start(end + timedelta(days=1)))
            .order_by(ChatSession.created_at.desc(), ChatSession.id))
    return [summarize(s) for s in (await db.execute(stmt)).scalars().all()]


def build_stats(sessions: list[SessionSummary], start: date, end: date) -> dict:
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    per_day = {d: {"date": d, "sessions": 0, "messages": 0} for d in days}
    for s in sessions:
        per_day[s.day]["sessions"] += 1
        for d in s.message_days:
            if d in per_day:
                per_day[d]["messages"] += 1
    total_messages = sum(s.messages_count for s in sessions)
    assistant = sum(s.assistant_total for s in sessions)
    with_sources = sum(s.assistant_with_sources for s in sessions)
    return {
        "start": start, "end": end, "series": list(per_day.values()),
        "sessions": len(sessions), "messages": total_messages,
        "distinct_users": len({s.user_id for s in sessions}),
        "assistant_messages": assistant,
        "assistant_with_sources_pct": round(100 * with_sources / assistant, 1) if assistant else None,
        "avg_messages_per_session": round(total_messages / len(sessions), 1) if sessions else None,
        "flags": [{"code": f, "label": FLAG_LABELS[f], "description": FLAG_DESCRIPTIONS[f],
                   "sessions": sum(1 for s in sessions if f in s.flags)} for f in FLAGS],
    }


async def stats(db: AsyncSession, days: int) -> dict:
    end = today_vn()
    start = end - timedelta(days=days - 1)
    return {"days": days, **build_stats(await sessions_between(db, start, end), start, end)}


async def views_today(db: AsyncSession, admin_id: uuid.UUID) -> int:
    return (await db.execute(select(func.count()).select_from(AdminAuditLog).where(
        AdminAuditLog.action == ACTION_VIEW, AdminAuditLog.admin_user_id == admin_id,
        AdminAuditLog.created_at >= vn_day_start(today_vn())))).scalar_one()


async def view(db: AsyncSession, admin_id: uuid.UUID, session_id: uuid.UUID, reason: str) -> dict:
    """Nội dung đã che của một phiên + ghi audit. Không commit. Vượt giới hạn → ViewLimitError."""
    # Khoá theo admin trong transaction: hai yêu cầu đồng thời không vượt giới hạn
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"conv-view:{admin_id}"})
    if await views_today(db, admin_id) >= settings.ADMIN_CONVERSATION_VIEW_DAILY_LIMIT:
        raise ViewLimitError()
    session = (await db.execute(select(ChatSession).options(selectinload(ChatSession.messages))
                                .where(ChatSession.id == session_id))).scalar_one_or_none()
    if session is None:
        raise ConversationNotFoundError()
    summary = summarize(session)
    messages = [{
        "index": i, "role": m.role if m.role in ("user", "assistant") else "assistant",
        "content": redact(m.content),
        "sources": [str(s.get("title", ""))[:200] for s in (m.sources or []) if isinstance(s, dict)],
    } for i, m in enumerate(ordered(session.messages), 1)]
    db.add(AdminAuditLog(admin_user_id=admin_id, action=ACTION_VIEW, target_type=TARGET, target_id=str(session_id),
                         details={"alias": summary.alias, "messages_count": summary.messages_count,
                                  "reason": redact(reason, REASON_MAX)}))
    await db.flush()
    return {"session_id": session.id, "alias": summary.alias, "date": summary.day,
            "messages_count": summary.messages_count, "flags": summary.flags, "messages": messages}
