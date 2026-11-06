"""Gợi ý chương trình tập luyện (lát 9d, FR12). Luật do code quyết định, không gọi LLM.

`recommend_program` là hàm thuần; `recommendation_for_user` đọc hồ sơ (theo user_id từ JWT) và danh sách
chương trình published, dùng chung cho API /training/recommendation và công cụ recommend_program của agent.

Thứ tự xét:
0) Chốt chặn chỉ số cân nặng thấp (BMI < 18,5, xét TRƯỚC mọi luật, kể cả experience):
   - mục tiêu giảm cân → không gợi ý chương trình nào;
   - mục tiêu khác → loại các chương trình weight_loss; không còn chương trình nào → không gợi ý.
1) Thiếu mức vận động và experience None → mức beginner (ghi chú hồ sơ còn thiếu).
3) experience "regular" → intermediate.   4) experience "new" → beginner.
5) Vận động ít/nhẹ, hoặc BMI ≥ 30, hoặc tuổi ≥ 60 → beginner, thay thế intermediate.
6) Vận động vừa trở lên → intermediate, thay thế beginner.
Không lọc theo tuổi dưới 18. Câu lý do chỉ nêu dữ kiện đã dùng; không nêu con số BMI, không cam kết kết quả,
không lời khuyên y tế.
"""
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.profile import UserProfile
from models.training import TrainingProgram, TrainingStatus
from services.metrics_service import calculate_bmi

EXPERIENCES = ("regular", "new")
BEGINNER, INTERMEDIATE = "beginner", "intermediate"
LOW_BMI, HIGH_BMI, SENIOR_AGE = 18.5, 30.0, 60
LOW_ACTIVITY = ("sedentary", "light")
HIGHER_ACTIVITY = ("moderate", "active", "very_active")
ACTIVITY_LABELS = {"sedentary": "ít vận động", "light": "nhẹ", "moderate": "vừa", "active": "năng động",
                   "very_active": "rất năng động"}
LEVEL_LABELS = {BEGINNER: "người mới", INTERMEDIATE: "trung bình"}
# Mục tiêu trong hồ sơ → goal_tag của chương trình
GOAL_TO_TAG = {"weight_loss": "weight_loss", "muscle_gain": "muscle_gain", "endurance": "endurance",
               "maintenance": "general"}

NOTE_MISSING_INFO = "hồ sơ còn thiếu thông tin, gợi ý có thể chưa sát"
NOTE_CAN_GO_HIGHER = "nếu bạn đã quen tập đều thì có thể chọn chương trình nâng cao hơn"
NOTE_NO_GOAL_PROGRAM = "hiện chưa có chương trình riêng cho mục tiêu này"
NOTE_NO_BMI = "hồ sơ chưa có chiều cao hoặc cân nặng nên chưa xét chỉ số cân nặng"
NOTE_NO_AGE = "hồ sơ chưa có tuổi nên chưa xét theo tuổi"
NOTE_LOW_BMI_FILTER = "chỉ số cân nặng hiện thấp nên không gợi ý chương trình giảm cân"
REASON_LOW_BMI_WEIGHT_LOSS = "chỉ số cân nặng hiện thấp; chưa gợi ý chương trình giảm cân"
REASON_ONLY_WEIGHT_LOSS = ("chỉ số cân nặng hiện thấp; hiện chỉ có chương trình giảm cân nên chưa gợi ý "
                           "chương trình nào")
REASON_NO_PROGRAM = "hiện chưa có chương trình nào để gợi ý"


@dataclass(frozen=True)
class ProgramOption:
    slug: str
    level: str
    goal_tag: str
    duration_days: int
    title: str = ""


@dataclass(frozen=True)
class ProfileFacts:
    age: int | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    activity_level: str | None = None
    fitness_goal: str | None = None


@dataclass
class Recommendation:
    primary: str | None
    alternative: str | None
    reason_code: str
    reason: str
    notes: list[str] = field(default_factory=list)


def _bmi(p: ProfileFacts) -> float | None:
    if not p.height_cm or not p.weight_kg:
        return None
    try:
        return calculate_bmi(p.height_cm, p.weight_kg)[0]
    except ValueError:
        return None


def _join(facts: list[str]) -> str:
    return facts[0] if len(facts) == 1 else ", ".join(facts[:-1]) + " và " + facts[-1]


def _pick(candidates: list[ProgramOption], level: str, goal_tag: str | None,
          exclude: str | None = None) -> ProgramOption | None:
    """Cùng level; ưu tiên goal_tag trùng mục tiêu, rồi chương trình ngắn hơn, rồi slug."""
    pool = [p for p in candidates if p.level == level and p.slug != exclude]
    pool.sort(key=lambda p: (p.goal_tag != goal_tag, p.duration_days, p.slug))
    return pool[0] if pool else None


def recommend_program(profile: ProfileFacts | None, experience: str | None,
                      programs: list[ProgramOption]) -> Recommendation:
    profile = profile or ProfileFacts()
    if experience is not None and experience not in EXPERIENCES:
        raise ValueError("experience phải là 'regular', 'new' hoặc bỏ trống")
    activity = profile.activity_level if profile.activity_level in ACTIVITY_LABELS else None
    goal = profile.fitness_goal
    goal_tag = GOAL_TO_TAG.get(goal) if goal else None
    bmi = _bmi(profile)
    notes: list[str] = []
    if bmi is None:
        notes.append(NOTE_NO_BMI)

    # 0) Chốt chặn chỉ số cân nặng thấp — trước mọi luật, kể cả experience
    candidates = list(programs)
    if bmi is not None and bmi < LOW_BMI:
        if goal == "weight_loss":
            return Recommendation(None, None, "bmi_thap_muc_tieu_giam_can", REASON_LOW_BMI_WEIGHT_LOSS, notes)
        candidates = [p for p in programs if p.goal_tag != "weight_loss"]
        if programs and not candidates:
            return Recommendation(None, None, "chi_co_chuong_trinh_giam_can", REASON_ONLY_WEIGHT_LOSS, notes)
        if len(candidates) != len(programs):
            notes.append(NOTE_LOW_BMI_FILTER)
    if not candidates:
        return Recommendation(None, None, "chua_co_chuong_trinh", REASON_NO_PROGRAM, notes)

    alt_level: str | None = None
    if activity is None and experience is None:                                   # 1
        level, code, because = BEGINNER, "thieu_thong_tin", "vì hồ sơ chưa có mức vận động"
        notes.insert(0, NOTE_MISSING_INFO)
    elif experience == "regular":                                                 # 3
        level, code, because = INTERMEDIATE, "da_tap_deu", "vì bạn cho biết đã tập đều trong vài tháng qua"
    elif experience == "new":                                                     # 4
        level, code, because = BEGINNER, "moi_bat_dau", "vì bạn cho biết mới bắt đầu tập"
    else:
        facts = []
        if activity in LOW_ACTIVITY:
            facts.append(f"mức vận động của bạn là {ACTIVITY_LABELS[activity]}")
        if bmi is not None and bmi >= HIGH_BMI:
            facts.append("chỉ số cân nặng (BMI) theo hồ sơ từ 30 trở lên")
        if profile.age is not None and profile.age >= SENIOR_AGE:
            facts.append("bạn từ 60 tuổi trở lên")
        if profile.age is None:
            notes.append(NOTE_NO_AGE)
        if facts:                                                                 # 5
            level, alt_level, code = BEGINNER, INTERMEDIATE, "nen_bat_dau_nhe"
            because = "vì " + _join(facts)
            notes.append(NOTE_CAN_GO_HIGHER)
        else:                                                                     # 6
            level, alt_level, code = INTERMEDIATE, BEGINNER, "muc_van_dong_vua_tro_len"
            because = f"vì mức vận động của bạn là {ACTIVITY_LABELS[activity]}"

    primary = _pick(candidates, level, goal_tag)
    if primary is None:
        other = INTERMEDIATE if level == BEGINNER else BEGINNER
        primary = _pick(candidates, other, goal_tag)
        notes.append(f"chưa có chương trình mức {LEVEL_LABELS[level]} nên gợi ý chương trình gần nhất "
                     f"(mức {LEVEL_LABELS[other]})")
    alternative = _pick(candidates, alt_level, goal_tag, exclude=primary.slug) if alt_level else None
    if goal in GOAL_TO_TAG and goal != "weight_loss" and not any(p.goal_tag == goal_tag for p in candidates):
        notes.append(NOTE_NO_GOAL_PROGRAM)
    reason = f"Nên bắt đầu ở mức {LEVEL_LABELS[level]} {because}."
    return Recommendation(primary.slug, alternative.slug if alternative else None, code, reason, notes)


# ── Đọc DB ───────────────────────────────────────────────────────────────────

def _option_out(option: ProgramOption | None) -> dict | None:
    if option is None:
        return None
    return {"slug": option.slug, "title": option.title, "duration_days": option.duration_days,
            "level": option.level, "goal_tag": option.goal_tag}


async def recommendation_for_user(db: AsyncSession, user_id: uuid.UUID, experience: str | None) -> dict:
    """Hồ sơ của chính user_id (không nhận hồ sơ từ client); không có hồ sơ → coi như thiếu thông tin."""
    row = await db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
    facts = ProfileFacts(age=row.age, height_cm=row.height_cm, weight_kg=row.weight_kg,
                         activity_level=row.activity_level, fitness_goal=row.fitness_goal) if row else ProfileFacts()
    programs = [ProgramOption(slug=p.slug, level=p.level.value, goal_tag=p.goal_tag.value,
                              duration_days=p.duration_days, title=p.title)
                for p in (await db.scalars(select(TrainingProgram).where(
                    TrainingProgram.status == TrainingStatus.PUBLISHED))).all()]
    rec = recommend_program(facts, experience, programs)
    by_slug = {p.slug: p for p in programs}
    return {
        "primary": _option_out(by_slug.get(rec.primary)),
        "alternative": _option_out(by_slug.get(rec.alternative)),
        "reason_code": rec.reason_code,
        "reason": rec.reason,
        "notes": rec.notes,
        "experience": experience,
    }
