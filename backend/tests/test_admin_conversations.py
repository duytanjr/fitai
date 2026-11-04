"""Tests xem hội thoại ẩn danh (lát 8b-2, FR20) và quyền xoá phiên của người dùng.

Postgres thật trong transaction rollback; bảng chat_sessions được làm rỗng TRONG transaction để thống kê chỉ tính
dữ liệu mẫu của test. Không gọi Gemini hay embedding.
"""
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text

from core.config import settings
from models.admin_audit_log import AdminAuditLog
from models.chat import ChatMessage, ChatSession
from services import conversations as conv
from services.meals import today_vn
from tests.test_admin_api import PASSWORD, admin, register, user  # noqa: F401
from tests.test_meals_api import client, require_postgres  # noqa: F401

URL = "/api/v1/admin/conversations"
EMAIL = "zq.benhnhan.fake@example.com"
PHONE = "0912 345 678"
FULL_NAME = "Nguyễn Văn Zqtest"
TITLE = "Tiêu đề phiên bí mật Zq"
SRC = [{"title": "WHO guidelines on physical activity", "authors_org": "WHO", "year": 2020, "page": 12}]
REASON = "Kiểm tra chất lượng câu trả lời về protein"


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_CONVERSATION_VIEWER_ENABLED", True)
    monkeypatch.setattr(settings, "ADMIN_CONVERSATION_VIEW_DAILY_LIMIT", 30)


@pytest.fixture
async def people(client, db_session):
    """Hai người dùng thử có email, full_name; bảng chat_sessions rỗng trong transaction này."""
    await db_session.execute(text("DELETE FROM chat_sessions"))
    out = []
    for tag in ("a", "b"):
        email = f"conv8b2_{tag}_{uuid.uuid4().hex[:6]}@example.com"
        res = await client.post("/api/v1/auth/register",
                                json={"email": email, "password": PASSWORD, "full_name": f"{FULL_NAME} {tag}"})
        uid = uuid.UUID(res.json()["id"])
        login = await client.post("/api/v1/auth/login", data={"username": email, "password": PASSWORD},
                                  headers={"Content-Type": "application/x-www-form-urlencoded"})
        out.append({"id": uid, "email": email, "full_name": f"{FULL_NAME} {tag}",
                    "headers": {"Authorization": f"Bearer {login.json()['access_token']}"}})
    return out


async def seed(db, user_id, days_ago: int, messages: list[tuple], title=TITLE, same_time=False) -> ChatSession:
    created = datetime.now(timezone.utc) - timedelta(days=days_ago)
    s = ChatSession(user_id=user_id, title=title, created_at=created)
    for i, (role, content, sources) in enumerate(messages):
        s.messages.append(ChatMessage(role=role, content=content, sources=sources,
                                      created_at=created if same_time else created + timedelta(seconds=i)))
    db.add(s)
    await db.flush()
    return s


@pytest.fixture
async def sample(db_session, people):
    """3 phiên của người dùng a, 1 phiên của b; số liệu tính tay ở test_stats_match_hand_computation."""
    a, b = people[0]["id"], people[1]["id"]
    s1 = await seed(db_session, a, 0, [
        ("user", f"Tôi tên Lan, email {EMAIL}, SĐT {PHONE}. Ăn 150 g cơm, mục tiêu 2.104 kcal, nặng 78 kg?", None),
        ("assistant", "Theo WHO (2020), người lớn nên vận động 150 phút mỗi tuần.", SRC),
        ("user", "Còn protein thì sao?", None),
        ("assistant", "Tôi chưa có tài liệu đủ tin cậy về vấn đề này.", None),
    ])
    s2 = await seed(db_session, a, 1, [
        ("user", "Tôi bị tiểu đường, huyết áp cao thì ăn gì?", None),
        ("assistant", "Bạn nên gặp bác sĩ để được tư vấn.", None),
    ])
    s3 = await seed(db_session, a, 3, [
        ("user", "Chào bạn", None),
        ("assistant", "Xin chào! Tôi có thể giúp gì?", SRC),
    ])
    s4 = await seed(db_session, b, 10, [("user", "Đậu phụ có bao nhiêu protein?", None),
                                         ("assistant", "Đậu phụ: protein 10,9 g trên 100 g (VN 2007, tr. PDF 77).", SRC)])
    return [s1, s2, s3, s4]


def assert_no_identity(payload, people, sessions=()):
    dumped = json.dumps(payload, ensure_ascii=False, default=str)
    for p in people:
        for secret in (p["email"], p["full_name"], str(p["id"]), p["id"].hex):
            assert secret not in dumped, secret
    assert TITLE not in dumped and FULL_NAME not in dumped


# ── Phân quyền, bật/tắt ──────────────────────────────────────────────────────
async def test_auth_matrix(client, admin, user, enabled, sample):
    sid = sample[0].id
    calls = [("get", f"{URL}/status", {}), ("get", f"{URL}/stats", {}), ("get", URL, {}),
             ("post", f"{URL}/{sid}/view", {"json": {"reason": REASON}})]
    for method, url, kw in calls:
        assert (await getattr(client, method)(url, **kw)).status_code == 401, url
        assert (await getattr(client, method)(url, headers=user, **kw)).status_code == 403, url
        res = await getattr(client, method)(url, headers=admin, **kw)
        assert res.status_code == 200, (url, res.text)
        assert res.headers["cache-control"] == "no-store"


async def test_disabled_blocks_list_and_view_but_not_status_stats(client, admin, sample, db_session, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_CONVERSATION_VIEWER_ENABLED", False)
    st = await client.get(f"{URL}/status", headers=admin)
    assert st.status_code == 200 and st.json()["enabled"] is False
    assert (await client.get(f"{URL}/stats", headers=admin)).status_code == 200
    for res in (await client.get(URL, headers=admin),
                await client.post(f"{URL}/{sample[0].id}/view", headers=admin, json={"reason": REASON})):
        assert res.status_code == 403 and "ADMIN_CONVERSATION_VIEWER_ENABLED" in res.json()["detail"]
        assert res.headers["cache-control"] == "no-store"
    assert (await db_session.execute(select(AdminAuditLog).where(AdminAuditLog.action == "conversation.view",
                                                                 AdminAuditLog.target_id == str(sample[0].id)))).first() is None


async def test_no_store_on_error_responses(client, admin):
    for res in (await client.get(f"{URL}/status"), await client.get(f"{URL}/stats?days=14", headers=admin),
                await client.get("/api/v1/admin/foods")):
        assert res.status_code in (401, 422) and res.headers["cache-control"] == "no-store"
    assert "no-store" not in (await client.get("/health")).headers.get("cache-control", "")


# ── Bí danh, không lộ danh tính ──────────────────────────────────────────────
def test_alias_is_hmac_8_hex_stable_and_distinct():
    a, b = uuid.uuid4(), uuid.uuid4()
    expected = hmac.new(settings.SECRET_KEY.encode(), f"conv-alias:{a}".encode(), hashlib.sha256).hexdigest()[:8].upper()
    assert conv.alias(a) == f"Phiên #{expected}" == conv.alias(str(a))
    assert conv.alias(a) != conv.alias(b) and len(conv.alias(a)) == len("Phiên #") + 8


async def test_responses_never_contain_identity(client, admin, enabled, sample, people):
    payloads = [(await client.get(f"{URL}/status", headers=admin)).json()]
    for days in (7, 30, 90):
        payloads.append((await client.get(f"{URL}/stats", headers=admin, params={"days": days})).json())
    listing = (await client.get(URL, headers=admin)).json()
    payloads.append(listing)
    for item in listing["items"]:
        payloads.append((await client.post(f"{URL}/{item['session_id']}/view", headers=admin,
                                           json={"reason": REASON})).json())
    assert_no_identity(payloads, people)
    assert {i["alias"] for i in listing["items"]} == {conv.alias(s.id) for s in sample}
    for item in listing["items"]:
        assert set(item) == {"session_id", "alias", "date", "messages_count", "flags"}


# ── Danh sách, cờ, lọc ───────────────────────────────────────────────────────
async def test_list_metadata_flags_and_filters(client, admin, enabled, sample):
    body = (await client.get(URL, headers=admin)).json()
    by_id = {i["session_id"]: i for i in body["items"]}
    s1, s2, s3, s4 = (str(s.id) for s in sample)
    assert [i["session_id"] for i in body["items"]] == [s1, s2, s3, s4]          # mới nhất trước
    assert by_id[s1]["flags"] == ["khong_nguon", "noi_chua_co_du_lieu"] and by_id[s1]["messages_count"] == 4
    assert by_id[s2]["flags"] == ["khong_nguon", "chu_de_y_te"]
    assert by_id[s3]["flags"] == [] and by_id[s4]["flags"] == []                  # "Đậu phụ" ≠ từ khoá y tế
    assert by_id[s1]["date"] == today_vn().isoformat()
    only = (await client.get(URL, headers=admin, params=[("flag", "noi_chua_co_du_lieu"), ("flag", "chu_de_y_te")])).json()
    assert {i["session_id"] for i in only["items"]} == {s1, s2}
    recent = (await client.get(URL, headers=admin, params={"date_from": (today_vn() - timedelta(days=1)).isoformat()})).json()
    assert recent["total"] == 2
    page = (await client.get(URL, headers=admin, params={"page_size": 1, "page": 2})).json()
    assert page["total"] == 4 and [i["session_id"] for i in page["items"]] == [s2]
    for params in ({"page_size": 21}, {"flag": "khac"}, {"date_from": (today_vn() - timedelta(days=90)).isoformat()},
                   {"date_from": "2026-11-05", "date_to": "2026-11-01"}, {"user_id": "x"}):
        res = await client.get(URL, headers=admin, params=params)
        assert res.status_code == (200 if "user_id" in params else 422), params
    params = (await client.get("/api/v1/openapi.json")).json()["paths"][URL]["get"]["parameters"]
    assert {p["name"] for p in params} == {"flag", "date_from", "date_to", "page", "page_size"}   # không tìm nội dung / user


@pytest.mark.parametrize("content,role,flags", [
    ("Tôi bị đau ngực và khó thở khi tập", "user", {"chu_de_y_te"}),
    ("Hay bị chóng mặt, có lúc ngất", "user", {"chu_de_y_te"}),
    ("toi bi di ung hai san", "user", {"chu_de_y_te"}),
    ("Thuộc nhóm thực phẩm nào? Đầu tuần ăn đậu", "user", set()),
    ("Tôi bị viêm họng", "user", set()),              # "viem" đã bỏ khỏi danh sách
    ("Bảng thực phẩm tạm thời không truy cập được.", "assistant", {"noi_chua_co_du_lieu", "khong_nguon"}),
    ("Mục này KHÔNG CÓ SỐ LIỆU xơ.", "assistant", {"noi_chua_co_du_lieu", "khong_nguon"}),
])
def test_message_flags(content, role, flags):
    assert conv.message_flags(role, content, None) == flags


# ── Xem nội dung ─────────────────────────────────────────────────────────────
async def test_view_redacts_and_orders(client, admin, enabled, sample, db_session):
    res = await client.post(f"{URL}/{sample[0].id}/view", headers=admin, json={"reason": REASON})
    body = res.json()
    assert res.status_code == 200 and body["alias"] == conv.alias(sample[0].id) and body["messages_count"] == 4
    first = body["messages"][0]
    assert first["index"] == 1 and first["role"] == "user"
    assert "[email]" in first["content"] and "[điện thoại]" in first["content"]
    assert EMAIL not in json.dumps(body) and "345 678" not in json.dumps(body)
    assert "150 g" in first["content"] and "2.104 kcal" in first["content"] and "78 kg" in first["content"]
    assert body["messages"][1]["sources"] == ["WHO guidelines on physical activity"]
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user", "assistant"]
    assert body["remaining_today"] == 29 and "created_at" not in json.dumps(body)


async def test_same_timestamp_user_before_assistant(client, admin, enabled, people, db_session):
    s = await seed(db_session, people[0]["id"], 0, [("assistant", "Trả lời", SRC), ("user", "Câu hỏi", None)],
                   same_time=True)
    body = (await client.post(f"{URL}/{s.id}/view", headers=admin, json={"reason": REASON})).json()
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]


async def test_long_message_truncated(client, admin, enabled, people, db_session):
    s = await seed(db_session, people[0]["id"], 0, [("user", "x" * 5000, None)])
    body = (await client.post(f"{URL}/{s.id}/view", headers=admin, json={"reason": REASON})).json()
    assert len(body["messages"][0]["content"]) == 2000


@pytest.mark.parametrize("reason", ["ngắn quá", " " * 20, "a" * 201, "\x00\x01" + "b" * 8, None, 123])
async def test_reason_length_422(client, admin, enabled, sample, reason):
    res = await client.post(f"{URL}/{sample[0].id}/view", headers=admin, json={"reason": reason})
    assert res.status_code == 422


async def test_unknown_session_404_without_audit(client, admin, enabled, sample, db_session):
    sid = uuid.uuid4()
    assert (await client.post(f"{URL}/{sid}/view", headers=admin, json={"reason": REASON})).status_code == 404
    assert (await db_session.execute(select(AdminAuditLog).where(AdminAuditLog.target_id == str(sid)))).first() is None


async def test_daily_limit_429(client, admin, enabled, sample, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_CONVERSATION_VIEW_DAILY_LIMIT", 2)
    for expected_remaining in (1, 0):
        res = await client.post(f"{URL}/{sample[0].id}/view", headers=admin, json={"reason": REASON})
        assert res.status_code == 200 and res.json()["remaining_today"] == expected_remaining
    res = await client.post(f"{URL}/{sample[1].id}/view", headers=admin, json={"reason": REASON})
    assert res.status_code == 429 and res.headers["cache-control"] == "no-store"
    st = (await client.get(f"{URL}/status", headers=admin)).json()
    assert (st["daily_limit"], st["remaining_today"]) == (2, 0)


async def test_audit_written_without_content(client, admin, enabled, sample, db_session, people):
    reason = f"Kiểm tra lỗi, liên hệ tôi qua {EMAIL} hoặc {PHONE}"
    await client.post(f"{URL}/{sample[0].id}/view", headers=admin, json={"reason": reason})
    [log] = (await db_session.execute(select(AdminAuditLog).where(
        AdminAuditLog.action == "conversation.view", AdminAuditLog.target_id == str(sample[0].id)))).scalars().all()
    assert log.target_type == "chat_session" and log.admin_user_id is not None
    assert set(log.details) == {"alias", "messages_count", "reason"}
    assert log.details["alias"] == conv.alias(sample[0].id) and log.details["messages_count"] == 4
    assert log.details["reason"] == "Kiểm tra lỗi, liên hệ tôi qua [email] hoặc [điện thoại]"
    dumped = json.dumps(log.details, ensure_ascii=False)
    for secret in (EMAIL, "345 678", "150 g", "WHO", "tiểu đường", str(people[0]["id"]), people[0]["email"]):
        assert secret not in dumped


async def test_logs_never_contain_content_or_reason(client, admin, enabled, sample, caplog):
    reason = "Lý do xem riêng tư Zq-reason-123"
    caplog.set_level(logging.DEBUG)
    for name in ("", "uvicorn", "uvicorn.access", "sqlalchemy.engine", "services", "api"):
        logging.getLogger(name).setLevel(logging.DEBUG)
    try:
        await client.get(URL, headers=admin)
        await client.post(f"{URL}/{sample[0].id}/view", headers=admin, json={"reason": reason})
        await client.post(f"{URL}/{sample[1].id}/view", headers=admin, json={"reason": "x"})       # 422
        await client.get(f"{URL}/stats", headers=admin)
    finally:
        for name in ("uvicorn", "uvicorn.access", "sqlalchemy.engine", "services", "api"):
            logging.getLogger(name).setLevel(logging.NOTSET)
    logged = caplog.text + " ".join(str(r.args) for r in caplog.records)
    for secret in (reason, "Zq-reason", EMAIL, "tiểu đường", "Còn protein thì sao", TITLE):
        assert secret not in logged


# ── Thống kê ─────────────────────────────────────────────────────────────────
async def test_stats_match_hand_computation(client, admin, sample):
    """Tính tay: 7 ngày gần nhất có s1 (hôm nay, 4 tin), s2 (hôm qua, 2 tin), s3 (3 ngày trước, 2 tin); s4 ở ngày -10.
    Phiên: 3; tin nhắn: 8; người dùng khác nhau: 1; tin trợ lý: 4, có nguồn: 2 → 50,0%; TB 8/3 = 2,7.
    Cờ: khong_nguon 2 (s1, s2), noi_chua_co_du_lieu 1 (s1), chu_de_y_te 1 (s2)."""
    body = (await client.get(f"{URL}/stats", headers=admin, params={"days": 7})).json()
    assert (body["sessions"], body["messages"], body["distinct_users"]) == (3, 8, 1)
    assert (body["assistant_messages"], body["assistant_with_sources_pct"], body["avg_messages_per_session"]) == (4, 50.0, 2.7)
    assert {f["code"]: f["sessions"] for f in body["flags"]} == {"khong_nguon": 2, "noi_chua_co_du_lieu": 1, "chu_de_y_te": 1}
    assert "ồn" in next(f["description"] for f in body["flags"] if f["code"] == "khong_nguon")
    series = {p["date"]: (p["sessions"], p["messages"]) for p in body["series"]}
    today = today_vn()
    assert len(series) == 7 and series[today.isoformat()] == (1, 4)
    assert series[(today - timedelta(days=1)).isoformat()] == (1, 2)
    assert series[(today - timedelta(days=3)).isoformat()] == (1, 2)
    assert sum(v[0] for v in series.values()) == 3
    body30 = (await client.get(f"{URL}/stats", headers=admin, params={"days": 30})).json()
    assert (body30["sessions"], body30["messages"], body30["distinct_users"]) == (4, 10, 2)
    assert body30["assistant_with_sources_pct"] == 60.0 and body30["avg_messages_per_session"] == 2.5
    for days in (0, 14, 365, "x"):
        assert (await client.get(f"{URL}/stats", headers=admin, params={"days": days})).status_code == 422


async def test_stats_empty(client, admin, people):
    body = (await client.get(f"{URL}/stats", headers=admin)).json()
    assert body["sessions"] == 0 and body["assistant_with_sources_pct"] is None and body["avg_messages_per_session"] is None


# ── Người dùng xoá phiên của mình ────────────────────────────────────────────
async def test_user_deletes_own_session_only(client, people, sample, db_session):
    a, b = people
    s1 = sample[0]
    assert (await client.delete(f"/api/v1/chat/sessions/{s1.id}")).status_code == 401
    assert (await client.delete(f"/api/v1/chat/sessions/{s1.id}", headers=b["headers"])).status_code == 404
    assert (await client.delete(f"/api/v1/chat/sessions/{uuid.uuid4()}", headers=a["headers"])).status_code == 404
    assert (await client.delete(f"/api/v1/chat/sessions/{s1.id}", headers=a["headers"])).status_code == 204
    count = (await db_session.execute(text("SELECT count(*) FROM chat_messages WHERE session_id = :s"),
                                      {"s": s1.id})).scalar_one()
    assert count == 0
    assert (await client.get(f"/api/v1/chat/sessions/{s1.id}/messages", headers=a["headers"])).status_code == 404
    sessions = (await client.get("/api/v1/chat/sessions", headers=a["headers"])).json()
    assert str(s1.id) not in {s["id"] for s in sessions} and len(sessions) == 2
