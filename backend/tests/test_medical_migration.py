"""Migration b7d4e2a9c615 (bệnh lý trong user_profiles): chạy downgrade() rồi upgrade() TRONG một transaction
và ROLLBACK, nên không đổi DB dev (Postgres hỗ trợ DDL trong transaction). Không chạy `alembic downgrade` thật."""
import importlib.util
import pathlib

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

from core.config import settings

MIGRATION = pathlib.Path(__file__).resolve().parents[1] / "alembic/versions/b7d4e2a9c615_add_medical_to_user_profiles.py"
NEW_COLUMNS = {"medical_conditions", "medical_notes", "medical_consent_at"}


def load_migration():
    spec = importlib.util.spec_from_file_location("mig_b7d4e2a9c615", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def columns(conn) -> dict:
    return {c["name"]: c for c in inspect(conn).get_columns("user_profiles")}


@pytest.fixture
def sync_conn():
    engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", "+psycopg2"))
    try:
        conn = engine.connect()
    except Exception as exc:  # noqa: BLE001
        engine.dispose()
        pytest.skip(f"Không kết nối được PostgreSQL ({type(exc).__name__})")
    trans = conn.begin()
    try:
        yield conn
    finally:
        trans.rollback()
        conn.close()
        engine.dispose()


def test_revision_chain():
    mig = load_migration()
    assert mig.revision == "b7d4e2a9c615" and mig.down_revision == "d2a6f9c3e8b1"


def test_downgrade_then_upgrade_in_rolled_back_transaction(sync_conn):
    mig = load_migration()
    assert NEW_COLUMNS <= set(columns(sync_conn)), "DB dev chưa chạy alembic upgrade head"
    user_id = sync_conn.execute(text(
        "INSERT INTO users (id, email, hashed_password, is_active, is_superuser) "
        "VALUES (gen_random_uuid(), 'zq.mig.medical@example.com', 'x', true, false) RETURNING id")).scalar_one()
    sync_conn.execute(text("INSERT INTO user_profiles (id, user_id) VALUES (gen_random_uuid(), :u)"), {"u": user_id})

    with Operations.context(MigrationContext.configure(sync_conn)):
        mig.downgrade()
    assert not NEW_COLUMNS & set(columns(sync_conn))

    with Operations.context(MigrationContext.configure(sync_conn)):
        mig.upgrade()
    cols = columns(sync_conn)
    assert NEW_COLUMNS <= set(cols)
    assert cols["medical_conditions"]["nullable"] is False
    assert cols["medical_notes"]["nullable"] is True and cols["medical_notes"]["type"].length == 500
    assert cols["medical_consent_at"]["nullable"] is True
    # Hàng có sẵn trước khi thêm cột (người dùng cũ) nhận danh sách rỗng
    row = sync_conn.execute(text(
        "SELECT medical_conditions, medical_notes, medical_consent_at FROM user_profiles WHERE user_id = :u"),
        {"u": user_id}).one()
    assert row == ([], None, None)
