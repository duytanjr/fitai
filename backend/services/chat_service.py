"""Chat Service — Quản lý vòng đời phiên chat, lịch sử tin nhắn và tích hợp AI Agent."""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from models.chat import ChatSession, ChatMessage
from models.profile import UserProfile
from services.ai_agents.fitness_advisor import AgentToolContext, ChatAgentException, fitness_agent
from services.foods.lookup import search_foods


class ChatService:
    """Quản lý các thao tác lưu trữ và tương tác chatbot của người dùng."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def handle_chat(
        self,
        user_id: uuid.UUID,
        message: str,
        session_id: Optional[uuid.UUID] = None,
    ) -> tuple[uuid.UUID, str, list[dict]]:
        """Xử lý luồng chat chuẩn:

        1. Kiểm tra quyền session (nếu có); nếu mới tạo UUID mới.
        2. Lấy 10 tin nhắn gần nhất TRƯỚC tin hiện tại làm ngữ cảnh.
        3. Đọc hồ sơ (chỉ thông tin cơ bản; con số chỉ số do công cụ calc_body_metrics tính).
        4. Gọi agent AI (không giữ transaction DB mở trong lúc chờ LLM).
        5. Chỉ khi gọi AI thành công mới lưu cả tin user và tin AI (kèm sources) trong 1 transaction.
        """
        is_new_session = False
        target_session_id = session_id

        # ── Bước 1: Kiểm tra quyền sở hữu session ──────────────────────────────
        if target_session_id is not None:
            stmt = select(ChatSession).where(
                ChatSession.id == target_session_id,
                ChatSession.user_id == user_id,
            )
            res = await self.db.execute(stmt)
            existing_session = res.scalar_one_or_none()
            if existing_session is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Phiên trò chuyện không tồn tại hoặc không thuộc quyền sở hữu của bạn.",
                )
        else:
            is_new_session = True
            target_session_id = uuid.uuid4()

        # ── Bước 2: Lấy 10 tin nhắn gần nhất TRƯỚC tin hiện tại ────────────────
        history: list[dict] = []
        if not is_new_session:
            history_stmt = (
                select(ChatMessage)
                .where(ChatMessage.session_id == target_session_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(10)
            )
            history_res = await self.db.execute(history_stmt)
            recent_msgs = history_res.scalars().all()
            # Đảo ngược lại để đúng thứ tự thời gian tăng dần
            for m in reversed(recent_msgs):
                history.append({"role": m.role, "content": m.content})

        # ── Bước 3: Lấy hồ sơ của user (KHÔNG đưa chỉ số tính toán vào prompt) ──
        profile = await self._load_profile(user_id)
        profile_data = None
        if profile is not None:
            profile_data = {
                "age": profile.age,
                "gender": profile.gender,
                "height_cm": profile.height_cm,
                "weight_kg": profile.weight_kg,
                "activity_level": profile.activity_level,
                "fitness_goal": profile.fitness_goal,
                "dietary_restrictions": profile.dietary_restrictions,
            }

        # ── Bước 4: Gọi FitnessAdvisorAgent ────────────────────────────────────
        # Công cụ calc_body_metrics chỉ đọc được hồ sơ của user_id lấy từ JWT;
        # lookup_food tra bảng foods bằng phiên DB của request (trong SAVEPOINT)
        tool_context = AgentToolContext(
            load_profile=lambda: self._load_profile(user_id),
            lookup_food=lambda query: search_foods(self.db, query),
        )
        try:
            ai_reply = await fitness_agent.chat(
                history=history,
                user_message=message,
                profile_data=profile_data,
                tool_context=tool_context,
            )
        except ChatAgentException as e:
            raise HTTPException(status_code=e.status_code, detail=e.message)
        sources = tool_context.sources

        # ── Bước 5: Lưu cả tin user và tin AI trong 1 transaction an toàn ──────
        try:
            now = datetime.now(timezone.utc)
            if is_new_session:
                title = message[:50].strip() if len(message) > 50 else message.strip()
                new_session = ChatSession(
                    id=target_session_id,
                    user_id=user_id,
                    title=title,
                    created_at=now,
                )
                self.db.add(new_session)

            user_msg = ChatMessage(
                session_id=target_session_id,
                role="user",
                content=message,
                created_at=now,
            )
            ai_msg = ChatMessage(
                session_id=target_session_id,
                role="assistant",
                content=ai_reply,
                sources=sources or None,
                created_at=now + timedelta(microseconds=50),
            )
            self.db.add(user_msg)
            self.db.add(ai_msg)

            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            import logging
            logging.getLogger(__name__).exception("Failed to save chat: %s", type(e).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Không thể lưu lịch sử cuộc trò chuyện. Vui lòng thử lại sau.",
            )

        return target_session_id, ai_reply, sources

    async def _load_profile(self, user_id: uuid.UUID) -> Optional[UserProfile]:
        res = await self.db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
        return res.scalar_one_or_none()

    async def get_user_sessions(self, user_id: uuid.UUID) -> list[ChatSession]:
        """Lấy danh sách các phiên chat của user, mới nhất xếp trước."""
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.created_at.desc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_session_messages(
        self, user_id: uuid.UUID, session_id: uuid.UUID
    ) -> list[ChatMessage]:
        """Lấy danh sách tin nhắn của một phiên chat theo thứ tự thời gian.

        Bảo vệ quyền riêng tư: Trả 404 nếu session không tồn tại hoặc không thuộc user.
        """
        # Kiểm tra session thuộc user
        session_stmt = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
        session_res = await self.db.execute(session_stmt)
        session = session_res.scalar_one_or_none()
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Phiên trò chuyện không tồn tại hoặc không thuộc quyền sở hữu của bạn.",
            )

        msg_stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        msg_res = await self.db.execute(msg_stmt)
        return list(msg_res.scalars().all())
