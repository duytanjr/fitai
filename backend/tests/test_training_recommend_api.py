"""Tests API /training/recommendation và hai công cụ agent recommend_program, get_training_summary (lát 9d).

Postgres thật trong transaction rollback; chương trình nạp từ CSV trong tmp_path (link giả chỉ trong test).
Không gọi Gemini: công cụ chạy trực tiếp qua build_tools, agent dùng FakeChatModel.
"""
import json
import logging

import pytest

from unittest.mock import patch

from langchain_core.messages import AIMessage

from services.ai_agents.fitness_advisor import (
    TRAINING_UNAVAILABLE_CODE, AgentToolContext, build_system_prompt, build_tools, fitness_agent,
)
from services.chat_service import ChatService
from services.training.recommend import NOTE_MISSING_INFO, REASON_LOW_BMI_WEIGHT_LOSS
from services.training.seed import apply_plan, load_dir
from tests.fakes import FakeChatModel, tool_call
from tests.test_admin_api import register
from tests.test_meals_api import client, require_postgres  # noqa: F401
from tests.test_training_api import empty_training_tables
from tests.test_training_seed import ID_A, ID_B, item, program, rest, write

URL = "/api/v1/training/recommendation"
BEG, MID = "zq-nguoi-moi", "zq-toan-than"


@pytest.fixture
async def programs(client, db_session, tmp_path):
    await empty_training_tables(db_session)
    progs = [program(slug=BEG, title="Zq người mới", days="2"),
             program(slug=MID, title="Zq toàn thân", level="intermediate", days="2")]
    rows = [item(1, 1, ID_A, slug=BEG, duration="10"), rest(2, slug=BEG),
            item(1, 1, ID_B, slug=MID, duration="20"), rest(2, slug=MID)]
    plan = load_dir(write(tmp_path, progs, rows))
    assert plan.ok, plan.errors
    await apply_plan(db_session, plan)


async def user_with_profile(client, tag: str, **profile) -> dict:
    _, headers = await register(client, tag)
    if profile:
        res = await client.put("/api/v1/profile", headers=headers, json=profile)
        assert res.status_code == 200, res.text
    return headers


FULL = {"age": 30, "gender": "female", "height_cm": 170, "weight_kg": 65, "activity_level": "moderate",
        "fitness_goal": "weight_loss"}


async def test_requires_login(client, programs):
    assert (await client.get(URL)).status_code == 401


@pytest.mark.parametrize("value", ["sometimes", "REGULAR", "1", ""])
async def test_bad_experience_422(client, programs, value):
    headers = await user_with_profile(client, "rec_bad", **FULL)
    assert (await client.get(f"{URL}?experience={value}", headers=headers)).status_code == 422


async def test_reads_own_profile(client, programs):
    moderate = await user_with_profile(client, "rec_mod", **FULL)
    light = await user_with_profile(client, "rec_light", **{**FULL, "activity_level": "light"})
    a = (await client.get(URL, headers=moderate)).json()
    b = (await client.get(URL, headers=light)).json()
    assert a["primary"] == {"slug": MID, "title": "Zq toàn thân", "duration_days": 2, "level": "intermediate",
                            "goal_tag": "weight_loss"}
    assert a["alternative"]["slug"] == BEG and a["reason"].endswith("mức vận động của bạn là vừa.")
    assert b["primary"]["slug"] == BEG and b["alternative"]["slug"] == MID
    assert b["reason_code"] == "nen_bat_dau_nhe"


async def test_experience_param_and_profile_not_modified(client, programs):
    headers = await user_with_profile(client, "rec_exp", **{**FULL, "activity_level": "light"})
    data = (await client.get(f"{URL}?experience=regular", headers=headers)).json()
    assert data["primary"]["slug"] == MID and data["reason_code"] == "da_tap_deu" and data["experience"] == "regular"
    profile = (await client.get("/api/v1/profile", headers=headers)).json()
    assert profile["activity_level"] == "light"


async def test_empty_profile_is_missing_info(client, programs):
    headers = await user_with_profile(client, "rec_empty")
    data = (await client.get(URL, headers=headers)).json()
    assert data["primary"]["slug"] == BEG and data["reason_code"] == "thieu_thong_tin"
    assert NOTE_MISSING_INFO in data["notes"]


async def test_no_profile_row_is_missing_info(client, db_session, programs):
    from sqlalchemy import text
    email, headers = await register(client, "rec_noprof")
    await db_session.execute(text("DELETE FROM user_profiles WHERE user_id = (SELECT id FROM users "
                                  "WHERE email = :e)"), {"e": email})
    data = (await client.get(URL, headers=headers)).json()
    assert data["reason_code"] == "thieu_thong_tin"


async def test_low_bmi_weight_loss_null_primary(client, programs):
    headers = await user_with_profile(client, "rec_low", **{**FULL, "weight_kg": 50})
    for q in ("", "?experience=regular"):
        data = (await client.get(URL + q, headers=headers)).json()
        assert data["primary"] is None and data["alternative"] is None
        assert data["reason"] == REASON_LOW_BMI_WEIGHT_LOSS


async def test_no_published_programs(client, db_session):
    await empty_training_tables(db_session)
    headers = await user_with_profile(client, "rec_none", **FULL)
    data = (await client.get(URL, headers=headers)).json()
    assert data["primary"] is None and data["reason_code"] == "chua_co_chuong_trinh"


# ── Công cụ agent ────────────────────────────────────────────────────────────

def tools_of(ctx) -> dict:
    return {t.name: t for t in build_tools(ctx)}


def test_seven_tools_no_user_id_parameter():
    tools = tools_of(AgentToolContext())
    assert set(tools) == {"search_knowledge", "calc_body_metrics", "lookup_food", "get_daily_summary",
                          "get_progress_summary", "recommend_program", "get_training_summary"}
    assert set(tools["recommend_program"].args) == {"experience"}
    assert set(tools["get_training_summary"].args) == set()
    for t in tools.values():
        assert "user_id" not in t.args


async def test_recommend_tool_rejects_bad_experience():
    called = []

    async def loader(experience):
        called.append(experience)
        return {}

    tool = tools_of(AgentToolContext(load_recommendation=loader))["recommend_program"]
    out = await tool.ainvoke({"experience": "da tap"})
    assert out.startswith("Lỗi tham số") and called == []
    await tool.ainvoke({"experience": "new"})
    await tool.ainvoke({})
    assert called == ["new", None]


async def test_tools_db_error_friendly(caplog):
    async def boom(*_):
        raise RuntimeError("connection refused password=secret")

    tools = tools_of(AgentToolContext(load_recommendation=boom, load_training_summary=boom))
    for name, args in (("recommend_program", {}), ("get_training_summary", {})):
        out = await tools[name].ainvoke(args)
        assert out.startswith(TRAINING_UNAVAILABLE_CODE) and "secret" not in out
    assert "secret" not in caplog.text


async def test_tools_use_current_user_via_chat_service(client, db_session, programs):
    """ChatService gắn user_id phía server: hai người dùng khác hồ sơ nhận kết quả khác nhau."""
    from sqlalchemy import select
    from models.user import User
    await user_with_profile(client, "rec_tool_a", **FULL)
    await user_with_profile(client, "rec_tool_b", **{**FULL, "activity_level": "sedentary"})
    users = (await db_session.scalars(select(User).where(User.email.like("admin8a_rec_tool_%"))
                                      .order_by(User.created_at))).all()
    service = ChatService(db_session)
    results = []
    for u in users:
        ctx = AgentToolContext(load_recommendation=lambda e, uid=u.id: service._load_recommendation(uid, e),
                               load_training_summary=lambda uid=u.id: service._load_training_summary(uid))
        tools = tools_of(ctx)
        results.append(json.loads(await tools["recommend_program"].ainvoke({})))
        summary = json.loads(await tools["get_training_summary"].ainvoke({}))
        assert summary["current_program"] is None and summary["this_week"]["completed_days"] is None
    assert [r["primary"]["slug"] for r in results] == [MID, BEG]


async def test_training_summary_tool_no_zero_when_missing(client, db_session, programs):
    from services.training.progress import training_summary_for_agent
    from sqlalchemy import select
    from models.user import User
    headers = await user_with_profile(client, "rec_sum", **FULL)
    uid = (await db_session.scalars(select(User.id).where(User.email.like("admin8a_rec_sum_%")))).one()
    empty = await training_summary_for_agent(db_session, uid)
    week = empty["this_week"]
    assert (week["completed_days"], week["active_dates"], week["total_minutes"], week["days_without_minutes"]) == \
        (None, None, None, None)
    assert empty["current_program"] is None and "chưa theo" in empty["current_program_note"]
    assert "không phải 0" in empty["this_week_note"]
    assert 0 not in [v for v in week.values() if not isinstance(v, str)]

    enrollment = (await client.post("/api/v1/training/enrollments", headers=headers,
                                    json={"program_slug": BEG})).json()
    await client.post(f"/api/v1/training/enrollments/{enrollment['id']}/days/1/complete", headers=headers)
    data = await training_summary_for_agent(db_session, uid)
    # BEG chỉ có 1 ngày tập → đánh dấu xong là completed, không còn chương trình đang theo
    assert data["current_program"] is None
    assert data["this_week"]["completed_days"] == 1 and data["this_week"]["total_minutes"] == 10
    assert "this_week_note" not in data and "tự đánh dấu" in data["minutes_note"]


async def test_agent_calls_training_tools_with_fake_llm():
    seen = []

    async def rec_loader(experience):
        seen.append(("rec", experience))
        return {"primary": None, "alternative": None, "reason_code": "chua_co_chuong_trinh",
                "reason": "hiện chưa có chương trình nào để gợi ý", "notes": [], "experience": experience}

    async def sum_loader():
        seen.append(("sum", None))
        return {"current_program": None, "this_week": {"completed_days": None}}

    fake = FakeChatModel(lambda messages, i, tc: (
        tool_call("recommend_program", {"experience": "regular"}) if i == 0 else
        tool_call("get_training_summary", {}) if i == 1 else AIMessage(content="ok")))
    ctx = AgentToolContext(load_recommendation=rec_loader, load_training_summary=sum_loader)
    with patch.object(fitness_agent, "llm", fake):
        reply = await fitness_agent.chat(history=[], user_message="Tôi nên tập chương trình nào?", tool_context=ctx)
    assert reply == "ok" and ctx.tool_calls == ["recommend_program", "get_training_summary"]
    assert "recommend_program" in fake.bound_tools and len(fake.bound_tools) == 7
    assert seen == [("rec", "regular"), ("sum", None)]


# ── System prompt ────────────────────────────────────────────────────────────

def test_system_prompt_training_rule():
    prompt = build_system_prompt(None)
    start = prompt.index("TẬP LUYỆN:")
    rule = prompt[start:prompt.index("NGUYÊN TẮC AN TOÀN Y TẾ:")]
    for phrase in ["PHẢI gọi recommend_program", "TỰ NÓI rõ", "không đoán", "PHẢI gọi get_training_summary",
                   "không tự bịa chương trình, bài tập, động tác hay số hiệp", "người dùng tự đánh dấu",
                   "không bao giờ nói là 0", "Không hứa kết quả giảm cân", "không nêu số kcal đã đốt",
                   "\"đã đạt\" hay \"chưa đạt\"", "chưa có hướng dẫn kỹ thuật riêng từng bài",
                   "hỏi huấn luyện viên", "bệnh nền", "gặp bác sĩ", TRAINING_UNAVAILABLE_CODE, "tuần lịch từ thứ Hai"]:
        assert phrase in rule, phrase
    # quy tắc cũ giữ nguyên, an toàn y tế vẫn ở cuối
    for old in ["16. TIẾN ĐỘ", "17. NGUỒN QUẢN TRỊ VIÊN NHẬP", "10. KHÔNG CÓ ĐÚNG MỤC THỰC PHẨM"]:
        assert old in prompt
    assert prompt.index("NGUYÊN TẮC AN TOÀN Y TẾ:") > start


async def test_no_profile_or_program_in_logs(client, programs, caplog):
    caplog.set_level(logging.DEBUG)
    headers = await user_with_profile(client, "rec_log", **FULL)
    await client.get(URL, headers=headers)
    assert "Zq toàn thân" not in caplog.text and "moderate" not in caplog.text


async def test_training_summary_tool_current_program(client, db_session, tmp_path):
    from services.training.progress import training_summary_for_agent
    from sqlalchemy import select
    from models.user import User
    await empty_training_tables(db_session)
    rows = [item(1, 1, ID_A, slug=BEG, duration="10"), rest(2, slug=BEG), item(3, 1, ID_B, slug=BEG, duration="")]
    await apply_plan(db_session, load_dir(write(tmp_path, [program(slug=BEG, title="Zq người mới")], rows)))
    headers = await user_with_profile(client, "rec_cur", **FULL)
    uid = (await db_session.scalars(select(User.id).where(User.email.like("admin8a_rec_cur_%")))).one()
    enrollment = (await client.post("/api/v1/training/enrollments", headers=headers,
                                    json={"program_slug": BEG})).json()
    await client.post(f"/api/v1/training/enrollments/{enrollment['id']}/days/3/complete", headers=headers)
    data = await training_summary_for_agent(db_session, uid)
    assert data["current_program"] == {"program_title": "Zq người mới", "training_days_done": 1,
                                       "training_days_total": 2, "next_day": 1, "available": True, "message": None}
    # ngày 3 thiếu thời lượng → có dữ liệu ngày nhưng tổng phút null (không phải 0)
    assert (data["this_week"]["completed_days"], data["this_week"]["total_minutes"],
            data["this_week"]["days_without_minutes"]) == (1, None, 1)
    assert "Chưa có dữ liệu thời lượng" in data["this_week_note"]
