"""Tests cho API Chatbot (POST /chat, GET /chat/sessions, GET /chat/sessions/{id}/messages).

Mọi bài test đều mock mô hình AI (FitnessAdvisorAgent/Gemini), tuyệt đối không gọi API thật.
"""
import uuid
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient

from services.ai_agents.fitness_advisor import ChatAgentException, build_system_prompt
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
async def test_chat_with_profile_and_metrics_personalization(
    async_client: AsyncClient,
):
    """7. System prompt cá nhân hóa:

    - User đã có hồ sơ và chỉ số: prompt chứa đúng tuổi, cân nặng, mục tiêu, calo, macro.
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
    assert profile_data["metrics"]["target_calories"] == 2104

    # Kiểm tra văn bản build_system_prompt
    prompt_text = build_system_prompt(profile_data)
    assert "22" in prompt_text
    assert "180.0 cm" in prompt_text
    assert "78.0 kg" in prompt_text
    assert "2104 kcal/ngày" in prompt_text
    assert "Dị ứng tôm cua" in prompt_text
    assert "TIẾNG VIỆT" in prompt_text
    assert "KHÔNG PHẢI là bác sĩ y khoa" in prompt_text


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
