"""
Alembic env.py — Cấu hình Alembic để nó nhận diện tất cả models và kết nối DB.

Flow: Alembic đọc file này → import Base (chứa metadata tất cả bảng)
     → so sánh metadata với DB thật → sinh ra migration script tự động.
"""
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ─── Import cấu hình project ─────────────────────────────────────────
from core.config import settings
from core.database import Base

# ─── Import TẤT CẢ models để Alembic "thấy" chúng ──────────────────
# (Nếu không import, Alembic sẽ không biết bảng nào cần tạo)
from models.user import User          # noqa: F401
from models.profile import UserProfile  # noqa: F401
from models.chat import ChatSession, ChatMessage  # noqa: F401
from models.food_source import FoodSource  # noqa: F401
from models.food import Food  # noqa: F401
from models.meal_log import MealLog  # noqa: F401
from models.body_metric import BodyMetric  # noqa: F401

# ─── Alembic Config ──────────────────────────────────────────────────
config = context.config

# Ghi đè sqlalchemy.url bằng DATABASE_URL thật từ .env
# Phải chuyển từ asyncpg → psycopg2 vì Alembic chạy sync
sync_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
config.set_main_option("sqlalchemy.url", sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target_metadata = metadata của Base → chứa tất cả bảng đã import ở trên
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Chạy migration trong 'offline' mode (chỉ sinh SQL, không kết nối DB)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Chạy migration trong 'online' mode (kết nối DB thật, áp dụng thay đổi)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
