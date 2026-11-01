"""Kiểm tra tự động (GỢI Ý, không phải điểm cuối) — CHỈ tiêu chí khách quan.

Trạng thái mỗi kiểm tra: dat | khong_dat | mot_phan | can_cham_tay. Tổng hợp: có khong_dat →
khong_dat; có mot_phan → mot_phan; mọi kiểm tra khách quan dat → dat; không có kiểm tra khách
quan nào → can_cham_tay. Tiêu chí chủ quan luôn được ghi "can_cham_tay" trong ghi chú.

Lưu ý: so với bảng foods / API chỉ chứng minh chatbot NHẤT QUÁN với DB, không chứng minh DB
đúng như PDF.

Quy tắc tách số (chấp nhận khi BẤT KỲ cách hiểu hợp lý nào khớp trong sai số):
- "63,4" → 63.4 (dấu phẩy thập phân kiểu Việt); "1,260" → 1.26 hoặc 1260 (phẩy ngăn nghìn kiểu Anh)
- "2.104" → 2104 (chấm ngăn nghìn kiểu Việt) hoặc 2.104 (chấm thập phân kiểu Anh)
- "1.260,8" → 1260.8 (kiểu Việt); "1,260.8" → 1260.8 (kiểu Anh); "2104" → 2104
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from evaluation.questions import Question, ToolExpectation, parse_tool_expectation

DAT, KHONG_DAT, MOT_PHAN, CAN_CHAM_TAY = "dat", "khong_dat", "mot_phan", "can_cham_tay"

_NUMBER = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)*(?![\w])")


def number_candidates(token: str) -> set[float]:
    """Mọi cách hiểu hợp lý của một chuỗi số."""
    out: set[float] = set()
    if "." in token and "," in token:
        if token.rfind(",") > token.rfind("."):          # 1.260,8 (Việt)
            out.add(float(token.replace(".", "").replace(",", ".")))
        else:                                             # 1,260.8 (Anh)
            out.add(float(token.replace(",", "")))
        return out
    for sep, other in ((".", ","), (",", ".")):
        if sep in token:
            parts = token.split(sep)
            if all(len(p) == 3 for p in parts[1:]):       # ngăn nghìn
                out.add(float("".join(parts)))
            if len(parts) == 2:                           # thập phân
                out.add(float(f"{parts[0]}.{parts[1]}"))
            return out
    out.add(float(token))
    return out


def numbers_in(text: str) -> list[tuple[str, set[float], int, int]]:
    return [(m.group(0), number_candidates(m.group(0)), m.start(), m.end()) for m in _NUMBER.finditer(text or "")]


def contains_value(text: str, expected: float, tol: float) -> bool:
    return any(abs(c - expected) <= tol for _, cands, _, _ in numbers_in(text) for c in cands)


_UNIT_AFTER = re.compile(r"\s*(kcal|calo|g)(?![\w/])", re.I)


def nutrient_numbers(text: str) -> list[tuple[str, set[float]]]:
    """Số đứng ngay trước đơn vị dinh dưỡng (kcal/calo/g, không tính "g/kg"). Bỏ "100 g" (mốc tính)."""
    out = []
    for token, cands, _, end in numbers_in(text):
        unit = _UNIT_AFTER.match(text, end)
        if not unit:
            continue
        if unit.group(1).lower() == "g" and 100.0 in cands:
            continue
        out.append((token, cands))
    return out


@dataclass
class CheckResult:
    status: str
    note: str


@dataclass
class References:
    """Dữ liệu đối chiếu do runner lấy từ API/DB trước khi kiểm tra."""
    metrics: dict[str, dict] = field(default_factory=dict)          # tài khoản → GET /profile/metrics
    summary: dict[str, dict] = field(default_factory=dict)          # tài khoản → GET /meals/summary
    foods: dict[int, Any] = field(default_factory=dict)             # mã → dòng foods (thuộc tính)
    substitutes: dict[str, list[tuple[str, float]]] = field(default_factory=dict)   # id → (nhãn, giá trị)


# Nhóm C: (mã trong bảng foods, tên mong đợi — test đối chiếu với DB, chất, số gam)
FOOD_CHECKS: dict[str, tuple[int, str, str, float]] = {
    "C01": (1004, "Gạo tẻ máy", "energy_kcal", 100),
    "C02": (1013, "Bánh phở", "carb_g", 200),
    "C03": (7013, "Thịt gà ta", "energy_kcal", 120),
    "C07": (7017, "Thịt lợn nạc", "energy_kcal", 100),
    "C08": (4100, "Súp lơ xanh", "protein_g", 100),
}
FOOD_TOLERANCE = 0.5          # cho phép làm tròn tới đơn vị (238,8 → 239)
# C04/C06/C09: không được chứa số liệu của mục thay thế (heuristic)
SUBSTITUTE_CHECKS = {"C04": "gợi ý cho 'ức gà'", "C06": "các nghĩa của 'bơ'", "C09": "gạo sống thay cho cơm"}
METRIC_TOLERANCE = 1.0
F01_TOLERANCE = 0.5           # chấp nhận 1260,8 hoặc 1261
TOOL_NAMES = ("search_knowledge", "calc_body_metrics", "lookup_food", "get_daily_summary")


def scaled(value: float | None, grams: float) -> float | None:
    return None if value is None else round(value * grams / 100.0, 1)


def check_tools(expect: ToolExpectation, calls: list[dict]) -> CheckResult | None:
    if expect.skip:
        return None
    called = [c["name"] for c in calls]
    names = set(called)
    if expect.expect_none:
        return (CheckResult(DAT, "công cụ: không gọi (đúng)") if not names
                else CheckResult(KHONG_DAT, f"công cụ: mong đợi không gọi, đã gọi {called}"))
    missing = sorted(expect.required - names)
    if missing:
        return CheckResult(KHONG_DAT, f"công cụ: thiếu {missing}, đã gọi {called}")
    no_grams = sorted(t for t in expect.requires_grams
                      if not any(c["name"] == t and "grams" in c.get("args", []) for c in calls))
    if no_grams:
        return CheckResult(KHONG_DAT, f"công cụ: {no_grams} không có tham số grams")
    extra = sorted(names - expect.required - expect.optional)
    note = f"công cụ: đúng {sorted(expect.required)}" + (f"; gọi thêm {extra}" if extra else "")
    return CheckResult(DAT, note)


def _metric_checks(q: Question, reply: str, refs: References) -> list[CheckResult]:
    m = refs.metrics.get(q.account) or {}
    if q.id == "B04":
        if m.get("is_complete"):
            return [CheckResult(CAN_CHAM_TAY, "B04: hồ sơ tài khoản không trống — kiểm tra lại chuẩn bị")]
        kcal = [t for t, _, _, end in numbers_in(reply) if re.match(r"\s*(kcal|calo)", reply[end:], re.I)]
        return [CheckResult(DAT if not kcal else KHONG_DAT,
                            "B04: không nêu số calo" if not kcal else f"B04: có số calo {kcal}")]
    if not m.get("is_complete"):
        return [CheckResult(CAN_CHAM_TAY, f"{q.id}: không có chỉ số API để đối chiếu")]
    wanted = {"B01": ["target_calories"], "B02": ["bmi"], "B03": ["protein_g", "fat_g", "carb_g"]}.get(q.id)
    if not wanted:
        return []
    out = []
    for key in wanted:
        ok = contains_value(reply, float(m[key]), METRIC_TOLERANCE)
        out.append(CheckResult(DAT if ok else KHONG_DAT, f"{key}={m[key]} {'có' if ok else 'KHÔNG có'} trong câu trả lời"))
    if q.id == "B02":
        cat = (m.get("bmi_category") or "").lower()
        ok = bool(cat) and cat in reply.lower()
        out.append(CheckResult(DAT if ok else KHONG_DAT, f"phân loại '{m.get('bmi_category')}' {'có' if ok else 'KHÔNG có'}"))
    return out


def _food_checks(q: Question, reply: str, sources: list[dict], refs: References) -> list[CheckResult]:
    if q.id in FOOD_CHECKS:
        code, name, nutrient, grams = FOOD_CHECKS[q.id]
        food = refs.foods.get(code)
        if food is None:
            return [CheckResult(CAN_CHAM_TAY, f"{q.id}: không thấy mã {code} trong bảng foods")]
        expected = scaled(getattr(food, nutrient), grams)
        ok = expected is not None and contains_value(reply, expected, FOOD_TOLERANCE)
        out = [CheckResult(DAT if ok else KHONG_DAT,
                           f"{name} {nutrient} theo {grams:g} g = {expected} {'có' if ok else 'KHÔNG có'} trong câu trả lời")]
        pages = [s.get("page") for s in sources]
        page_ok = food.source_page in pages
        out.append(CheckResult(DAT if page_ok else KHONG_DAT,
                               f"nguồn tr. {food.source_page} {'có' if page_ok else 'KHÔNG có'} (nguồn: {pages})"))
        return out
    if q.id in SUBSTITUTE_CHECKS:
        return [_substitute_check(q.id, reply, sources, refs.substitutes.get(q.id, []))]
    return []


def _substitute_check(qid: str, reply: str, sources: list[dict], values: list[tuple[str, float]]) -> CheckResult:
    """Heuristic: số liệu kèm đơn vị (kcal/g) trùng giá trị của mục thay thế → nghi vấn.
    Bỏ qua 100 g (mốc tính) và % (vd. thải bỏ 39%). Không chắc thì mot_phan / can_cham_tay."""
    found = nutrient_numbers(reply)
    if not found:
        note = f"{qid}: không có số liệu dinh dưỡng nào ({SUBSTITUTE_CHECKS[qid]})"
        return CheckResult(DAT if not sources else MOT_PHAN, note + ("" if not sources else f"; có nguồn {sources}"))
    hits = []
    for token, cands in found:
        for label, value in values:
            if value in (0, 100) or value < 1:
                continue
            if any(abs(c - value) <= 0.05 for c in cands):
                hits.append(f"{token} ≈ {label}")
    if hits:
        strong = [h for h in hits if len(re.sub(r"\D", "", h.split(" ≈ ")[0])) >= 3]
        return CheckResult(KHONG_DAT if strong else MOT_PHAN, f"{qid}: nghi dùng số của mục thay thế: {hits}")
    return CheckResult(CAN_CHAM_TAY, f"{qid}: có số kèm đơn vị {[t for t, _ in found]} nhưng không trùng mục thay thế")


def _summary_checks(q: Question, reply: str, refs: References) -> list[CheckResult]:
    s = refs.summary.get(q.account) or {}
    if not s:
        return [CheckResult(CAN_CHAM_TAY, f"{q.id}: không có /meals/summary để đối chiếu")]
    if q.id == "F01":
        out = []
        eaten = s["eaten"]["energy_kcal"]
        out.append(CheckResult(DAT if contains_value(reply, eaten, F01_TOLERANCE) else KHONG_DAT,
                               f"đã ăn {eaten} kcal {'có' if contains_value(reply, eaten, F01_TOLERANCE) else 'KHÔNG có'}"))
        if s.get("remaining"):
            rem = s["remaining"]["energy_kcal"]
            ok = contains_value(reply, rem, F01_TOLERANCE)
            out.append(CheckResult(DAT if ok else KHONG_DAT, f"còn lại {rem} kcal {'có' if ok else 'KHÔNG có'}"))
        if s.get("incomplete_totals"):
            ok = "chưa đầy đủ" in reply.lower()
            out.append(CheckResult(DAT if ok else MOT_PHAN, f"cảnh báo 'chưa đầy đủ' {'có' if ok else 'không thấy cụm này'}"))
        return out
    if q.id == "F02":
        if s.get("entries_count"):
            return [CheckResult(CAN_CHAM_TAY, f"F02: nhật ký không trống ({s['entries_count']} mục) — kiểm tra lại chuẩn bị")]
        target = (s.get("target") or {}).get("energy_kcal")
        kcal = [t for t, cands, _, end in numbers_in(reply)
                if re.match(r"\s*(kcal|calo)", reply[end:], re.I) and not (target and any(abs(c - target) <= 1 for c in cands))]
        return [CheckResult(DAT if not kcal else MOT_PHAN,
                            "F02: không nêu lượng đã ăn" if not kcal else f"F02: có số kcal khác mục tiêu {kcal}")]
    return []


def auto_check(q: Question, reply: str, sources: list[dict], calls: list[dict], refs: References) -> tuple[str, str]:
    if not q.has_criteria:
        return CAN_CHAM_TAY, "dòng chưa có tiêu chí: chấm tay"
    checks: list[CheckResult] = []
    tool = check_tools(parse_tool_expectation(q.get("cong_cu_mong_doi")), calls)
    if tool:
        checks.append(tool)
    if q.group == "B":
        checks += _metric_checks(q, reply, refs)
    elif q.group == "C":
        checks += _food_checks(q, reply, sources, refs)
    elif q.group == "D":
        checks.append(CheckResult(DAT if not sources else KHONG_DAT,
                                  "nguồn rỗng" if not sources else f"có nguồn {sources}"))
    elif q.group == "F":
        checks += _summary_checks(q, reply, refs)

    objective = [c for c in checks if c.status != CAN_CHAM_TAY]
    statuses = {c.status for c in objective}
    if KHONG_DAT in statuses:
        overall = KHONG_DAT
    elif MOT_PHAN in statuses:
        overall = MOT_PHAN
    elif objective:
        overall = DAT
    else:
        overall = CAN_CHAM_TAY
    notes = [f"[{c.status}] {c.note}" for c in checks] + ["[can_cham_tay] các tiêu chí còn lại"]
    return overall, "; ".join(notes)
