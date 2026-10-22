"""Chat Service — Quản lý vòng đời phiên chat, lịch sử tin nhắn và tích hợp AI Agent."""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from models.chat import ChatSession, ChatMessage
from models.profile import UserProfile
from services.ai_agents.fitness_advisor import fitness_agent, ChatAgentException
from services.metrics_service import calculate_user_metrics


class ChatService:
    """Quản lý các thao tác lưu trữ và tương tác chatbot của người dùng."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def handle_chat(
        self,
        user_id: uuid.UUID,
        message: str,
        session_id: Optional[uuid.UUID] = None,
    ) -> tuple[uuid.UUID, str]:
        """Xử lý luồng chat chuẩn:

        1. Kiểm tra quyền session (nếu có); nếu mới tạo UUID mới.
        2. Lấy 10 tin nhắn gần nhất TRƯỚC tin hiện tại làm ngữ cảnh.
        3. Đọc hồ sơ và tính toán chỉ số sức khỏe (nếu đủ).
        4. Gọi agent AI (không giữ transaction DB mở trong lúc chờ LLM).
        5. Chỉ khi gọi AI thành công mới lưu cả tin user và tin AI trong 1 transaction.
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

        # ── Bước 3: Lấy hồ sơ và chỉ số sức khỏe của user ─────────────────────
        profile_stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        profile_res = await self.db.execute(profile_stmt)
        profile = profile_res.scalar_one_or_none()

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
                "metrics": None,
            }
            # Kiểm tra xem có đủ 6 trường cốt lõi để tính metrics không
            required_fields = ["age", "gender", "height_cm", "weight_kg", "activity_level", "fitness_goal"]
            if all(getattr(profile, f, None) is not None for f in required_fields):
                try:
                    m = calculate_user_metrics(
                        age=profile.age,
                        gender=profile.gender,
                        height_cm=profile.height_cm,
                        weight_kg=profile.weight_kg,
                        activity_level=profile.activity_level,
                        fitness_goal=profile.fitness_goal,
                    )
                    profile_data["metrics"] = {
                        "is_complete": True,
                        "bmi": m.bmi,
                        "bmi_category": m.bmi_category,
                        "bmr": m.bmr,
                        "tdee": m.tdee,
                        "target_calories": m.target_calories,
                        "calorie_floor_applied": m.calorie_floor_applied,
                        "protein_g": m.protein_g,
                        "fat_g": m.fat_g,
                        "carb_g": m.carb_g,
                    }
                except Exception:
                    profile_data["metrics"] = {"is_complete": False}
            else:
                profile_data["metrics"] = {"is_complete": False}

        # ── Bước 4: Gọi FitnessAdvisorAgent ────────────────────────────────────
        try:
            ai_reply = await fitness_agent.chat(
                history=history,
                user_message=message,
                profile_data=profile_data,
            )
        except ChatAgentException as e:
            raise HTTPException(status_code=e.status_code, detail=e.message)

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

        return target_session_id, ai_reply

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
