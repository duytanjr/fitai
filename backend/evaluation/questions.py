"""Đọc file câu hỏi đánh giá (CHỈ ĐỌC — không ghi lại, không đụng cột điểm).

Bắt buộc: id, nhom, cau_hoi, chuan_bi. Các cột tiêu chí có thể trống (dòng thêm sau): khi đó
runner chỉ ghi can_cham_tay.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_COLUMNS = ("id", "nhom", "cau_hoi", "chuan_bi")
CRITERIA_COLUMNS = ("hanh_vi_mong_doi", "cong_cu_mong_doi", "nguon_mong_doi", "tieu_chi_dat", "dau_hieu_that_bai")
GROUP_ORDER = "ABCDEF"
TOOLS = ("search_knowledge", "calc_body_metrics", "lookup_food", "get_daily_summary")

# Tài khoản đánh giá (xem accounts.py)
ACCOUNT_SAMPLE = "mau"                    # hồ sơ mẫu + nhật ký hôm nay 4 món (F01)
ACCOUNT_NO_PROFILE = "chua_ho_so"         # chưa điền hồ sơ
ACCOUNT_EMPTY_LOG = "nhat_ky_trong"       # hồ sơ mẫu, nhật ký hôm nay trống


@dataclass
class Question:
    id: str
    nhom: str
    cau_hoi: str
    chuan_bi: str
    columns: dict[str, str] = field(default_factory=dict)

    def get(self, column: str) -> str:
        return (self.columns.get(column) or "").strip()

    @property
    def group(self) -> str:
        m = re.match(r"([A-Za-z])\d", self.id)
        return (m.group(1) if m else self.nhom.strip()[:1]).upper()

    @property
    def has_criteria(self) -> bool:
        return any(self.get(c) for c in CRITERIA_COLUMNS)

    @property
    def account(self) -> str:
        text = self.chuan_bi.lower()
        if "chưa điền hồ sơ" in text:
            return ACCOUNT_NO_PROFILE
        if "nhật ký hôm nay trống" in text:
            return ACCOUNT_EMPTY_LOG
        return ACCOUNT_SAMPLE          # hồ sơ mẫu (có nhật ký F01) hoặc "Bất kỳ tài khoản nào"


class QuestionFileError(ValueError):
    pass


def load_questions(path: Path) -> list[Question]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise QuestionFileError(f"Thiếu cột: {missing}")
        questions: list[Question] = []
        seen: set[str] = set()
        for row in reader:
            qid = (row.get("id") or "").strip()
            if not qid:
                continue
            if qid in seen:
                raise QuestionFileError(f"Trùng id: {qid}")
            seen.add(qid)
            questions.append(Question(
                id=qid, nhom=(row.get("nhom") or "").strip(), cau_hoi=(row.get("cau_hoi") or "").strip(),
                chuan_bi=(row.get("chuan_bi") or "").strip(),
                columns={k: (v or "") for k, v in row.items() if k},
            ))
    return questions


def order_and_filter(questions: list[Question], groups: list[str] | None = None,
                     ids: list[str] | None = None) -> list[Question]:
    """Theo thứ tự nhóm A→F (nhóm lạ xếp sau), giữ thứ tự trong file trong cùng nhóm."""
    wanted_groups = {g.upper() for g in groups or []}
    wanted_ids = {i.upper() for i in ids or []}
    picked = [q for q in questions
              if (not wanted_groups or q.group in wanted_groups) and (not wanted_ids or q.id.upper() in wanted_ids)]
    rank = {g: i for i, g in enumerate(GROUP_ORDER)}
    return sorted(picked, key=lambda q: rank.get(q.group, len(GROUP_ORDER)))


@dataclass(frozen=True)
class ToolExpectation:
    required: frozenset[str] = frozenset()
    optional: frozenset[str] = frozenset()
    expect_none: bool = False          # cột ghi "Không": không được gọi công cụ nào
    requires_grams: frozenset[str] = frozenset()   # công cụ phải được gọi với tham số grams
    skip: bool = False                 # trống / "Không bắt buộc" / "Có thể không gọi…": không kiểm tra


def parse_tool_expectation(text: str) -> ToolExpectation:
    """Quy tắc đọc cột cong_cu_mong_doi:
    - trống, "Không bắt buộc", "Có thể không gọi công cụ nào" → không kiểm tra;
    - đúng "Không" → không được gọi công cụ nào;
    - tên công cụ ngoài ngoặc → bắt buộc; "X (có thể)" hoặc "(có thể thêm Y)" → X/Y tuỳ chọn;
    - "X (có tham số grams)" / "X (có grams)" → X phải có tham số grams;
    - ngoặc khác (vd. "(trả gợi ý)", "(có thể không tìm ra do dưới ngưỡng)") chỉ là ghi chú.
    """
    t = (text or "").strip()
    low = t.lower()
    if not t or low.startswith("không bắt buộc") or low.startswith("có thể không gọi"):
        return ToolExpectation(skip=True)
    if not any(tool in t for tool in TOOLS):
        return ToolExpectation(expect_none=True) if low.startswith("không") else ToolExpectation(skip=True)

    required: set[str] = set()
    optional: set[str] = set()
    grams: set[str] = set()
    # Tách "tên (ngoặc)" theo thứ tự xuất hiện
    for m in re.finditer(r"(\w+)\s*(?:\(([^)]*)\))?", t):
        name, paren = m.group(1), (m.group(2) or "").strip().lower()
        if name not in TOOLS:
            continue
        if paren == "có thể":
            optional.add(name)
        else:
            required.add(name)
        if "grams" in paren:
            grams.add(name)
        if paren.startswith("có thể"):
            optional.update(tool for tool in TOOLS if tool in paren and tool != name)
    # Tên chỉ xuất hiện trong ngoặc "có thể thêm …" là tuỳ chọn, không bắt buộc
    for m in re.finditer(r"\(([^)]*)\)", t):
        inner = m.group(1).lower()
        if inner.startswith("có thể"):
            for tool in TOOLS:
                if tool in inner:
                    required.discard(tool)
                    optional.add(tool)
    return ToolExpectation(frozenset(required), frozenset(optional - required), False, frozenset(grams))
