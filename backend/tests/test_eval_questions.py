"""Tests đọc file câu hỏi đánh giá (chỉ đọc) và phân tích cột công cụ mong đợi."""
from pathlib import Path

import pytest

from core.config import settings
from evaluation.questions import (
    ACCOUNT_EMPTY_LOG,
    ACCOUNT_NO_PROFILE,
    ACCOUNT_SAMPLE,
    QuestionFileError,
    ToolExpectation,
    load_questions,
    order_and_filter,
    parse_tool_expectation,
)

REAL_FILE = Path(settings.KNOWLEDGE_DIR).parent / "eval" / "eval_questions.csv"


@pytest.fixture
def real_questions():
    if not REAL_FILE.exists():
        pytest.skip(f"Không thấy {REAL_FILE}")
    return load_questions(REAL_FILE)


def test_real_file_has_38_questions_in_six_groups(real_questions):
    assert len(real_questions) == 38
    assert {q.group for q in real_questions} == set("ABCDEF")
    assert [q.id for q in order_and_filter(real_questions)][:2] == ["A01", "A02"]
    assert all(q.has_criteria for q in real_questions)


def test_accounts_follow_preparation_column(real_questions):
    by_id = {q.id: q for q in real_questions}
    assert by_id["B04"].account == ACCOUNT_NO_PROFILE
    assert by_id["F02"].account == ACCOUNT_EMPTY_LOG
    assert by_id["F01"].account == ACCOUNT_SAMPLE and by_id["B01"].account == ACCOUNT_SAMPLE
    assert by_id["A01"].account == ACCOUNT_SAMPLE                       # "Bất kỳ tài khoản nào"


def test_filter_by_group_and_id(real_questions):
    assert [q.id for q in order_and_filter(real_questions, groups=["d"])] == ["D01", "D02", "D03", "D04", "D05"]
    assert [q.id for q in order_and_filter(real_questions, ids=["c04", "A01"])] == ["A01", "C04"]


def write_csv(tmp_path, text):
    p = tmp_path / "q.csv"
    p.write_text(text, encoding="utf-8-sig")
    return p


def test_rows_with_only_basic_columns_are_accepted(tmp_path):
    p = write_csv(tmp_path, "id,nhom,cau_hoi,chuan_bi,hanh_vi_mong_doi\nG01,G. Mới,Câu mới?,Bất kỳ,\n")
    [q] = load_questions(p)
    assert q.id == "G01" and q.group == "G" and not q.has_criteria
    assert order_and_filter([q])[0].id == "G01"


def test_missing_required_column_or_duplicate_id_is_rejected(tmp_path):
    with pytest.raises(QuestionFileError, match="Thiếu cột"):
        load_questions(write_csv(tmp_path, "id,nhom,cau_hoi\nA01,A,x\n"))
    with pytest.raises(QuestionFileError, match="Trùng id"):
        load_questions(write_csv(tmp_path, "id,nhom,cau_hoi,chuan_bi\nA01,A,x,y\nA01,A,z,y\n"))


@pytest.mark.parametrize("text,expected", [
    ("search_knowledge", ToolExpectation(frozenset({"search_knowledge"}))),
    ("search_knowledge (có thể thêm calc_body_metrics)",
     ToolExpectation(frozenset({"search_knowledge"}), frozenset({"calc_body_metrics"}))),
    ("search_knowledge (có thể không tìm ra do dưới ngưỡng)", ToolExpectation(frozenset({"search_knowledge"}))),
    ("calc_body_metrics (trả is_complete=false)", ToolExpectation(frozenset({"calc_body_metrics"}))),
    ("calc_body_metrics (có thể)", ToolExpectation(optional=frozenset({"calc_body_metrics"}))),
    ("calc_body_metrics, search_knowledge", ToolExpectation(frozenset({"calc_body_metrics", "search_knowledge"}))),
    ("lookup_food (có tham số grams)",
     ToolExpectation(frozenset({"lookup_food"}), requires_grams=frozenset({"lookup_food"}))),
    ("lookup_food (có grams)", ToolExpectation(frozenset({"lookup_food"}), requires_grams=frozenset({"lookup_food"}))),
    ("lookup_food (trả CHI_CO_DANG_SONG hoặc hỏi lại)", ToolExpectation(frozenset({"lookup_food"}))),
    ("Không", ToolExpectation(expect_none=True)),
    ("Không bắt buộc", ToolExpectation(skip=True)),
    ("Có thể không gọi công cụ nào", ToolExpectation(skip=True)),
    ("", ToolExpectation(skip=True)),
])
def test_parse_tool_expectation(text, expected):
    assert parse_tool_expectation(text) == expected


def test_every_tool_column_in_real_file_is_understood(real_questions):
    for q in real_questions:
        exp = parse_tool_expectation(q.get("cong_cu_mong_doi"))
        assert exp.skip or exp.expect_none or exp.required or exp.optional, q.id
