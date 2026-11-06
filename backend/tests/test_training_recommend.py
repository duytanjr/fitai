"""Ma trận luật gợi ý chương trình (services/training/recommend.py, lát 9d) — hàm thuần, không DB, không LLM."""
import pytest

from services.training.recommend import (
    NOTE_CAN_GO_HIGHER, NOTE_LOW_BMI_FILTER, NOTE_MISSING_INFO, NOTE_NO_AGE, NOTE_NO_BMI, NOTE_NO_GOAL_PROGRAM,
    REASON_LOW_BMI_WEIGHT_LOSS, REASON_NO_PROGRAM, REASON_ONLY_WEIGHT_LOSS, ProfileFacts, ProgramOption,
    recommend_program,
)

BEG = ProgramOption("zq-nguoi-moi", "beginner", "weight_loss", 14, "Zq người mới")
MID = ProgramOption("zq-toan-than", "intermediate", "weight_loss", 28, "Zq toàn thân")
GEN = ProgramOption("zq-chung", "beginner", "general", 21, "Zq sức khoẻ chung")
BOTH = [BEG, MID]

# Cao 170 cm: 53 kg → BMI 18,3; 53,5 → 18,5; 86,7 → 30,0; 86,6 → 30,0 (làm tròn); 86,5 → 29,9; 65 → 22,5
H = 170.0


def facts(weight=65.0, activity="moderate", goal="weight_loss", age=30, height=H) -> ProfileFacts:
    return ProfileFacts(age=age, height_cm=height, weight_kg=weight, activity_level=activity, fitness_goal=goal)


def rec(profile, experience=None, programs=BOTH):
    return recommend_program(profile, experience, programs)


# ── Luật 1: thiếu mức vận động ───────────────────────────────────────────────

def test_rule1_missing_activity():
    r = rec(facts(activity=None))
    assert (r.primary, r.alternative, r.reason_code) == (BEG.slug, None, "thieu_thong_tin")
    assert r.notes[0] == NOTE_MISSING_INFO and "vì hồ sơ chưa có mức vận động" in r.reason


def test_rule1_no_profile_at_all():
    r = rec(None)
    assert (r.primary, r.reason_code) == (BEG.slug, "thieu_thong_tin")
    assert NOTE_MISSING_INFO in r.notes and NOTE_NO_BMI in r.notes


def test_rule1_skipped_when_experience_given():
    assert rec(facts(activity=None), "regular").reason_code == "da_tap_deu"
    assert rec(facts(activity=None), "new").reason_code == "moi_bat_dau"


# ── Luật 2 / chốt chặn chỉ số cân nặng thấp ──────────────────────────────────

def test_low_bmi_weight_loss_blocks_everything():
    r = rec(facts(weight=53.0))
    assert (r.primary, r.alternative, r.reason_code, r.reason) == \
        (None, None, "bmi_thap_muc_tieu_giam_can", REASON_LOW_BMI_WEIGHT_LOSS)


@pytest.mark.parametrize("experience", [None, "regular", "new"])
def test_experience_cannot_bypass_low_bmi_gate(experience):
    assert rec(facts(weight=53.0), experience).primary is None
    assert rec(facts(weight=53.0, activity=None), experience).reason_code == "bmi_thap_muc_tieu_giam_can"


def test_low_bmi_gate_before_missing_activity_rule():
    r = rec(facts(weight=53.0, activity=None))
    assert r.primary is None and r.reason_code == "bmi_thap_muc_tieu_giam_can"


def test_bmi_18_4_muscle_gain_only_weight_loss_programs():
    r = rec(facts(weight=53.2, goal="muscle_gain"))                # 53,2 / 1,7² = 18,4
    assert (r.primary, r.alternative, r.reason_code, r.reason) == \
        (None, None, "chi_co_chuong_trinh_giam_can", REASON_ONLY_WEIGHT_LOSS)
    assert rec(facts(weight=53.2, goal="muscle_gain"), "regular").primary is None


def test_bmi_low_other_goal_keeps_non_weight_loss_programs():
    r = rec(facts(weight=53.2, goal="maintenance"), programs=[BEG, MID, GEN])
    assert r.primary == GEN.slug and NOTE_LOW_BMI_FILTER in r.notes
    assert r.alternative is None                                   # không có intermediate ngoài weight_loss


def test_bmi_18_5_not_blocked():
    r = rec(facts(weight=53.5))                                    # 18,5
    assert r.primary == MID.slug and r.reason_code == "muc_van_dong_vua_tro_len"
    r = rec(facts(weight=53.5, goal="muscle_gain"))
    assert r.primary == MID.slug


@pytest.mark.parametrize("height,weight", [(None, 45.0), (H, None), (None, None)])
def test_missing_height_or_weight_no_gate_but_note(height, weight):
    r = rec(facts(height=height, weight=weight))
    assert r.primary == MID.slug and NOTE_NO_BMI in r.notes


def test_low_bmi_texts_have_no_number_or_medical_advice():
    for r in (rec(facts(weight=53.0)), rec(facts(weight=53.2, goal="muscle_gain")),
              rec(facts(weight=53.2, goal="maintenance"), programs=[BEG, MID, GEN])):
        text = " ".join([r.reason, *r.notes]).lower()
        assert not any(ch.isdigit() for ch in text)
        for banned in ("bác sĩ", "thiếu cân", "suy dinh dưỡng", "bệnh", "nên ăn", "kcal"):
            assert banned not in text


# ── Luật 3, 4: experience ghi đè mức vận động ────────────────────────────────

@pytest.mark.parametrize("activity", ["sedentary", "light", "moderate", "very_active"])
def test_experience_overrides_activity(activity):
    assert rec(facts(activity=activity), "regular").primary == MID.slug
    assert rec(facts(activity=activity), "new").primary == BEG.slug


def test_experience_overrides_age_and_high_bmi():
    r = rec(facts(weight=100.0, age=70), "regular")
    assert (r.primary, r.alternative, r.reason_code) == (MID.slug, None, "da_tap_deu")
    assert r.reason == "Nên bắt đầu ở mức trung bình vì bạn cho biết đã tập đều trong vài tháng qua."


def test_invalid_experience_rejected():
    with pytest.raises(ValueError):
        rec(facts(), "sometimes")


# ── Luật 5, 6 ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("activity,label", [("sedentary", "ít vận động"), ("light", "nhẹ")])
def test_rule5_low_activity(activity, label):
    r = rec(facts(activity=activity))
    assert (r.primary, r.alternative, r.reason_code) == (BEG.slug, MID.slug, "nen_bat_dau_nhe")
    assert r.reason == f"Nên bắt đầu ở mức người mới vì mức vận động của bạn là {label}."
    assert NOTE_CAN_GO_HIGHER in r.notes


@pytest.mark.parametrize("weight,expected", [(86.5, "muc_van_dong_vua_tro_len"), (86.7, "nen_bat_dau_nhe")])
def test_rule5_bmi_30_boundary(weight, expected):
    r = rec(facts(weight=weight))                                  # 29,9 / 30,0
    assert r.reason_code == expected
    if expected == "nen_bat_dau_nhe":
        assert "chỉ số cân nặng (BMI) theo hồ sơ từ 30 trở lên" in r.reason and "30,0" not in r.reason


@pytest.mark.parametrize("age,expected", [(59, "muc_van_dong_vua_tro_len"), (60, "nen_bat_dau_nhe")])
def test_rule5_age_60_boundary(age, expected):
    r = rec(facts(age=age))
    assert r.reason_code == expected
    if age == 60:
        assert "bạn từ 60 tuổi trở lên" in r.reason


def test_rule5_lists_all_matched_facts():
    r = rec(facts(activity="light", weight=90.0, age=65))
    assert r.reason == ("Nên bắt đầu ở mức người mới vì mức vận động của bạn là nhẹ, chỉ số cân nặng (BMI) theo "
                        "hồ sơ từ 30 trở lên và bạn từ 60 tuổi trở lên.")


@pytest.mark.parametrize("activity,label", [("moderate", "vừa"), ("active", "năng động"),
                                            ("very_active", "rất năng động")])
def test_rule6_higher_activity(activity, label):
    r = rec(facts(activity=activity))
    assert (r.primary, r.alternative, r.reason_code) == (MID.slug, BEG.slug, "muc_van_dong_vua_tro_len")
    assert r.reason == f"Nên bắt đầu ở mức trung bình vì mức vận động của bạn là {label}."


def test_missing_age_note():
    r = rec(facts(age=None))
    assert r.reason_code == "muc_van_dong_vua_tro_len" and NOTE_NO_AGE in r.notes


def test_no_age_filter_under_18():
    assert rec(facts(age=15)).primary == MID.slug
    assert rec(facts(age=15, activity="light")).primary == BEG.slug


# ── Mục tiêu khác giảm cân ───────────────────────────────────────────────────

@pytest.mark.parametrize("goal", ["muscle_gain", "endurance", "maintenance"])
def test_other_goal_note_when_no_matching_program(goal):
    r = rec(facts(goal=goal))
    assert r.primary == MID.slug and NOTE_NO_GOAL_PROGRAM in r.notes


def test_other_goal_no_note_when_matching_program_exists():
    r = rec(facts(goal="maintenance", activity="light"), programs=[BEG, MID, GEN])
    assert r.primary == GEN.slug and NOTE_NO_GOAL_PROGRAM not in r.notes    # ưu tiên goal_tag trùng mục tiêu


def test_weight_loss_goal_no_goal_note():
    assert NOTE_NO_GOAL_PROGRAM not in rec(facts()).notes
    assert NOTE_NO_GOAL_PROGRAM not in rec(facts(goal=None)).notes


# ── Không có chương trình / không đúng level ─────────────────────────────────

def test_no_published_programs():
    for profile in (facts(), facts(activity=None), facts(weight=53.2, goal="muscle_gain")):
        r = rec(profile, programs=[])
        assert (r.primary, r.alternative, r.reason_code, r.reason) == \
            (None, None, "chua_co_chuong_trinh", REASON_NO_PROGRAM)


def test_no_program_of_wanted_level_uses_nearest():
    r = rec(facts(activity="moderate"), programs=[BEG])
    assert (r.primary, r.alternative) == (BEG.slug, None)
    assert any("chưa có chương trình mức trung bình" in n for n in r.notes)
    r = rec(facts(), "new", programs=[MID])
    assert r.primary == MID.slug and any("chưa có chương trình mức người mới" in n for n in r.notes)


def test_tie_break_shorter_then_slug():
    long_beg = ProgramOption("zq-a-dai", "beginner", "weight_loss", 30)
    short_beg = ProgramOption("zq-b-ngan", "beginner", "weight_loss", 10)
    assert rec(facts(activity="light"), programs=[long_beg, short_beg]).primary == short_beg.slug


def test_reason_never_promises_results():
    profiles = [facts(), facts(activity=None), facts(activity="light"), facts(weight=95.0), facts(age=70),
                facts(goal="muscle_gain")]
    for p in profiles:
        for exp in (None, "regular", "new"):
            r = rec(p, exp)
            text = " ".join([r.reason, *r.notes]).lower()
            for banned in ("giảm được", "đảm bảo", "chắc chắn", "kcal", "kg", "bác sĩ", "đạt"):
                assert banned not in text, (p, exp, banned)
