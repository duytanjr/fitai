"""Tests từ đồng nghĩa, từ mơ hồ, trạng thái trong tra cứu, và backfill preparation.

Phần DB dùng PostgreSQL THẬT trong transaction tự rollback (fixture foods_session của
test_foods_db: bảng foods được làm rỗng trong transaction). Test đối chiếu mã số AMBIGUOUS
đọc dữ liệu thật (không xoá gì) và SKIP nếu chưa nạp bảng foods.
"""
import uuid
from datetime import date

import pytest
from sqlalchemy import func, select, text

from core.security import get_password_hash
from models.food import Food
from models.meal_log import MealLog, MealType
from models.user import User
from models.food_source import FoodSource
from services.foods.sources import USDA_SR
from services.foods.aliases import (
    AMBIGUOUS,
    COOKED_DISHES,
    FOOD_ALIASES,
    EXPECTED_NAMES,
    SYNONYMS,
    ambiguity_key,
    expand,
    find_ambiguous,
    find_cooked_dish,
)
from services.foods.ingest import apply_preparation_backfill, plan_preparation_backfill
from services.foods.lookup import MATCH_EXACT, AmbiguousFoodQuery, RawOnlyFoodQuery, accent_words, search_foods
from services.foods.preparation import PREPARATION_OVERRIDES, FoodPreparation
from tests.test_foods_db import foods_session, make_food, seed  # noqa: F401 — fixture dùng chung


def food(code, name, page=1, en=None, **values):
    f = make_food(code, name, page, **values)
    f.name_en = en
    return f


ALIAS_FOODS = [
    food(7017, "Thịt lợn nạc", 321, "Pork, lean"),
    food(7018, "Thịt lợn nửa nạc, nửa mỡ", 322, "Pork, medium fat"),
    food(3025, "Đậu phụ", 91, "Soybean curt cake pressed, raw"),
    food(1012, "Bánh mỳ", 25, "French bread"),
    food(1022, "Mỳ sợi", 35, "Wheat noodles"),
    food(1018, "Bột mì", 31, "Wheat flour"),
    food(5028, "Mít dai", 258, "Jackfruit"),                         # 'mi' khớp đầu từ 'mít' — không liên quan
    food(6014, "Dầu oliu", 302, "Olive oil, salad or cooking"),
    food(6008, "Dầu cọ", 296, "Palm oil"),
    food(8042, "Ốc đá", 430, "Marble snail"),                         # 'o' khớp đầu 'oc' — không liên quan
    food(4100, "Súp lơ xanh", 202, "Cauliflower, green"),
    food(4016, "Cải xanh", 118, "Mustard greens"),
    food(5042, "Quả bơ vỏ xanh", 272, "Avocado, green"),
    food(5041, "Quả bơ vỏ tím", 271, "Avocado, purple"),
    food(6001, "Bơ", 289, "Butter, unsalted"),
    food(7003, "Thịt bò loại I", 307, "Beef, grade I"),
    food(5010, "Dưa bở", 240, "Musk melon"),
    food(7007, "Thịt bồ câu ra ràng", 311, "Pigeon"),
    food(8051, "Tôm biển", 439, "Sea shrimp"),
    food(8052, "Tôm đồng", 440, "Fresh-water shrimp"),
    food(8053, "Tôm khô", 441, "Shrimp, dried"),
    food(5007, "Chuối tiêu", 237, "Banana, dwarf"),
    food(5006, "Chuối tây", 236, "Banana"),
    food(4019, "Chuối xanh", 121, "Banana common varieties, unripe"),
    food(5005, "Chuối khô", 235, "Banana, dried"),
    food(11001, "Chuối nước đường", 474, "Banana, canned, sweetened"),
    food(1004, "Gạo tẻ máy", 17, "Ordinary polished rice"),
    food(1003, "Gạo tẻ giã", 16, "Under milled, home-pounded rice"),
    food(1001, "Gạo nếp cái", 14, "Glutinous rice, milled"),
    food(1002, "Gạo nếp máy (Loại thường)", 15, "Glutinous rice, milled"),
    food(4021, "Củ cải trắng", 123, "Radish garden while, raw"),
    food(9003, "Lòng trắng trứng gà", 452, "Hen egg, white"),
    food(2025, "Sắn khô", 63, "Dried bitter cassava"),
    food(7058, "Thịt chó sấn", 362, "Dog meat"),                    # 'sấn' ≈ 'sắn' khi bỏ dấu
    food(1013, "Bánh phở", 26, "Rice noodles"),
]


async def names(session, query, limit=10):
    return [(m.food.name_vi, m.matched_via) for m in await search_foods(session, query, limit=limit)]


# ── Cấu hình ─────────────────────────────────────────────────────────────────
APPROVED_SYNONYMS = [
    ("heo", "lợn", False), ("đậu hũ", "đậu phụ", False), ("mì", "mỳ", True),
    ("bánh mì", "bánh mỳ", False), ("ô liu", "oliu", True),     # 5d-2: bỏ "bông cải xanh → súp lơ xanh"
    ("đậu phộng", "lạc", False), ("hạt mè", "vừng", False), ("bắp cải", "cải bắp", False),
    ("khóm", "dứa", False), ("trái thơm", "dứa", False), ("khổ qua", "mướp đắng", False),
    ("ngò rí", "rau mùi", False), ("cá lóc", "cá quả", False), ("dưa leo", "dưa chuột", False),
    ("bông cải trắng", "súp lơ trắng", False), ("nấm đông cô", "nấm hương", False), ("khoai mì", "sắn", False),
    ("hột gà", "trứng gà", False), ("hột vịt", "trứng vịt", False), ("quýt", "quít", True),
    ("trái", "quả", False), ("bí đỏ", "bí ngô", False),
]


def test_synonym_list_is_exactly_the_approved_list():
    assert [(s.source, s.target, s.bidirectional) for s in SYNONYMS] == APPROVED_SYNONYMS
    assert set(AMBIGUOUS) == {"bơ", "bo", "tôm", "tom", "chuối", "chuoi",
                              "bắp", "mè", "thơm", "mãng cầu", "táo", "hồng", "dưa", "com"}


def test_expand_matches_whole_phrases_only():
    assert expand(["thit", "heo", "nac"]) == [(["thit", "lon", "nac"], "heo → lợn", ("lợn",))]
    assert expand(["dau", "hu"]) == [(["dau", "phu"], "đậu hũ → đậu phụ", ("đậu", "phụ"))]
    assert expand(["hu", "tieu"]) == []                     # "hũ" đơn lẻ không bị đổi ("hủ tiếu")
    assert expand(["mit"]) == []                             # "mi" phải là nguyên từ
    assert (["bot", "mi"], "mỳ → mì", ("mì",)) in expand(["bot", "my"])
    assert expand(["ngo"]) == []                             # chỉ cụm "ngò rí", không phải "ngò"


def test_cooked_dish_matching_ignores_color_words_only():
    assert find_cooked_dish("xôi").raw_label == "gạo nếp" and find_cooked_dish("Xôi trắng").label == "xôi"
    assert find_cooked_dish("cháo").raw_label == "gạo tẻ"
    assert find_cooked_dish("cơm") is None and find_cooked_dish("cơm trắng") is None   # 5d-2: cơm có ở USDA
    assert find_cooked_dish("chao") is None                  # trùng "Lạc chao dầu"


def test_ambiguity_uses_accented_whole_query():
    assert find_ambiguous("Bơ")[0] == "bơ"
    assert find_ambiguous("  bo ")[0] == "bo"
    assert find_ambiguous("bò") is None                      # thịt bò, không mơ hồ
    assert find_ambiguous("quả bơ") is None and find_ambiguous("tôm biển") is None


def test_every_ambiguous_code_has_expected_name():
    refs = {r for meanings in AMBIGUOUS.values() for m in meanings for r in m.refs}
    refs |= {r for d in COOKED_DISHES.values() for r in d.refs}
    refs |= {r for a in FOOD_ALIASES.values() for r in a.refs}
    assert refs <= set(EXPECTED_NAMES)
    bo_meanings = [m.label for m in AMBIGUOUS["bo"]]
    assert bo_meanings == ["quả bơ", "bơ động vật (butter)", "thịt bò"]
    assert AMBIGUOUS["bo"][2].search == "thịt bò" and AMBIGUOUS["bo"][2].refs == ()


async def test_ambiguous_codes_exist_in_real_foods_table(db_session):
    """Đối chiếu trực tiếp với dữ liệu đã nạp (chỉ đọc)."""
    try:
        total = (await db_session.execute(select(func.count()).select_from(Food))).scalar_one()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Không đọc được bảng foods ({type(exc).__name__})")
    if total == 0:
        pytest.skip("Bảng foods chưa có dữ liệu — hãy chạy scripts/ingest_foods.py")
    rows = (await db_session.execute(select(FoodSource.code, Food.source_ref, Food.name_vi).join(
        FoodSource, FoodSource.id == Food.source_id))).all()
    actual = {(c, ref): name for c, ref, name in rows}
    for ref, name in EXPECTED_NAMES.items():
        if ref[0] == USDA_SR and not any(k[0] == USDA_SR for k in actual):
            continue                                         # chưa nạp USDA trên DB này
        assert actual.get(ref) == name, ref


async def _real_names(db_session) -> list[str]:
    try:
        names_ = list((await db_session.execute(select(Food.name_vi).where(Food.code < 99000))).scalars())
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Không đọc được bảng foods ({type(exc).__name__})")
    if not names_:
        pytest.skip("Bảng foods chưa có dữ liệu — hãy chạy scripts/ingest_foods.py")
    return names_


async def test_synonym_rule_target_exists_and_source_is_not_an_item(db_session):
    """Quy tắc chung: chỉ thêm khi tên đích có trong bảng và tên nguồn không phải một mục riêng."""
    names_ = await _real_names(db_session)
    lowered = [ambiguity_key(n) for n in names_]
    for syn in SYNONYMS:
        target = ambiguity_key(syn.target).split()
        assert any(" ".join(target) in " ".join(accent_words(n)) for n in names_), syn
        if not syn.bidirectional:
            assert ambiguity_key(syn.source) not in lowered, syn
    assert "bí đỏ" not in lowered                             # điều kiện của "bí đỏ → bí ngô"


@pytest.mark.parametrize("query,expected", [
    ("đậu phộng", "Lạc hạt"), ("hạt mè", "Vừng (đen, trắng)"), ("bắp cải", "Cải bắp"),
    ("khóm", "Dứa ta"), ("trái thơm", "Dứa ta"), ("khổ qua", "Mướp đắng"), ("ngò rí", "Rau mùi"),
    ("cá lóc", "Cá quả"), ("dưa leo", "Dưa chuột"), ("bông cải trắng", "Súp lơ trắng"),
    ("nấm đông cô", "Nấm hương tươi"), ("khoai mì", "Củ sắn"), ("hột gà", "Trứng gà"), ("hột vịt", "Trứng vịt"),
    ("quýt", "Quít"), ("trái kiwi", "Quả kiwi"), ("bí đỏ", "Bí ngô"),
    ("thịt heo nạc", "Thịt lợn nạc"), ("đậu hũ", "Đậu phụ"), ("bánh mì", "Bánh mỳ"),
    ("dầu ô liu", "Dầu oliu"),
])
async def test_each_synonym_on_real_data(db_session, query, expected):
    await _real_names(db_session)
    matches = await search_foods(db_session, query, limit=10)
    got = [m.food.name_vi for m in matches]
    assert expected in got, got
    # Có thể đã khớp trực tiếp (vd. "bắp cải" ~ "Cải bắp": tìm không phụ thuộc thứ tự từ)
    via = [m for m in matches if m.matched_via]
    for m in via:                                                     # không kéo mục không liên quan
        target = next(s for s in SYNONYMS if m.matched_via in (f"{s.source} → {s.target}", f"{s.target} → {s.source}"))
        need = ambiguity_key(target.target if m.matched_via.endswith(target.target) else target.source).split()
        assert set(need) <= set(accent_words(m.food.name_vi)), (m.food.name_vi, m.matched_via)


@pytest.mark.parametrize("term", ["bắp", "mè", "thơm", "mãng cầu", "táo", "hồng", "dưa"])
async def test_new_ambiguous_terms_on_real_data(db_session, term):
    await _real_names(db_session)
    with pytest.raises(AmbiguousFoodQuery) as exc:
        await search_foods(db_session, term)
    for meaning, cfg in zip(exc.value.meanings, AMBIGUOUS[term]):
        assert [(f.source.code, f.source_ref) for f in meaning.foods] == list(cfg.refs)   # mọi mục đều có


# ── Từ đồng nghĩa ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("query,expected_name,via", [
    ("thịt heo nạc", "Thịt lợn nạc", "heo → lợn"),
    ("đậu hũ", "Đậu phụ", "đậu hũ → đậu phụ"),
    ("bánh mì", "Bánh mỳ", "bánh mì → bánh mỳ"),
    ("dầu ô liu", "Dầu oliu", "ô liu → oliu"),
])
async def test_synonyms_find_source_name(foods_session, query, expected_name, via):
    await seed(foods_session, foods=ALIAS_FOODS)
    first = (await search_foods(foods_session, query))[0]
    assert first.food.name_vi == expected_name                  # tên gốc trong nguồn
    assert first.matched_via == via and first.level == MATCH_EXACT and first.is_exact


async def test_direct_match_is_not_overridden_by_synonym(foods_session):
    await seed(foods_session, foods=ALIAS_FOODS)
    got = await names(foods_session, "bột mì")
    assert got[0] == ("Bột mì", None)                           # khớp trực tiếp đứng đầu, không matched_via
    assert ("Bột mì", "mì → mỳ") not in got

    got = await names(foods_session, "thịt lợn nạc")
    assert got[0] == ("Thịt lợn nạc", None)


async def test_bidirectional_variants_do_not_pull_unrelated_items(foods_session):
    await seed(foods_session, foods=ALIAS_FOODS)
    via_mi = [(n, v) for n, v in await names(foods_session, "mì") if v]
    assert sorted(via_mi) == [("Bánh mỳ", "mì → mỳ"), ("Mỳ sợi", "mì → mỳ")]
    via_my = [(n, v) for n, v in await names(foods_session, "mỳ") if v]
    assert via_my == [("Bột mì", "mỳ → mì")]                     # không kéo "Mít dai"

    olive = await names(foods_session, "ô liu")
    assert olive == [("Dầu oliu", "ô liu → oliu")]              # không kéo "Ốc đá"
    assert await names(foods_session, "oliu") == [("Dầu oliu", None)]


# ── Từ mơ hồ ─────────────────────────────────────────────────────────────────
async def test_bo_requires_clarification_without_any_numbers(foods_session):
    await seed(foods_session, foods=ALIAS_FOODS)
    with pytest.raises(AmbiguousFoodQuery) as exc:
        await search_foods(foods_session, "bơ")
    meanings = exc.value.meanings
    assert [m.label for m in meanings] == ["quả bơ", "bơ động vật (butter)"]
    assert [f.name_vi for f in meanings[0].foods] == ["Quả bơ vỏ xanh", "Quả bơ vỏ tím"]
    assert [f.name_vi for f in meanings[1].foods] == ["Bơ"]     # mục trùng đúng tên KHÔNG được coi là đúng nghĩa


async def test_unaccented_bo_includes_beef_search(foods_session):
    await seed(foods_session, foods=ALIAS_FOODS)
    with pytest.raises(AmbiguousFoodQuery) as exc:
        await search_foods(foods_session, "bo")
    assert exc.value.meanings[2].label == "thịt bò" and exc.value.meanings[2].search == "thịt bò"
    assert exc.value.meanings[2].foods == []


@pytest.mark.parametrize("query,names_expected", [
    ("tôm", ["Tôm biển", "Tôm đồng", "Tôm khô"]),
    ("chuối", ["Chuối tiêu", "Chuối tây", "Chuối xanh", "Chuối khô", "Chuối nước đường"]),
])
async def test_terms_without_generic_item_list_kinds(foods_session, query, names_expected):
    await seed(foods_session, foods=ALIAS_FOODS)
    with pytest.raises(AmbiguousFoodQuery) as exc:
        await search_foods(foods_session, query)
    assert [f.name_vi for m in exc.value.meanings for f in m.foods] == names_expected


async def test_specific_names_are_not_ambiguous(foods_session):
    await seed(foods_session, foods=ALIAS_FOODS)
    exact = (await search_foods(foods_session, "quả bơ vỏ xanh"))[0]
    assert exact.food.name_vi == "Quả bơ vỏ xanh" and exact.is_exact
    assert (await search_foods(foods_session, "tôm biển"))[0].food.name_vi == "Tôm biển"


async def test_accent_match_ranks_first(foods_session):
    await seed(foods_session, foods=ALIAS_FOODS)
    got = [n for n, _ in await names(foods_session, "bò")]
    assert got[0] == "Thịt bò loại I" and got.index("Thịt bò loại I") < got.index("Dưa bở")
    got = [n for n, _ in await names(foods_session, "thịt bò")]
    assert got[0] == "Thịt bò loại I" and got[-1] == "Thịt bồ câu ra ràng"


# ── Món đã nấu, từ chỉ màu ───────────────────────────────────────────────────
@pytest.mark.parametrize("query,names_expected", [
    ("xôi", ["Gạo nếp cái", "Gạo nếp máy (Loại thường)"]), ("xôi trắng", ["Gạo nếp cái", "Gạo nếp máy (Loại thường)"]),
    ("cháo", ["Gạo tẻ máy", "Gạo tẻ giã"]),
])
async def test_cooked_dish_returns_raw_ingredients(foods_session, query, names_expected):
    await seed(foods_session, foods=ALIAS_FOODS)
    with pytest.raises(RawOnlyFoodQuery) as exc:
        await search_foods(foods_session, query)
    assert [f.name_vi for f in exc.value.foods] == names_expected


async def test_color_words_do_not_drive_suggestions(foods_session):
    await seed(foods_session, foods=ALIAS_FOODS)
    assert await search_foods(foods_session, "zqmon trắng") == []     # không kéo "Củ cải trắng"...
    got = [m.food.name_vi for m in await search_foods(foods_session, "trắng")]
    assert "Củ cải trắng" in got                                      # chỉ có từ màu: vẫn tìm bình thường


async def test_synonym_requires_accented_target_word(foods_session):
    await seed(foods_session, foods=ALIAS_FOODS)
    got = await names(foods_session, "khoai mì")
    assert ("Sắn khô", "khoai mì → sắn") in got
    assert all(n != "Thịt chó sấn" for n, _ in got)


# ── Trạng thái và backfill ───────────────────────────────────────────────────
async def test_ingest_sets_preparation_and_keeps_manual_value(foods_session):
    await seed(foods_session, foods=ALIAS_FOODS)
    row = lambda code: foods_session.execute(select(Food).where(Food.code == code))  # noqa: E731
    tofu = (await row(3025)).scalar_one()
    assert (tofu.preparation, tofu.preparation_source) == (FoodPreparation.RAW, "auto")
    pho = (await row(1013)).scalar_one()
    assert pho.preparation is FoodPreparation.UNKNOWN               # tên không ghi rõ → không đoán
    rice = (await row(1004)).scalar_one()
    assert (rice.preparation, rice.preparation_source) == (FoodPreparation.RAW, "manual")   # override

    await foods_session.execute(text("UPDATE foods SET preparation='cooked', preparation_source='manual' WHERE code=1013"))
    await seed(foods_session, foods=ALIAS_FOODS)                    # nạp lại
    foods_session.expire_all()
    pho = (await row(1013)).scalar_one()
    assert (pho.preparation, pho.preparation_source) == (FoodPreparation.COOKED, "manual")


async def test_backfill_updates_only_unknown_or_auto_and_never_manual(foods_session):
    await seed(foods_session, foods=ALIAS_FOODS)
    await foods_session.execute(text(
        "UPDATE foods SET preparation='unknown', preparation_source=NULL"))          # như ngay sau migration
    await foods_session.execute(text(
        "UPDATE foods SET preparation='cooked', preparation_source='manual' WHERE code=3025"))
    await foods_session.execute(text(
        "UPDATE foods SET preparation='raw', preparation_source='auto' WHERE code=8053"))  # auto cũ, sai

    plan = await plan_preparation_backfill(foods_session)
    assert [f.code for f in plan.manual] == [3025]
    override_codes = {f.code for f in plan.overrides}
    updated = await apply_preparation_backfill(foods_session, plan)
    assert updated == len(ALIAS_FOODS) - 1
    foods_session.expire_all()
    rows = dict((await foods_session.execute(select(Food.code, Food.preparation))).all())
    assert rows[3025] is FoodPreparation.COOKED                     # chỉnh tay giữ nguyên
    assert rows[8053] is FoodPreparation.DRIED                      # auto cũ được tính lại
    assert rows[1004] is FoodPreparation.RAW                        # override đã duyệt
    assert rows[1013] is FoodPreparation.UNKNOWN
    sources = dict((await foods_session.execute(select(Food.code, Food.preparation_source))).all())
    assert sources[1004] == "manual" and sources[1013] == "auto"
    assert override_codes == {1001, 1002, 1003, 1004}                 # các mã override có trong ALIAS_FOODS

    # Chạy lại: không đổi gì
    assert await apply_preparation_backfill(foods_session, await plan_preparation_backfill(foods_session)) == 0


async def test_backfill_does_not_touch_meal_logs(foods_session):
    await seed(foods_session, foods=ALIAS_FOODS)
    user = User(email=f"prep_{uuid.uuid4().hex[:8]}@fitai.vn", hashed_password=get_password_hash("x"))
    foods_session.add(user)
    await foods_session.flush()
    tofu = (await foods_session.execute(select(Food).where(Food.code == 3025))).scalar_one()
    foods_session.add(MealLog(user_id=user.id, food_id=tofu.id, eaten_on=date(2026, 10, 31),
                              meal_type=MealType.TRUA, grams=150, energy_kcal=142.5))
    await foods_session.flush()
    snapshot = lambda: foods_session.execute(text(  # noqa: E731
        "SELECT md5(string_agg(t::text, '|' ORDER BY id)) FROM meal_logs t"))
    before = (await snapshot()).scalar_one()
    await foods_session.execute(text("UPDATE foods SET preparation='unknown', preparation_source=NULL"))
    await apply_preparation_backfill(foods_session, await plan_preparation_backfill(foods_session))
    assert (await snapshot()).scalar_one() == before


# ── Override chỉnh tay đã duyệt ──────────────────────────────────────────────
def test_overrides_are_exactly_the_approved_list():
    assert {k: o.value.value for k, o in PREPARATION_OVERRIDES.items()} == {
        ("VN2007", "1001"): "raw", ("VN2007", "1002"): "raw", ("VN2007", "1003"): "raw",
        ("VN2007", "1004"): "raw", ("VN2007", "1005"): "raw",
        ("VN2007", "3031"): "unknown", ("VN2007", "1021"): "unknown", ("VN2007", "8056"): "unknown",
        ("VN2007", "11007"): "unknown",
        ("USDA_SR_LEGACY_2018", "173904"): "dried",
    }
    assert all(o.reason for o in PREPARATION_OVERRIDES.values())


async def test_override_codes_exist_in_real_foods_table(db_session):
    await _real_names(db_session)
    rows = {(c, ref): name for c, ref, name in (await db_session.execute(
        select(FoodSource.code, Food.source_ref, Food.name_vi).join(FoodSource, FoodSource.id == Food.source_id)
    )).all()}
    for key, o in PREPARATION_OVERRIDES.items():
        if key[0] == USDA_SR and not any(k[0] == USDA_SR for k in rows):
            continue                                         # chưa nạp USDA trên DB này
        assert rows.get(key) == o.name, key


async def test_override_beats_keyword_rule_on_ingest(foods_session):
    """8056 'Bánh phồng tôm sống' khớp 'sống' nhưng override giữ unknown (manual)."""
    await seed(foods_session, foods=ALIAS_FOODS + [food(8056, "Bánh phồng tôm sống", 444, "Shrimp paste")])
    row = (await foods_session.execute(select(Food).where(Food.code == 8056))).scalar_one()
    assert (row.preparation, row.preparation_source) == (FoodPreparation.UNKNOWN, "manual")
