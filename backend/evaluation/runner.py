"""Chạy câu hỏi đánh giá, ghi kết quả CSV (utf-8-sig) sau MỖI câu (dừng giữa chừng không mất).

- Giãn nhịp `delay` giây giữa các lượt gọi chatbot.
- Lỗi hạn mức (ResourceExhausted / HTTP 429) → chờ `quota_wait` rồi thử lại tối đa `retries` lần;
  hết lượt thì ghi trang_thai="loi_han_muc" (không coi là câu trả lời sai, không chấm).
- Chạy tiếp: đọc file kết quả cũ, bỏ qua các id đã "ok", chạy lại các id lỗi.
- Console chỉ in id / trạng thái / thời gian (chế độ retrieval in thêm top-k đoạn tài liệu);
  KHÔNG in câu trả lời.
"""
from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from evaluation.checks import References, auto_check
from evaluation.questions import Question

RESULT_COLUMNS = ["id", "nhom", "tai_khoan", "trang_thai", "thoi_gian_s", "so_lan_thu", "cau_tra_loi", "nguon",
                  "cong_cu_da_goi", "loai_loi", "auto_check", "auto_ghi_chu", "retrieval_topk"]
STATUS_OK, STATUS_QUOTA, STATUS_OTHER = "ok", "loi_han_muc", "loi_khac"
QUOTA_ERRORS = {"ResourceExhausted", "TooManyRequests", "RateLimitError"}
DEFAULT_CHAT_DELAY = 45.0
DEFAULT_RETRIEVAL_DELAY = 1.0


@dataclass
class ChatOutcome:
    http_status: int
    reply: str = ""
    sources: list[dict] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)       # [{"name": ..., "args": [tên tham số]}]
    error_type: str | None = None                         # loại lỗi gốc (chỉ tên), vd. ResourceExhausted


ChatFn = Callable[[Question], Awaitable[ChatOutcome]]
RetrieveFn = Callable[[str], Awaitable[list[dict]]]
SleepFn = Callable[[float], Awaitable[None]]


def is_quota_error(outcome: ChatOutcome) -> bool:
    return outcome.http_status == 429 or (outcome.http_status >= 500 and outcome.error_type in QUOTA_ERRORS)


class ResultStore:
    """File kết quả; ghi lại toàn bộ (tmp + replace) sau mỗi dòng, giữ thứ tự câu hỏi."""

    def __init__(self, path: Path, order: list[str]) -> None:
        self.path = path
        self.order = order
        self.rows: dict[str, dict] = {}
        if path.exists():
            with open(path, encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    if row.get("id"):
                        self.rows[row["id"]] = row

    @property
    def done(self) -> set[str]:
        return {i for i, r in self.rows.items() if r.get("trang_thai") == STATUS_OK}

    def save(self, row: dict) -> None:
        self.rows[row["id"]] = row
        rank = {qid: i for i, qid in enumerate(self.order)}
        ordered = sorted(self.rows.values(), key=lambda r: rank.get(r["id"], len(rank)))
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=RESULT_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(ordered)
        os.replace(tmp, self.path)


def _base_row(q: Question) -> dict:
    return {"id": q.id, "nhom": q.nhom, "tai_khoan": q.account}


async def ask(q: Question, chat: ChatFn, retries: int, quota_wait: float, sleep: SleepFn,
              clock: Callable[[], float] = time.monotonic) -> tuple[dict, ChatOutcome]:
    attempts = 0
    while True:
        attempts += 1
        start = clock()
        outcome = await chat(q)
        elapsed = clock() - start
        if outcome.http_status == 200:
            status = STATUS_OK
        elif is_quota_error(outcome):
            if attempts <= retries:
                await sleep(quota_wait)
                continue
            status = STATUS_QUOTA
        else:
            status = STATUS_OTHER
        row = {
            **_base_row(q), "trang_thai": status, "thoi_gian_s": f"{elapsed:.1f}", "so_lan_thu": attempts,
            "cau_tra_loi": outcome.reply if status == STATUS_OK else "",
            "nguon": json.dumps(outcome.sources, ensure_ascii=False),
            "cong_cu_da_goi": json.dumps(outcome.calls, ensure_ascii=False),
            "loai_loi": outcome.error_type or ("" if status == STATUS_OK else f"HTTP {outcome.http_status}"),
        }
        return row, outcome


async def run_chat(questions: list[Question], chat: ChatFn, refs: References, store: ResultStore, *,
                   delay: float = DEFAULT_CHAT_DELAY, retries: int = 3, quota_wait: float = 90.0,
                   sleep: SleepFn, log: Callable[[str], None] = print) -> None:
    first = True
    for q in questions:
        if q.id in store.done:
            log(f"{q.id}: đã có kết quả ok — bỏ qua")
            continue
        if not first:
            await sleep(delay)
        first = False
        row, outcome = await ask(q, chat, retries, quota_wait, sleep)
        if row["trang_thai"] == STATUS_OK:
            row["auto_check"], row["auto_ghi_chu"] = auto_check(q, outcome.reply, outcome.sources, outcome.calls, refs)
        else:
            row["auto_check"], row["auto_ghi_chu"] = "", f"không kiểm tra: {row['trang_thai']}"
        store.save(row)
        log(f"{q.id}: {row['trang_thai']} | {row['thoi_gian_s']} s | {row['so_lan_thu']} lần | "
            f"công cụ {[c['name'] for c in outcome.calls]} | auto_check={row['auto_check']}")


async def run_retrieval(questions: list[Question], retrieve: RetrieveFn, store: ResultStore, *, threshold: float,
                        delay: float = DEFAULT_RETRIEVAL_DELAY, sleep: SleepFn,
                        log: Callable[[str], None] = print) -> None:
    """Chỉ truy xuất (không gọi LLM): ghi top-k đoạn kèm điểm, trang, có qua ngưỡng không."""
    first = True
    for q in questions:
        if q.id in store.done:
            log(f"{q.id}: đã có kết quả ok — bỏ qua")
            continue
        if not first:
            await sleep(delay)
        first = False
        row = {**_base_row(q), "so_lan_thu": 1, "auto_check": "can_cham_tay", "auto_ghi_chu": "retrieval-only"}
        try:
            hits = await retrieve(q.cau_hoi)
        except Exception as exc:  # noqa: BLE001 — ghi loại lỗi, không dừng cả lượt
            cause = type(exc.__cause__).__name__ if exc.__cause__ else type(exc).__name__
            store.save({**row, "trang_thai": STATUS_QUOTA if cause in QUOTA_ERRORS else STATUS_OTHER, "loai_loi": cause})
            log(f"{q.id}: lỗi truy xuất ({cause})")
            continue
        top = [{"hang": i, "diem": h.get("score"), "qua_nguong": (h.get("score") or 0) >= threshold,
                "trang_pdf": h.get("page"), "tai_lieu": h.get("file") or h.get("title"),
                "trich": " ".join((h.get("text") or "").split())[:160]} for i, h in enumerate(hits, 1)]
        store.save({**row, "trang_thai": STATUS_OK, "retrieval_topk": json.dumps(top, ensure_ascii=False)})
        log(f"{q.id}: {q.cau_hoi}")
        for t in top:
            mark = "✓" if t["qua_nguong"] else "·"
            log(f"   {mark} #{t['hang']} điểm {t['diem']:.3f} | {t['tai_lieu']} tr. PDF {t['trang_pdf']} | {t['trich'][:90]}")
