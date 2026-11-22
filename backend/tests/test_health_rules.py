"""Bảng cảnh báo theo bệnh (services/health_rules.py): mỗi quy tắc có nguồn hoặc DESIGN_RULE, câu chữ an toàn,
xuất bảng cho tài liệu và đồng bộ với docs/CHI_SO_CAN_CU.md (chỉ kiểm id có mặt, không so từng chữ)."""
import pathlib
import re
import sys

import pytest

from models.profile import MEDICAL_CONDITION_CODES
from services.health_rules import (
    DESIGN_RULE, DOMAINS, HEALTH_RULES, RuleSource, declared_conditions, health_warnings, rules_table,
)

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "scripts"))
import export_health_rules  # noqa: E402

WHO_SALT = "WHO khuyến nghị người lớn dùng dưới 5 g muối mỗi ngày"
YEAR = re.compile(r"\b(19|20)\d{2}\b")


def _repo_file(rel: str) -> pathlib.Path | None:
    """File theo đường dẫn từ gốc repo: trên máy (backend/..) hoặc trong container (/app có mount ./data)."""
    for base in (BACKEND.parent, BACKEND):
        path = base / rel
        if path.exists():
            return path
    return None


def test_rule_ids_unique_and_fields_valid():
    ids = [r.id for r in HEALTH_RULES]
    assert len(ids) == len(set(ids))
    for r in HEALTH_RULES:
        assert r.domain in DOMAINS, r.id
        assert r.conditions and set(r.conditions) <= set(MEDICAL_CONDITION_CODES), r.id


def test_every_rule_has_source_or_design_rule():
    for r in HEALTH_RULES:
        assert r.source is None or isinstance(r.source, RuleSource), r.id
        if r.source is None:
            assert r.source_text == DESIGN_RULE, r.id
        else:
            assert r.source_text != DESIGN_RULE and r.source.url.startswith("https://"), r.id
    sourced = [r.id for r in HEALTH_RULES if r.source is not None]
    assert sourced == ["salt"]  # chỉ ý muối có nguồn (WHO); còn lại là quy tắc thiết kế


def test_sourced_rule_points_to_file_in_repo():
    for r in HEALTH_RULES:
        if r.source is not None:
            assert _repo_file(r.source.file) is not None, r.source.file


def test_every_code_triggers_at_least_one_rule():
    for code in MEDICAL_CONDITION_CODES:
        assert health_warnings([code]), code


def test_messages_are_general_notes_without_year_or_citation_format():
    salt = next(r for r in HEALTH_RULES if r.id == "salt")
    assert WHO_SALT in salt.message
    for r in HEALTH_RULES:
        assert "bác sĩ" in r.message, r.id
        assert not r.message.endswith("."), r.id          # nơi hiển thị tự thêm dấu chấm
        assert not YEAR.search(r.message), r.id            # không kèm năm (lớp chống trích dẫn ở frontend)
        assert "(WHO" not in r.message, r.id
        if r.source is None:
            assert "WHO" not in r.message, r.id            # quy tắc thiết kế không gán cho tổ chức nào
    assert not YEAR.search(salt.source_text)                # chuỗi nguồn ở API cũng không kèm năm


def test_health_warnings_output_shape_dedup_and_filter():
    out = health_warnings(["stroke", "hypertension", "cardiovascular", "zq_ma_la", "kidney"])
    salt = [w for w in out if w["id"] == "salt"]
    assert len(salt) == 1 and salt[0]["codes"] == ["cardiovascular", "hypertension", "stroke"]
    assert salt[0] == {"id": "salt", "domain": "nutrition", "codes": ["cardiovascular", "hypertension", "stroke"],
                       "message": salt[0]["message"], "source": "WHO, Healthy diet (fact sheet), tr. 3",
                       "source_short": "WHO, Healthy diet",
                       "source_url": "https://www.who.int/news-room/fact-sheets/detail/healthy-diet"}
    assert [w["id"] for w in out] == ["salt", "sat_fat", "cardio_training", "htn_training", "stroke_training"]
    design = next(w for w in out if w["id"] == "sat_fat")
    assert design["source"] == DESIGN_RULE and design["source_short"] is None and design["source_url"] is None
    assert [w["id"] for w in health_warnings(["cardiovascular"], ("training", "general"))] == ["cardio_training"]
    assert health_warnings([]) == [] and health_warnings(None) == []
    assert declared_conditions(["other", "kidney", "metabolic", "other"]) == ["metabolic", "other"]


def test_export_table_has_every_rule_and_source():
    md = export_health_rules.markdown()
    lines = md.splitlines()
    assert len(lines) == 2 + len(HEALTH_RULES)
    for r in rules_table():
        assert f"| {r['id']} |" in md
    assert DESIGN_RULE in md and "https://www.who.int/news-room/fact-sheets/detail/healthy-diet" in md


def test_doc_lists_every_rule_id():
    doc = _repo_file("docs/CHI_SO_CAN_CU.md")
    if doc is None:
        pytest.skip("docs/ không có trong container backend (chỉ mount ./backend, ./data); chạy test này trên máy")
    text = doc.read_text(encoding="utf-8")
    for r in HEALTH_RULES:
        assert re.search(rf"(?<![\w-]){re.escape(r.id)}(?![\w-])", text), r.id
    assert DESIGN_RULE in text
