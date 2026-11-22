"""Cảnh báo theo bệnh lý tự khai báo — nguồn DUY NHẤT cho mọi cảnh báo (API, báo cáo tuần, gợi ý tập, agent).

Mục đích: lưu ý an toàn chung và nhắc hỏi bác sĩ. KHÔNG phải chỉ dẫn điều trị, KHÔNG đổi mục tiêu dinh dưỡng
(BMI/BMR/TDEE/calo/macro luôn tính như người không bệnh) và KHÔNG lọc bài tập (kho bài tập chưa có nhãn
cường độ/tác động/nhóm cơ đủ để lọc).

Mỗi quy tắc PHẢI có `source` (nguồn thật đã kiểm trong kho tài liệu) hoặc để None = DESIGN_RULE.
Bảng cho tài liệu đồ án: `python scripts/export_health_rules.py` (docs/CHI_SO_CAN_CU.md, mục c).
Câu cảnh báo không kèm năm hay định dạng trích dẫn kiểu "WHO (2026)" (lớp chống trích dẫn không nguồn ở
frontend/src/lib/citations.ts sẽ bắt mẫu đó). Không ghi tên bệnh hay ghi chú ra log.
"""
from dataclasses import dataclass
from typing import Iterable, Literal

from models.profile import MEDICAL_CONDITION_CODES

DESIGN_RULE = "Quy tắc thiết kế, chưa có nguồn lâm sàng"

Domain = Literal["nutrition", "training", "general"]
DOMAINS: tuple[str, ...] = ("nutrition", "training", "general")
DOMAIN_LABELS = {"nutrition": "Dinh dưỡng", "training": "Tập luyện", "general": "Chung"}


@dataclass(frozen=True)
class RuleSource:
    """Nguồn đã kiểm (file trong kho tài liệu và trang chứa câu tương ứng)."""
    short: str          # nhãn ngắn hiển thị trên UI
    title: str
    org: str
    year: int
    page: int
    url: str
    file: str           # đường dẫn trong repo
    updated: str = ""   # ngày cập nhật của tài liệu (chỉ ghi ở bảng xuất, không trả qua API)

    @property
    def citation(self) -> str:
        """Chuỗi nguồn cho API (không kèm năm để agent không chép thành dạng trích dẫn "WHO (năm)")."""
        return f"{self.org}, {self.title}, tr. {self.page}"


WHO_HEALTHY_DIET = RuleSource(
    short="WHO, Healthy diet",
    title="Healthy diet (fact sheet)",
    org="WHO",
    year=2026,
    page=3,
    url="https://www.who.int/news-room/fact-sheets/detail/healthy-diet",
    file="data/knowledge/extra/who_healthy_diet.pdf",
    updated="26/01/2026",
)


@dataclass(frozen=True)
class HealthRule:
    id: str
    domain: Domain
    conditions: tuple[str, ...]      # mã bệnh kích hoạt quy tắc
    message: str                     # không có dấu chấm cuối (nơi hiển thị tự thêm)
    source: RuleSource | None = None  # None = DESIGN_RULE

    @property
    def source_text(self) -> str:
        return self.source.citation if self.source else DESIGN_RULE


HEALTH_RULES: tuple[HealthRule, ...] = (
    # ── Dinh dưỡng ──
    HealthRule(
        "salt", "nutrition", ("cardiovascular", "hypertension", "stroke"),
        "Nên hạn chế muối: WHO khuyến nghị người lớn dùng dưới 5 g muối mỗi ngày; "
        "hãy hỏi bác sĩ về mức phù hợp với bạn",
        WHO_HEALTHY_DIET,
    ),
    HealthRule(
        "sat_fat", "nutrition", ("cardiovascular",),
        "Lưu ý lượng chất béo bão hòa trong bữa ăn; hãy hỏi bác sĩ về chế độ ăn phù hợp",
    ),
    HealthRule(
        "metabolic_diet", "nutrition", ("metabolic",),
        "Cẩn thận khi cắt giảm calo mạnh và chú ý lượng, loại carb trong bữa ăn; "
        "hãy hỏi bác sĩ trước khi thay đổi chế độ ăn",
    ),
    # ── Tập luyện ──
    HealthRule(
        "msk_training", "training", ("musculoskeletal",),
        "Tránh bài có xung lực mạnh (như bật nhảy) và bài dồn tải nặng lên cột sống; "
        "hãy hỏi bác sĩ về bài tập phù hợp",
    ),
    HealthRule(
        "cardio_training", "training", ("cardiovascular",),
        "Giảm cường độ, không tập đến mức tối đa và chỉ tập khi bác sĩ đã cho phép; "
        "dừng tập ngay nếu đau ngực hoặc khó thở",
    ),
    HealthRule(
        "htn_training", "training", ("hypertension",),
        "Tập ở cường độ vừa và tránh nín thở khi nâng vật nặng; hãy hỏi bác sĩ trước khi tập",
    ),
    HealthRule(
        "metabolic_training", "training", ("metabolic",),
        "Theo dõi dấu hiệu hạ đường huyết khi tập; hãy hỏi bác sĩ cách phòng tránh và xử lý",
    ),
    HealthRule(
        "resp_training", "training", ("respiratory",),
        "Tập ở cường độ vừa, khởi động kỹ và mang theo thuốc nếu bác sĩ đã kê; hãy hỏi bác sĩ trước khi tập",
    ),
    HealthRule(
        "stroke_training", "training", ("stroke",),
        "Nên tập khi có người giám sát, chú ý thăng bằng và nguy cơ ngã; hãy hỏi bác sĩ trước khi tập",
    ),
    # ── Chung ──
    HealthRule(
        "other_general", "general", ("other",),
        "Mục tiêu và gợi ý chỉ mang tính tham khảo với tình trạng sức khỏe bạn khai báo; hãy hỏi bác sĩ",
    ),
)


def declared_conditions(raw) -> list[str]:
    """Mã bệnh hợp lệ theo thứ tự chuẩn, không trùng; mã lạ (không qua schema, vd. mã cũ) bị bỏ qua."""
    present = set(raw or [])
    return [code for code in MEDICAL_CONDITION_CODES if code in present]


def warning_out(rule: HealthRule, codes: list[str]) -> dict:
    return {
        "id": rule.id,
        "domain": rule.domain,
        "codes": codes,
        "message": rule.message,
        "source": rule.source_text,
        "source_short": rule.source.short if rule.source else None,
        "source_url": rule.source.url if rule.source else None,
    }


def health_warnings(conditions, domains: Iterable[str] | None = None) -> list[dict]:
    """Cảnh báo áp dụng cho các bệnh đã khai báo, theo thứ tự HEALTH_RULES; mỗi quy tắc xuất một lần.

    `codes` là các bệnh đã khai báo kích hoạt quy tắc (thứ tự chuẩn). `domains` để lọc theo lĩnh vực.
    """
    declared = declared_conditions(conditions)
    wanted = set(domains) if domains is not None else None
    out = []
    for rule in HEALTH_RULES:
        if wanted is not None and rule.domain not in wanted:
            continue
        codes = [c for c in declared if c in rule.conditions]
        if codes:
            out.append(warning_out(rule, codes))
    return out


def rules_table() -> list[dict]:
    """Bảng quy tắc cho tài liệu (dùng bởi scripts/export_health_rules.py)."""
    return [
        {
            "id": r.id,
            "domain": r.domain,
            "conditions": list(r.conditions),
            "message": r.message,
            "source": r.source_text,
            "source_url": r.source.url if r.source else None,
            "source_year": r.source.year if r.source else None,
            "source_updated": r.source.updated if r.source else None,
            "source_file": r.source.file if r.source else None,
        }
        for r in HEALTH_RULES
    ]
