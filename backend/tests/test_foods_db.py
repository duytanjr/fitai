"""Tests bảng foods trên PostgreSQL THẬT (transaction tự rollback sau mỗi test).

Nếu không kết nối được Postgres hoặc bảng foods chưa được tạo (chưa chạy migration),
các test này được SKIP kèm lý do.
"""
import logging
import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from core.config import settings
from core.security import get_password_hash
from models.chat import ChatMessage, ChatSession
from models.food import Food
from models.profile import UserProfile
from models.user import User
from services.foods import lookup as lookup_module
from services.foods.ingest import analyse, load_foods
from services.foods.lookup import (
    MAX_QUERY_LENGTH,
    SUGGESTION_LIMIT,
    FoodLookupError,
    FoodQueryError,
    nutrient_line,
    scale,
    search_foods,
)
from services.foods.parser import FoodRecord, ParseResult


@pytest.fixture
async def foods_session():
    """Phiên DB trong transaction rollback; bảng foods được làm rỗng TRONG transaction."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
    try:
        conn = await engine.connect()
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"Không kết nối được PostgreSQL ({type(exc).__name__}) — bỏ qua test bảng foods")
    trans = await conn.begin()
    session = AsyncSession(bind=conn, expire_on_commit=False)
    try:
        await session.execute(text("SELECT 1 FROM foods LIMIT 1"))
    except Exception as exc:  # noqa: BLE001
        await session.close()
        await trans.rollback()
        await conn.close()
        await engine.dispose()
        pytest.skip(f"Bảng foods chưa có ({type(exc).__name__}) — hãy chạy alembic upgrade head")
    await session.execute(text("DELETE FROM foods"))   # chỉ trong transaction, sẽ rollback
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await conn.close()
        await engine.dispose()


def make_food(code: int, name: str, page: int, **values) -> FoodRecord:
    base = dict(water_g=60.0, energy_kcal=140.0, protein_g=3.0, fat_g=0.5, carb_g=31.0, fiber_g=0.5, ash_g=0.4)
    base.update(values)
    return FoodRecord(
        stt=code % 1000 + (code // 1000) * 100, code=code, name_vi=name, name_en=None,
        group_code=code // 1000, group_name=f"Nhóm {code // 1000}", refuse_pct=0.0, source_page=page, **base,
    )


FIXTURE_FOODS = [
    make_food(1013, "Bánh phở", 26, water_g=64.3, energy_kcal=143.0, protein_g=3.2, fat_g=0.4, carb_g=31.7,
              fiber_g=0.0, ash_g=0.4),
    make_food(1004, "Gạo tẻ máy", 17, water_g=14.0, energy_kcal=344.0, protein_g=7.9, fat_g=1.0, carb_g=75.9,
              fiber_g=0.4, ash_g=0.8),
    make_food(1020, "Bún", 33, fat_g=None, energy_kcal=110.0, protein_g=1.7, carb_g=25.7),
    make_food(7032, "Thịt gà ta", 317, protein_g=20.3, fat_g=13.1, carb_g=0.0, energy_kcal=199.0),
    make_food(7020, "Gan gà", 344, protein_g=18.2, fat_g=3.4, carb_g=2.0),
    make_food(4100, "Men bia khô", 221, protein_g=40.0),
    make_food(1001, "Gạo nếp cái", 14),
]


async def seed(session: AsyncSession, foods=FIXTURE_FOODS, reset=False):
    stats, rows = analyse(ParseResult(100, len(foods), list(foods), [], []))
    await load_foods(session, rows, stats, reset=reset)
    await session.flush()
    return stats


async def count_foods(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(Food))).scalar_one()


# ── Nạp ──────────────────────────────────────────────────────────────────────
async def test_load_twice_does_not_duplicate(foods_session):
    first = await seed(foods_session)
    assert (first.inserted, first.updated) == (len(FIXTURE_FOODS), 0)
    second = await seed(foods_session)
    assert (second.inserted, second.updated) == (0, len(FIXTURE_FOODS))
    assert await count_foods(foods_session) == len(FIXTURE_FOODS)

    bun = (await foods_session.execute(select(Food).where(Food.code == 1020))).scalar_one()
    assert bun.fat_g is None                       # "-" lưu NULL, không phải 0
    assert bun.name_search == "bun"
    assert "atwater_thieu_so_lieu" in bun.quality_flags


async def test_reload_removes_codes_no_longer_present(foods_session):
    await seed(foods_session)
    stats = await seed(foods_session, foods=FIXTURE_FOODS[:3])
    assert stats.deleted_stale == len(FIXTURE_FOODS) - 3
    assert await count_foods(foods_session) == 3


async def test_reset_reloads_cleanly(foods_session):
    await seed(foods_session)
    foods_session.add(Food(code=99001, stt=99001, name_vi="Rác", name_search="rac", group_code=99,
                           group_name="x", source_page=1))
    await foods_session.flush()
    stats = await seed(foods_session, reset=True)
    assert stats.reset_deleted == len(FIXTURE_FOODS) + 1
    assert stats.inserted == len(FIXTURE_FOODS)
    codes = set((await foods_session.execute(select(Food.code))).scalars())
    assert codes == {f.code for f in FIXTURE_FOODS}


async def test_reset_does_not_touch_other_tables(foods_session):
    user = User(email=f"foods_reset_{uuid.uuid4().hex[:8]}@fitai.vn", hashed_password=get_password_hash("x"))
    foods_session.add(user)
    await foods_session.flush()
    session_id = uuid.uuid4()
    foods_session.add_all([
        UserProfile(user_id=user.id, age=30),
        ChatSession(id=session_id, user_id=user.id, title="t"),
        ChatMessage(session_id=session_id, role="user", content="xin chào"),
    ])
    await foods_session.flush()

    async def counts():
        return [
            (await foods_session.execute(select(func.count()).select_from(m))).scalar_one()
            for m in (User, UserProfile, ChatSession, ChatMessage)
        ]

    before = await counts()
    await seed(foods_session, reset=True)
    await seed(foods_session, reset=True)
    assert await counts() == before
    assert await count_foods(foods_session) == len(FIXTURE_FOODS)


# ── Tra cứu ──────────────────────────────────────────────────────────────────
async def test_lookup_without_diacritics(foods_session):
    await seed(foods_session)
    matches = await search_foods(foods_session, "pho")
    assert [m.food.name_vi for m in matches] == ["Bánh phở"]

    matches = await search_foods(foods_session, "ga")
    names = [m.food.name_vi for m in matches]
    assert names[:2] == ["Gan gà", "Thịt gà ta"]          # khớp nguyên từ "gà" xếp trước "gạo"
    assert set(names[2:]) <= {"Gạo tẻ máy", "Gạo nếp cái"}


async def test_lookup_exact_and_partial(foods_session):
    await seed(foods_session)
    exact = await search_foods(foods_session, "Gạo tẻ máy")
    assert exact[0].food.name_vi == "Gạo tẻ máy" and exact[0].is_exact
    pho = await search_foods(foods_session, "banh pho")
    assert pho[0].food.name_vi == "Bánh phở" and pho[0].is_exact and not pho[0].is_suggestion

    partial = await search_foods(foods_session, "thi ga")
    assert partial[0].food.name_vi == "Thịt gà ta" and not partial[0].is_exact

    beer = await search_foods(foods_session, "bia")
    assert [m.food.name_vi for m in beer] == ["Men bia khô"]
    assert not beer[0].is_exact                            # không phải "bia"


async def test_lookup_no_result(foods_session):
    await seed(foods_session)
    assert await search_foods(foods_session, "pizza") == []
    assert await search_foods(foods_session, "xyzxyz") == []
    assert await search_foods(foods_session, "xyz abc") == []      # thử từng từ cũng không có gì


async def test_no_full_match_returns_flagged_suggestions(foods_session):
    await seed(foods_session)
    matches = await search_foods(foods_session, "ức gà")           # không mục nào có từ "uc"
    names = [m.food.name_vi for m in matches]
    assert names[:2] == ["Gan gà", "Thịt gà ta"]
    assert all(m.is_suggestion and not m.is_exact for m in matches)

    with_number = await search_foods(foods_session, "100 g ức gà")   # bỏ "100", "g" khi gợi ý
    assert [m.food.name_vi for m in with_number] == names


async def test_suggestions_are_capped(foods_session):
    many = [make_food(2000 + i, f"Gai {i}", 50 + i) for i in range(20)]
    await seed(foods_session, foods=FIXTURE_FOODS + many)
    matches = await search_foods(foods_session, "uc ga")
    assert len(matches) == SUGGESTION_LIMIT
    assert [m.food.name_vi for m in matches[:2]] == ["Gan gà", "Thịt gà ta"]


async def test_same_level_prefers_keyword_earlier_in_name(foods_session):
    foods = FIXTURE_FOODS + [
        make_food(5054, "Vú sữa", 284),
        make_food(10001, "Sữa bò tươi", 463),
        make_food(12023, "Kẹo sữa", 519),
    ]
    await seed(foods_session, foods=foods)
    names = [m.food.name_vi for m in await search_foods(foods_session, "sua")]
    assert names[0] == "Sữa bò tươi"                                 # "sữa" đứng đầu tên
    assert set(names[1:3]) == {"Vú sữa", "Kẹo sữa"}                  # cùng vị trí → tên ngắn trước


async def test_lookup_candidates_ranked_before_cut(foods_session):
    """SQL lấy tới 50 ứng viên rồi mới xếp hạng; mục khớp nguyên từ không bị cắt."""
    many = [make_food(2000 + i, f"Gai {i}", 50 + i) for i in range(60)]   # 'gai' cũng bắt đầu bằng 'ga'
    await seed(foods_session, foods=FIXTURE_FOODS + many)
    matches = await search_foods(foods_session, "ga")
    assert len(matches) == 5
    assert [m.food.name_vi for m in matches[:2]] == ["Gan gà", "Thịt gà ta"]


async def test_null_is_not_zero_and_grams_scaling(foods_session):
    await seed(foods_session)
    bun = (await search_foods(foods_session, "bun"))[0].food
    assert bun.fat_g is None
    assert scale(bun.fat_g, 200) is None
    line = nutrient_line(bun, 200)
    assert "lipid KHÔNG CÓ SỐ LIỆU" in line
    assert "lipid 0" not in line

    pho = (await search_foods(foods_session, "banh pho"))[0].food
    assert "glucid 63.4 g" in nutrient_line(pho, 200)       # 31.7 × 200/100
    assert "năng lượng 286 kcal" in nutrient_line(pho, 200)


@pytest.mark.parametrize("query", [
    "'; DROP TABLE foods; --",
    "gà%_\\' OR 1=1",
    "phở\x00",
    "SELECT * FROM users",
])
async def test_special_characters_do_not_break_query(foods_session, query):
    await seed(foods_session)
    await search_foods(foods_session, query)              # không lỗi
    assert await count_foods(foods_session) == len(FIXTURE_FOODS)


@pytest.mark.parametrize("query", ["", "   ", "%%%", "x" * (MAX_QUERY_LENGTH + 1)])
async def test_invalid_query_rejected(foods_session, query):
    with pytest.raises(FoodQueryError):
        await search_foods(foods_session, query)


async def test_app_engine_does_not_log_query_parameters(caplog):
    """Engine của app ẩn tham số SQL: từ khoá người dùng không xuất hiện trong log."""
    from core.database import AsyncSessionLocal, engine

    assert engine.sync_engine.hide_parameters is True
    caplog.set_level(logging.INFO, logger="sqlalchemy.engine")   # như khi bật SQL_ECHO
    try:
        async with AsyncSessionLocal() as session:
            await search_foods(session, "zqmarker phở")
    except FoodLookupError:
        pytest.skip("Bảng foods chưa có — hãy chạy alembic upgrade head")
    except OSError as exc:
        pytest.skip(f"Không kết nối được PostgreSQL ({type(exc).__name__})")
    finally:
        await engine.dispose()
    assert "FROM foods" in caplog.text                            # câu SQL đã được ghi
    assert "zqmarker" not in caplog.text and "pho" not in caplog.text.split("FROM foods", 1)[1]


async def test_database_error_is_wrapped_and_session_stays_usable(foods_session, monkeypatch):
    await seed(foods_session)
    monkeypatch.setattr(lookup_module, "CANDIDATE_LIMIT", -1)   # Postgres: LIMIT âm → lỗi thật
    with pytest.raises(FoodLookupError):
        await search_foods(foods_session, "pho")
    # SAVEPOINT: transaction ngoài vẫn dùng được (lượt chat vẫn lưu được tin nhắn)
    assert (await foods_session.execute(text("SELECT 1"))).scalar_one() == 1
    assert await count_foods(foods_session) == len(FIXTURE_FOODS)
