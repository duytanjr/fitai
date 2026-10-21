"""
Seed Data Script — Nạp dữ liệu mẫu vào database.

Tạo 1 user nam, 182cm, 79kg, mục tiêu giảm cân để test tính năng tư vấn.

Chạy bên trong Docker container:
  docker exec fitai_backend python scripts/seed_data.py
"""
import asyncio
import sys
import os

# Thêm thư mục gốc vào sys.path để import được core, models, v.v.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import AsyncSessionLocal, engine, Base
from core.security import get_password_hash
from models.user import User
from models.profile import UserProfile
from models.chat import ChatSession, ChatMessage


async def seed():
    """Tạo dữ liệu mẫu."""

    async with AsyncSessionLocal() as session:
        # ──────────────────────────────────────────────────
        # 1. Kiểm tra xem user đã tồn tại chưa (tránh chạy 2 lần bị lỗi)
        # ──────────────────────────────────────────────────
        from sqlalchemy import select

        existing = await session.execute(
            select(User).where(User.email == "test@fitai.vn")
        )
        if existing.scalar_one_or_none():
            print("⚠️  User test@fitai.vn đã tồn tại. Bỏ qua seed.")
            return

        # ──────────────────────────────────────────────────
        # 2. Tạo User
        # ──────────────────────────────────────────────────
        user = User(
            email="test@fitai.vn",
            hashed_password=get_password_hash("Test@1234"),  # Mật khẩu: Test@1234
            full_name="Nguyễn Văn Tân",
            is_active=True,
        )
        session.add(user)
        await session.flush()  # flush để lấy user.id (UUID) cho profile bên dưới

        print(f"✅ Tạo user: {user.email} (id: {user.id})")
        print(f"   Mật khẩu: Test@1234")

        # ──────────────────────────────────────────────────
        # 3. Tạo Profile (thông tin thể chất)
        # ──────────────────────────────────────────────────
        profile = UserProfile(
            user_id=user.id,
            age=25,
            gender="male",
            height_cm=182.0,
            weight_kg=79.0,
            activity_level="moderate",       # Vận động vừa phải
            fitness_goal="weight_loss",      # Mục tiêu: giảm cân
            dietary_restrictions="Không",    # Không dị ứng thực phẩm
        )
        session.add(profile)

        print(f"✅ Tạo profile: Nam, 25 tuổi, 182cm, 79kg")
        print(f"   Mục tiêu: Giảm cân | Vận động: Vừa phải")

        # ──────────────────────────────────────────────────
        # 4. Tạo 1 chat session mẫu + 2 tin nhắn
        # ──────────────────────────────────────────────────
        chat_session = ChatSession(
            user_id=user.id,
            title="Tư vấn giảm cân lần đầu",
        )
        session.add(chat_session)
        await session.flush()

        msg1 = ChatMessage(
            session_id=chat_session.id,
            role="user",
            content="Tôi cao 1m82, nặng 79kg, muốn giảm cân. Bạn tư vấn giúp tôi nhé!",
        )
        msg2 = ChatMessage(
            session_id=chat_session.id,
            role="assistant",
            content=(
                "Chào bạn! Với chiều cao 182cm và cân nặng 79kg, BMI của bạn khoảng 23.8 — "
                "nằm trong ngưỡng bình thường nhưng gần mức thừa cân. "
                "Để giảm cân hiệu quả, tôi cần biết thêm:\n"
                "1. Bạn thường tập luyện thể thao gì?\n"
                "2. Chế độ ăn hiện tại của bạn ra sao?\n"
                "3. Mục tiêu cân nặng lý tưởng bạn mong muốn là bao nhiêu?"
            ),
        )
        session.add_all([msg1, msg2])

        print(f"✅ Tạo chat session: '{chat_session.title}' (2 tin nhắn mẫu)")

        # ──────────────────────────────────────────────────
        # 5. Commit tất cả
        # ──────────────────────────────────────────────────
        await session.commit()

        print()
        print("=" * 50)
        print("🎉 SEED DATA THÀNH CÔNG!")
        print("=" * 50)
        print()
        print("Thông tin đăng nhập:")
        print(f"  Email:    test@fitai.vn")
        print(f"  Password: Test@1234")
        print()
        print("Thông tin thể chất:")
        print(f"  Giới tính:  Nam")
        print(f"  Tuổi:       25")
        print(f"  Chiều cao:  182 cm")
        print(f"  Cân nặng:   79 kg")
        print(f"  Mục tiêu:   Giảm cân")
        print(f"  Vận động:   Vừa phải")


if __name__ == "__main__":
    asyncio.run(seed())
