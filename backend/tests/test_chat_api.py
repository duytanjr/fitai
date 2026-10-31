"""Tests cho API Chatbot (POST /chat, GET /chat/sessions, GET /chat/sessions/{id}/messages).

Mọi bài test đều mock mô hình AI (FitnessAdvisorAgent/Gemini), tuyệt đối không gọi API thật.
"""
import json
import uuid
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient

from services.ai_agents.fitness_advisor import ChatAgentException, build_system_prompt, build_tools
from models.chat import ChatMessage, ChatSession
from sqlalchemy import select

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
CHAT_URL = "/api/v1/chat"
SESSIONS_URL = "/api/v1/chat/sessions"


# ── Helpers ──────────────────────────────────────────────────────────────────
async def register_and_login(client: AsyncClient, suffix: str) -> tuple[str, str]:
    """Đăng ký + đăng nhập → trả (access_token, email)."""
    email = f"chatuser{suffix}@fitai.vn"
    password = "Password@123"
    await client.post(REGISTER_URL, json={"email": email, "password": password})
    res = await client.post(
        LOGIN_URL,
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return res.json()["access_token"], email


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Tests ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_chat_unauthenticated(async_client: AsyncClient):
    """1. Gọi các endpoint chat khi chưa đăng nhập → 401."""
    # POST /chat
    res = await async_client.post(CHAT_URL, json={"message": "Xin chào"})
    assert res.status_code == 401

    # GET /chat/sessions
    res = await async_client.get(SESSIONS_URL)
    assert res.status_code == 401

    # GET /chat/sessions/{id}/messages
    random_id = uuid.uuid4()
    res = await async_client.get(f"{SESSIONS_URL}/{random_id}/messages")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_chat_validation_empty_and_too_long(async_client: AsyncClient):
    """4. Tin nhắn rỗng hoặc chỉ có khoảng trắng, hoặc dài > 2000 ký tự → 422."""
    token, _ = await register_and_login(async_client, "_val")

    # Tin nhắn rỗng
    res = await async_client.post(
        CHAT_URL, json={"message": ""}, headers=auth_headers(token)
    )
    assert res.status_code == 422

    # Tin nhắn toàn khoảng trắng
    res = await async_client.post(
        CHAT_URL, json={"message": "    "}, headers=auth_headers(token)
    )
    assert res.status_code == 422

    # Tin nhắn quá 2000 ký tự
    long_msg = "a" * 2001
    res = await async_client.post(
        CHAT_URL, json={"message": long_msg}, headers=auth_headers(token)
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_chat_success_saves_both_messages(async_client: AsyncClient):
    """2. Chat thành công lưu đúng 2 tin nhắn (user và AI)."""
    token, _ = await register_and_login(async_client, "_succ")

    mock_reply = "Chào bạn! Tôi là FitAI. Hôm nay bạn muốn tập nhóm cơ nào?"
    with patch(
        "services.chat_service.fitness_agent.chat",
        new=AsyncMock(return_value=mock_reply),
    ):
        res = await async_client.post(
            CHAT_URL,
            json={"message": "Chào FitAI!"},
            headers=auth_headers(token),
        )

    assert res.status_code == 200
    data = res.json()
    assert "session_id" in data
    assert data["reply"] == mock_reply
    session_id = data["session_id"]

    # Kiểm tra lịch sử session qua API GET /chat/sessions/{id}/messages
    res_msgs = await async_client.get(
        f"{SESSIONS_URL}/{session_id}/messages",
        headers=auth_headers(token),
    )
    assert res_msgs.status_code == 200
    msgs = res_msgs.json()
    assert len(msgs) == 2

    # Tin nhắn user
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "Chào FitAI!"

    # Tin nhắn AI
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == mock_reply


@pytest.mark.asyncio
async def test_chat_cross_user_session_returns_404(async_client: AsyncClient):
    """3. Truy cập hoặc gửi tin vào session_id của user khác → 404."""
    token_a, _ = await register_and_login(async_client, "_userA")
    token_b, _ = await register_and_login(async_client, "_userB")

    # User A tạo 1 session
    with patch(
        "services.chat_service.fitness_agent.chat",
        new=AsyncMock(return_value="Phản hồi cho A"),
    ):
        res_a = await async_client.post(
            CHAT_URL,
            json={"message": "Tin nhắn của User A"},
            headers=auth_headers(token_a),
        )
    session_id_a = res_a.json()["session_id"]

    # User B cố gắng gửi tin vào session của User A → 404
    with patch(
        "services.chat_service.fitness_agent.chat",
        new=AsyncMock(return_value="Phản hồi hack"),
    ):
        res_b_send = await async_client.post(
            CHAT_URL,
            json={"message": "User B can thiệp", "session_id": session_id_a},
            headers=auth_headers(token_b),
        )
    assert res_b_send.status_code == 404

    # User B cố gắng xem tin nhắn của User A → 404
    res_b_get = await async_client.get(
        f"{SESSIONS_URL}/{session_id_a}/messages",
        headers=auth_headers(token_b),
    )
    assert res_b_get.status_code == 404


@pytest.mark.asyncio
async def test_chat_history_order_and_limit(async_client: AsyncClient):
    """5 & 7. Kiểm tra lịch sử đưa vào agent:

    - Đúng các tin TRƯỚC tin hiện tại
    - Tối đa 10 tin gần nhất
    - Đúng thứ tự thời gian (tăng dần)
    - Tin hiện tại KHÔNG bị lặp trong history
    """
    token, _ = await register_and_login(async_client, "_hist")

    # Tạo 1 session ban đầu
    with patch(
        "services.chat_service.fitness_agent.chat",
        new=AsyncMock(return_value="AI rep 1"),
    ):
        res = await async_client.post(
            CHAT_URL,
            json={"message": "Msg 1"},
            headers=auth_headers(token),
        )
    session_id = res.json()["session_id"]

    # Gửi liên tiếp thêm 6 lượt (mỗi lượt tạo 1 user + 1 ai message = 2 messages)
    # Tổng cộng trong DB sẽ có: 1 * 2 + 6 * 2 = 14 messages
    for i in range(2, 8):
        with patch(
            "services.chat_service.fitness_agent.chat",
            new=AsyncMock(return_value=f"AI rep {i}"),
        ):
            await async_client.post(
                CHAT_URL,
                json={"message": f"Msg {i}", "session_id": session_id},
                headers=auth_headers(token),
            )

    # Lượt thứ 8: Gửi "Msg 8", lúc này DB đang có 14 tin nhắn
    # Kiểm tra argument truyền vào mock agent.chat
    mock_chat = AsyncMock(return_value="AI rep 8")
    with patch("services.chat_service.fitness_agent.chat", new=mock_chat):
        await async_client.post(
            CHAT_URL,
            json={"message": "Msg 8", "session_id": session_id},
            headers=auth_headers(token),
        )

    assert mock_chat.called
    kwargs = mock_chat.call_args.kwargs
    passed_history = kwargs["history"]
    passed_user_message = kwargs["user_message"]

    # 1. user_message truyền vào đúng là Msg 8
    assert passed_user_message == "Msg 8"

    # 2. History tối đa 10 tin nhắn
    assert len(passed_history) == 10

    # 3. Tin nhắn Msg 8 không xuất hiện trong history
    assert not any(m["content"] == "Msg 8" for m in passed_history)

    # 4. Thứ tự lịch sử: tin nhắn cũ hơn đứng trước, mới hơn đứng sau
    # 10 tin gần nhất của 14 tin (từ Msg 1 đến AI rep 7) sẽ bắt đầu từ Msg 3 hoặc AI rep 2
    # và kết thúc bằng AI rep 7
    assert passed_history[-1]["content"] == "AI rep 7"
    assert passed_history[-1]["role"] == "assistant"
    assert passed_history[-2]["content"] == "Msg 7"
    assert passed_history[-2]["role"] == "user"


@pytest.mark.asyncio
async def test_chat_agent_failure_does_not_save_any_message(
    async_client: AsyncClient,
):
    """6. Khi Agent bị lỗi hoặc trả về rỗng:

    - Trả lỗi thân thiện (502 hoặc 503)
    - KHÔNG lưu tin nhắn user hay tin nhắn AI vào DB
    """
    token, _ = await register_and_login(async_client, "_fail")

    # Ca 6a: Agent raise lỗi quá tải / timeout
    mock_fail = AsyncMock(
        side_effect=ChatAgentException("Dịch vụ AI tạm thời bị gián đoạn.", status_code=503)
    )
    with patch("services.chat_service.fitness_agent.chat", new=mock_fail):
        res = await async_client.post(
            CHAT_URL,
            json={"message": "Tin nhắn lỗi"},
            headers=auth_headers(token),
        )
    assert res.status_code == 503
    assert "Dịch vụ AI tạm thời bị gián đoạn" in res.json()["detail"]

    # Kiểm tra danh sách session của user: phải hoàn toàn rỗng vì không lưu gì!
    res_sessions = await async_client.get(SESSIONS_URL, headers=auth_headers(token))
    assert res_sessions.status_code == 200
    assert len(res_sessions.json()) == 0

    # Ca 6b: Agent trả về rỗng (safety filter block)
    mock_empty = AsyncMock(
        side_effect=ChatAgentException(
            "Phản hồi từ AI bị rỗng hoặc bị chặn bởi bộ lọc an toàn.",
            status_code=502,
        )
    )
    with patch("services.chat_service.fitness_agent.chat", new=mock_empty):
        res_empty = await async_client.post(
            CHAT_URL,
            json={"message": "Câu hỏi nhạy cảm"},
            headers=auth_headers(token),
        )
    assert res_empty.status_code == 502
    assert "bị chặn bởi bộ lọc an toàn" in res_empty.json()["detail"]


@pytest.mark.asyncio
async def test_chat_with_profile_personalization_without_metric_numbers(
    async_client: AsyncClient,
):
    """7. System prompt cá nhân hóa:

    - Prompt chứa đúng tuổi, chiều cao, cân nặng, dị ứng — nhưng KHÔNG chứa con số chỉ số
      cơ thể (BMR/TDEE/calo mục tiêu): các con số này chỉ đến từ công cụ calc_body_metrics.
    - calc_body_metrics (gắn với user hiện tại) trả đúng 2104 kcal cho hồ sơ mẫu.
    """
    token, _ = await register_and_login(async_client, "_profile_ctx")

    # Cập nhật hồ sơ đầy đủ
    await async_client.put(
        "/api/v1/profile",
        json={
            "age": 22,
            "gender": "male",
            "height_cm": 180.0,
            "weight_kg": 78.0,
            "activity_level": "light",
            "fitness_goal": "weight_loss",
            "dietary_restrictions": "Dị ứng tôm cua",
        },
        headers=auth_headers(token),
    )

    mock_chat = AsyncMock(return_value="Kế hoạch giảm cân cho bạn...")
    with patch("services.chat_service.fitness_agent.chat", new=mock_chat):
        res = await async_client.post(
            CHAT_URL,
            json={"message": "Tôi nên ăn bao nhiêu calo?"},
            headers=auth_headers(token),
        )

    assert res.status_code == 200
    assert mock_chat.called
    profile_data = mock_chat.call_args.kwargs["profile_data"]
    assert profile_data is not None
    assert profile_data["age"] == 22
    assert profile_data["gender"] == "male"
    assert profile_data["height_cm"] == 180.0
    assert profile_data["weight_kg"] == 78.0
    assert "metrics" not in profile_data

    # Kiểm tra văn bản build_system_prompt
    prompt_text = build_system_prompt(profile_data)
    assert "22" in prompt_text
    assert "180.0 cm" in prompt_text
    assert "78.0 kg" in prompt_text
    assert "Dị ứng tôm cua" in prompt_text
    assert "TIẾNG VIỆT" in prompt_text
    assert "KHÔNG PHẢI là bác sĩ y khoa" in prompt_text
    assert "calc_body_metrics TRƯỚC KHI trả lời" in prompt_text

    # Công cụ calc_body_metrics của lượt chat này trả đúng 2104 kcal
    tool_context = mock_chat.call_args.kwargs["tool_context"]
    calc = {t.name: t for t in build_tools(tool_context)}["calc_body_metrics"]
    metrics = json.loads(await calc.ainvoke({}))
    assert metrics["is_complete"] is True
    assert metrics["target_calories"] == 2104

    # ...và không con số chỉ số nào nằm sẵn trong system prompt
    for value in (metrics["target_calories"], metrics["bmr"], metrics["tdee"]):
        assert str(value) not in prompt_text
    assert "kcal/ngày" not in prompt_text


@pytest.mark.asyncio
async def test_chat_with_incomplete_or_empty_profile(async_client: AsyncClient):
    """2. Hồ sơ chưa đủ hoặc trống: chat vẫn chạy bình thường, prompt ghi 'chưa có thông tin'."""
    token, _ = await register_and_login(async_client, "_empty_profile")

    mock_chat = AsyncMock(return_value="Chào bạn, tôi sẵn sàng tư vấn!")
    with patch("services.chat_service.fitness_agent.chat", new=mock_chat):
        res = await async_client.post(
            CHAT_URL,
            json={"message": "Cho tôi lời khuyên tập luyện"},
            headers=auth_headers(token),
        )

    assert res.status_code == 200
    assert mock_chat.called
    profile_data = mock_chat.call_args.kwargs["profile_data"]

    prompt_text = build_system_prompt(profile_data)
    assert "chưa có thông tin" in prompt_text
    assert "TIẾNG VIỆT" in prompt_text


# ── FR5: RAG, công cụ và nguồn trích dẫn (LLM + RAG đều là bản giả) ─────────────
from langchain_core.messages import AIMessage, ToolMessage  # noqa: E402

from services import rag_service  # noqa: E402
from services.ai_agents import fitness_advisor  # noqa: E402
from services.ai_agents.fitness_advisor import KNOWLEDGE_UNAVAILABLE_CODE, fitness_agent  # noqa: E402
from tests.fakes import FakeChatModel, FakeEmbedder, tool_call  # noqa: E402


def rag_doc(page: int, title: str = "WHO guidelines on physical activity and sedentary behaviour"):
    return {"text": "Adults should do at least 150–300 minutes of moderate-intensity activity.",
            "title": title, "authors_org": "WHO", "year": 2020, "page": page, "page_end": page,
            "is_table": False, "file": "who.pdf", "score": 0.74}


def search_then_answer(answer: str):
    def script(messages, i, tool_choice):
        if i == 0:
            return tool_call("search_knowledge", {"query": "physical activity adults"})
        return AIMessage(content=answer)
    return script


@pytest.mark.asyncio
async def test_chat_returns_and_persists_sources_after_reload(async_client: AsyncClient):
    """POST /chat trả sources (bỏ trùng tài liệu+trang); GET messages (F5) vẫn trả nguồn."""
    token, _ = await register_and_login(async_client, "_sources")
    answer = "Người lớn nên vận động 150–300 phút mỗi tuần (WHO, 2020, tr. PDF 12)."
    search = AsyncMock(return_value=[rag_doc(12), rag_doc(12), rag_doc(41)])

    with patch.object(fitness_agent, "llm", FakeChatModel(search_then_answer(answer))), \
         patch.object(fitness_advisor, "asearch_knowledge", search):
        res = await async_client.post(
            CHAT_URL, json={"message": "Người lớn nên tập bao nhiêu phút?"}, headers=auth_headers(token)
        )

    assert res.status_code == 200
    data = res.json()
    expected = [
        {"title": "WHO guidelines on physical activity and sedentary behaviour", "authors_org": "WHO", "year": 2020, "page": 12},
        {"title": "WHO guidelines on physical activity and sedentary behaviour", "authors_org": "WHO", "year": 2020, "page": 41},
    ]
    assert data["reply"] == answer
    assert data["sources"] == expected

    # Tải lại trang (F5): lịch sử lấy từ DB vẫn còn nguồn
    msgs = (await async_client.get(f"{SESSIONS_URL}/{data['session_id']}/messages", headers=auth_headers(token))).json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["sources"] == []
    assert msgs[1]["sources"] == expected


@pytest.mark.asyncio
async def test_chat_without_matching_documents_has_empty_sources(async_client: AsyncClient, db_session):
    token, _ = await register_and_login(async_client, "_nosources")
    with patch.object(fitness_agent, "llm", FakeChatModel(search_then_answer("Tôi chưa có tài liệu đủ tin cậy về vấn đề này."))), \
         patch.object(fitness_advisor, "asearch_knowledge", AsyncMock(return_value=[])):
        res = await async_client.post(CHAT_URL, json={"message": "Cách nấu phở?"}, headers=auth_headers(token))

    assert res.status_code == 200
    assert res.json()["sources"] == []
    session_id = uuid.UUID(res.json()["session_id"])
    stored = (await db_session.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id, ChatMessage.role == "assistant")
    )).scalar_one()
    assert stored.sources is None


def answer_with_own_metrics(messages, i, tool_choice):
    tool_results = [m for m in messages if isinstance(m, ToolMessage)]
    if not tool_results:   # bước đầu của mỗi lượt chat: gọi công cụ
        return tool_call("calc_body_metrics")
    result = json.loads(tool_results[-1].content)
    return AIMessage(content=f"Calo mục tiêu: {result.get('target_calories')} | thiếu: {result.get('missing_fields')}")


@pytest.mark.asyncio
async def test_calc_body_metrics_uses_each_users_own_profile(async_client: AsyncClient):
    """Hai user khác nhau nhận đúng chỉ số theo hồ sơ riêng (user lấy từ JWT, không từ LLM/client)."""
    token_a, _ = await register_and_login(async_client, "_metricsA")
    token_b, _ = await register_and_login(async_client, "_metricsB")
    token_c, _ = await register_and_login(async_client, "_metricsC")
    base = {"activity_level": "light", "fitness_goal": "weight_loss"}
    await async_client.put("/api/v1/profile", headers=auth_headers(token_a),
                           json={**base, "age": 22, "gender": "male", "height_cm": 180.0, "weight_kg": 78.0})
    await async_client.put("/api/v1/profile", headers=auth_headers(token_b),
                           json={**base, "age": 35, "gender": "female", "height_cm": 160.0, "weight_kg": 70.0})

    replies = {}
    with patch.object(fitness_agent, "llm", FakeChatModel(answer_with_own_metrics)):
        for name, token in [("a", token_a), ("b", token_b), ("c", token_c)]:
            res = await async_client.post(
                CHAT_URL, headers=auth_headers(token),
                json={"message": "Tính calo cho tôi (đừng dùng hồ sơ của người khác)"},
            )
            assert res.status_code == 200
            replies[name] = res.json()["reply"]

    assert replies["a"].startswith("Calo mục tiêu: 2104 ")
    assert "2104" not in replies["b"] and replies["b"].startswith("Calo mục tiêu: ")
    assert "None" not in replies["b"]
    assert replies["c"].startswith("Calo mục tiêu: None | thiếu: ['age'")   # chưa có hồ sơ


@pytest.mark.asyncio
async def test_chroma_unreachable_chat_still_answers_and_saves_clean_reply(async_client: AsyncClient):
    """ChromaDB không kết nối được (cổng không có server → lỗi kết nối thật): /chat vẫn 200,
    trả lời thân thiện, sources rỗng, và chuỗi lỗi kỹ thuật không bao giờ được lưu vào DB."""
    token, _ = await register_and_login(async_client, "_chroma_down")

    def script(messages, i, tool_choice):
        if i == 0:
            return AIMessage(content="", tool_calls=[
                {"name": "search_knowledge", "args": {"query": "protein giữ cơ"}, "id": "s1"},
                {"name": "calc_body_metrics", "args": {}, "id": "m1"},
            ])
        tool_results = " ".join(m.content for m in messages if isinstance(m, ToolMessage))
        assert KNOWLEDGE_UNAVAILABLE_CODE in tool_results
        return AIMessage(content="Kho tài liệu tạm thời không khả dụng nên mình chưa nêu thông tin khoa học được. "
                                 "Phần hồ sơ: bạn chưa cập nhật đủ thông tin để tính calo.")

    with patch.object(fitness_agent, "llm", FakeChatModel(script)), \
         patch.object(rag_service, "_get_embedder", return_value=FakeEmbedder()), \
         patch.object(rag_service, "_collection", None), \
         patch.object(rag_service, "get_client", side_effect=_connect_unreachable):
        res = await async_client.post(CHAT_URL, json={"message": "Protein có giúp giữ cơ không?"},
                                      headers=auth_headers(token))

    assert res.status_code == 200
    data = res.json()
    assert "kho tài liệu tạm thời không khả dụng" in data["reply"].lower()
    assert data["sources"] == []

    msgs = (await async_client.get(f"{SESSIONS_URL}/{data['session_id']}/messages", headers=auth_headers(token))).json()
    assert len(msgs) == 2
    saved = msgs[1]["content"]
    assert saved == data["reply"]
    for technical in (KNOWLEDGE_UNAVAILABLE_CODE, "KnowledgeSearchError", "KnowledgeStoreError", "Traceback", "127.0.0.1"):
        assert technical not in saved


async def _add_test_food(db_session):
    from models.food import Food

    db_session.add(Food(
        code=99901, stt=99901, name_vi="Bánh thử nghiệm FitAI", name_search="banh thu nghiem fitai",
        group_code=1, group_name="Ngũ cốc và sản phẩm chế biến", refuse_pct=0.0, source_page=999,
        water_g=60.0, energy_kcal=150.0, protein_g=4.0, fat_g=None, carb_g=33.0, fiber_g=0.5, ash_g=0.5,
    ))
    await db_session.flush()


def lookup_then_answer(messages, i, tool_choice):
    tool_results = [m for m in messages if isinstance(m, ToolMessage)]
    if not tool_results:
        return tool_call("lookup_food", {"query": "banh thu nghiem fitai", "grams": 200})
    return AIMessage(content="Kết quả: " + tool_results[-1].content.split("\n")[0][:60])


@pytest.mark.asyncio
async def test_chat_lookup_food_adds_food_source_and_persists(async_client: AsyncClient, db_session):
    """lookup_food tra bảng foods THẬT (Postgres) qua phiên DB của request; nguồn thực phẩm
    được trả về và lưu cùng tin nhắn AI."""
    await _add_test_food(db_session)
    token, _ = await register_and_login(async_client, "_food_src")
    fake = FakeChatModel(lookup_then_answer)
    with patch.object(fitness_agent, "llm", fake):
        res = await async_client.post(CHAT_URL, json={"message": "200 g bánh thử nghiệm?"}, headers=auth_headers(token))

    assert res.status_code == 200
    expected = [{"title": "Bảng thành phần thực phẩm Việt Nam", "authors_org": "Viện Dinh dưỡng", "year": 2007, "page": 999}]
    assert res.json()["sources"] == expected
    tool_text = [m for m in fake.calls[-1]["messages"] if isinstance(m, ToolMessage)][0].content
    assert "Theo 200 g phần ăn được (code đã tính)" in tool_text
    assert "glucid (không gồm xơ) 66 g" in tool_text and "lipid KHÔNG CÓ SỐ LIỆU" in tool_text

    msgs = (await async_client.get(f"{SESSIONS_URL}/{res.json()['session_id']}/messages", headers=auth_headers(token))).json()
    assert msgs[1]["sources"] == expected


@pytest.mark.asyncio
async def test_chat_food_database_error_still_answers_and_saves(async_client: AsyncClient, db_session, monkeypatch):
    """Lỗi SQL thật khi tra foods (trong SAVEPOINT): /chat vẫn 200 và vẫn lưu được tin nhắn."""
    from services.foods import lookup as lookup_module
    from services.ai_agents.fitness_advisor import FOOD_UNAVAILABLE_CODE

    token, _ = await register_and_login(async_client, "_food_dberr")
    monkeypatch.setattr(lookup_module, "CANDIDATE_LIMIT", -1)   # LIMIT âm → Postgres báo lỗi

    def script(messages, i, tool_choice):
        tool_results = [m for m in messages if isinstance(m, ToolMessage)]
        if not tool_results:
            return tool_call("lookup_food", {"query": "gạo tẻ máy"})
        assert tool_results[-1].content.startswith(FOOD_UNAVAILABLE_CODE)
        return AIMessage(content="Bảng thực phẩm tạm thời không truy cập được, bạn thử lại sau nhé.")

    with patch.object(fitness_agent, "llm", FakeChatModel(script)):
        res = await async_client.post(CHAT_URL, json={"message": "Gạo tẻ máy bao nhiêu calo?"}, headers=auth_headers(token))

    assert res.status_code == 200
    assert res.json()["sources"] == []
    msgs = (await async_client.get(f"{SESSIONS_URL}/{res.json()['session_id']}/messages", headers=auth_headers(token))).json()
    assert len(msgs) == 2 and FOOD_UNAVAILABLE_CODE not in msgs[1]["content"]


def _connect_unreachable():
    import chromadb
    from services.knowledge.vector_store import KnowledgeStoreError

    try:
        return chromadb.HttpClient(host="127.0.0.1", port=1)
    except Exception as exc:  # noqa: BLE001 — giống get_client thật: bọc lỗi kết nối
        raise KnowledgeStoreError("Không kết nối được ChromaDB.") from exc
