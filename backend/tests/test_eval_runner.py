"""Tests runner đánh giá: lỗi hạn mức, chạy tiếp, ghi CSV utf-8-sig — Gemini mock hoàn toàn."""
import csv
import json

from evaluation.checks import References
from evaluation.questions import Question
from evaluation.runner import (
    RESULT_COLUMNS,
    STATUS_OK,
    STATUS_OTHER,
    STATUS_QUOTA,
    ChatOutcome,
    ResultStore,
    run_chat,
    run_retrieval,
)


def question(qid, tools="Không"):
    return Question(id=qid, nhom=f"{qid[0]}. Nhóm", cau_hoi=f"câu {qid}?", chuan_bi="Bất kỳ tài khoản nào",
                    columns={"hanh_vi_mong_doi": "x", "cong_cu_mong_doi": tools})


class FakeChat:
    def __init__(self, script):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls = []

    async def __call__(self, q):
        self.calls.append(q.id)
        return self.script[q.id].pop(0)


class FakeSleep:
    def __init__(self):
        self.waits = []

    async def __call__(self, seconds):
        self.waits.append(seconds)


OK = ChatOutcome(200, reply="Mình chỉ hỗ trợ thể dục và dinh dưỡng.")
QUOTA = ChatOutcome(503, error_type="ResourceExhausted")


def read(path):
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")                              # utf-8-sig
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == RESULT_COLUMNS
        return {r["id"]: r for r in reader}


async def test_quota_error_is_retried_then_succeeds(tmp_path):
    chat, sleep = FakeChat({"D01": [QUOTA, QUOTA, OK]}), FakeSleep()
    store = ResultStore(tmp_path / "r.csv", ["D01"])
    await run_chat([question("D01")], chat, References(), store, delay=45, retries=3, quota_wait=90,
                   sleep=sleep, log=lambda _: None)
    row = read(tmp_path / "r.csv")["D01"]
    assert (row["trang_thai"], row["so_lan_thu"], row["auto_check"]) == (STATUS_OK, "3", "dat")
    assert sleep.waits == [90, 90]                                         # chỉ chờ hạn mức, không delay trước câu đầu


async def test_quota_exhausted_is_recorded_not_graded(tmp_path):
    chat, sleep = FakeChat({"D01": [QUOTA] * 4, "D02": [OK]}), FakeSleep()
    store = ResultStore(tmp_path / "r.csv", ["D01", "D02"])
    await run_chat([question("D01"), question("D02")], chat, References(), store, delay=45, retries=3,
                   quota_wait=60, sleep=sleep, log=lambda _: None)
    rows = read(tmp_path / "r.csv")
    assert rows["D01"]["trang_thai"] == STATUS_QUOTA and rows["D01"]["so_lan_thu"] == "4"
    assert rows["D01"]["auto_check"] == "" and rows["D01"]["cau_tra_loi"] == ""
    assert rows["D01"]["loai_loi"] == "ResourceExhausted"
    assert rows["D02"]["trang_thai"] == STATUS_OK
    assert sleep.waits == [60, 60, 60, 45]                                 # 3 lần chờ hạn mức, rồi giãn nhịp


async def test_other_errors_are_not_retried(tmp_path):
    chat, sleep = FakeChat({"D01": [ChatOutcome(503, error_type="ConnectError")]}), FakeSleep()
    store = ResultStore(tmp_path / "r.csv", ["D01"])
    await run_chat([question("D01")], chat, References(), store, retries=3, quota_wait=60, sleep=sleep,
                   log=lambda _: None)
    row = read(tmp_path / "r.csv")["D01"]
    assert (row["trang_thai"], row["so_lan_thu"], row["loai_loi"]) == (STATUS_OTHER, "1", "ConnectError")
    assert sleep.waits == []


async def test_resume_skips_ok_rows_and_reruns_failed(tmp_path):
    path = tmp_path / "r.csv"
    order = ["D01", "D02", "D03"]
    first = FakeChat({"D01": [OK], "D02": [QUOTA, QUOTA], "D03": [OK]})
    await run_chat([question(i) for i in order], first, References(), ResultStore(path, order), retries=1,
                   quota_wait=1, sleep=FakeSleep(), log=lambda _: None)
    assert read(path)["D02"]["trang_thai"] == STATUS_QUOTA

    second = FakeChat({"D02": [OK]})
    logs = []
    await run_chat([question(i) for i in order], second, References(), ResultStore(path, order), retries=1,
                   quota_wait=1, sleep=FakeSleep(), log=logs.append)
    assert second.calls == ["D02"]                                         # D01, D03 đã ok → không chạy lại
    rows = read(path)
    assert list(rows) == order and all(r["trang_thai"] == STATUS_OK for r in rows.values())
    assert any("D01: đã có kết quả ok" in line for line in logs)


async def test_results_record_tools_sources_and_no_reply_in_console(tmp_path):
    outcome = ChatOutcome(200, reply="BÍ MẬT câu trả lời", sources=[{"title": "t", "page": 3}],
                          calls=[{"name": "search_knowledge", "args": ["query"]}])
    logs = []
    store = ResultStore(tmp_path / "r.csv", ["A01"])
    await run_chat([question("A01", "search_knowledge")], FakeChat({"A01": [outcome]}), References(), store,
                   sleep=FakeSleep(), log=logs.append)
    row = read(tmp_path / "r.csv")["A01"]
    assert row["cau_tra_loi"] == "BÍ MẬT câu trả lời"
    assert json.loads(row["nguon"]) == [{"title": "t", "page": 3}]
    assert json.loads(row["cong_cu_da_goi"]) == [{"name": "search_knowledge", "args": ["query"]}]
    assert row["auto_check"] == "dat"
    assert not any("BÍ MẬT" in line for line in logs)


async def test_retrieval_only_records_top_k_with_threshold(tmp_path):
    async def retrieve(text):
        return [{"score": 0.71, "page": 12, "file": "who.pdf", "text": "Adults should do at least 150–300 minutes"},
                {"score": 0.6, "page": 42, "file": "who.pdf", "text": "khác"}]

    store = ResultStore(tmp_path / "r.csv", ["A05"])
    await run_retrieval([question("A05")], retrieve, store, threshold=0.65, sleep=FakeSleep(), log=lambda _: None)
    row = read(tmp_path / "r.csv")["A05"]
    top = json.loads(row["retrieval_topk"])
    assert row["trang_thai"] == STATUS_OK and row["auto_check"] == "can_cham_tay"
    assert [(t["hang"], t["trang_pdf"], t["qua_nguong"]) for t in top] == [(1, 12, True), (2, 42, False)]


async def test_retrieval_quota_error_is_marked(tmp_path):
    class ResourceExhausted(Exception):
        pass

    async def retrieve(text):
        try:
            raise ResourceExhausted()
        except ResourceExhausted as exc:
            raise RuntimeError("embedding lỗi") from exc

    store = ResultStore(tmp_path / "r.csv", ["A01"])
    await run_retrieval([question("A01")], retrieve, store, threshold=0.65, sleep=FakeSleep(), log=lambda _: None)
    assert read(tmp_path / "r.csv")["A01"]["trang_thai"] == STATUS_QUOTA
