"""Migration e4c1a8f2d905 (đưa mọi khai báo bệnh cũ về rỗng): chạy upgrade() TRONG một transaction rồi ROLLBACK,
nên không đổi DB dev. Không chạy `alembic downgrade` thật."""
import importlib.util
import pathlib

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from core.config import settings

MIGRATION = (pathlib.Path(__file__).resolve().parents[1]
             / "alembic/versions/e4c1a8f2d905_reset_medical_conditions_new_codes.py")


def load_migration():
    spec = importlib.util.spec_from_file_location("mig_e4c1a8f2d905", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    assert mig.revision == "e4c1a8f2d905" and mig.down_revision == "b7d4e2a9c615"


def _user_with_profile(conn, email: str, conditions: list[str], notes, consent: bool):
    user_id = conn.execute(text(
        "INSERT INTO users (id, email, hashed_password, is_active, is_superuser) "
        "VALUES (gen_random_uuid(), :e, 'x', true, false) RETURNING id"), {"e": email}).scalar_one()
    conn.execute(text(
        "INSERT INTO user_profiles (id, user_id, age, medical_conditions, medical_notes, medical_consent_at) "
        "VALUES (gen_random_uuid(), :u, 30, CAST(:c AS varchar[]), :n, CASE WHEN :k THEN now() END)"),
        {"u": user_id, "c": conditions, "n": notes, "k": consent})
    return user_id


def _row(conn, user_id):
    return conn.execute(text(
        "SELECT medical_conditions, medical_notes, medical_consent_at, age FROM user_profiles WHERE user_id = :u"),
        {"u": user_id}).one()


def test_upgrade_resets_old_declarations_in_rolled_back_transaction(sync_conn):
    mig = load_migration()
    old = _user_with_profile(sync_conn, "zq.mig.codes.old@example.com", ["kidney", "other"], "ghi chú thử", True)
    kept_code = _user_with_profile(sync_conn, "zq.mig.codes.kept@example.com", ["hypertension"], None, True)
    none = _user_with_profile(sync_conn, "zq.mig.codes.none@example.com", [], None, False)

    with Operations.context(MigrationContext.configure(sync_conn)):
        mig.upgrade()

    # Phương án B: mọi khai báo (kể cả mã vẫn còn trong danh sách mới) về rỗng, ghi chú và thời điểm đồng ý null
    assert _row(sync_conn, old) == ([], None, None, 30)
    assert _row(sync_conn, kept_code) == ([], None, None, 30)
    assert _row(sync_conn, none) == ([], None, None, 30)


def test_downgrade_is_noop(sync_conn):
    mig = load_migration()
    user_id = _user_with_profile(sync_conn, "zq.mig.codes.down@example.com", ["stroke"], None, True)
    with Operations.context(MigrationContext.configure(sync_conn)):
        mig.downgrade()
    conditions, notes, consent_at, _ = _row(sync_conn, user_id)
    assert conditions == ["stroke"] and notes is None and consent_at is not None
