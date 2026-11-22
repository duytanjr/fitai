"""reset medical conditions after switching to the new 7-code list (phương án B)

Revision ID: e4c1a8f2d905
Revises: b7d4e2a9c615
Create Date: 2026-11-23 10:00:00.000000

Danh sách bệnh đổi từ 11 mã sang 7 mã (musculoskeletal, cardiovascular, hypertension, metabolic, respiratory,
stroke, other). Sự đồng ý cũ gắn với danh sách cũ (và musculoskeletal đổi nghĩa), nên MỌI hồ sơ đã khai báo
bệnh được đưa về "không khai báo": medical_conditions = '{}', medical_notes = NULL, medical_consent_at = NULL.
Chỉ có tài khoản thử bị ảnh hưởng; người dùng khai báo lại ở bước "Sức khỏe". Không đổi cấu trúc bảng.

downgrade() KHÔNG làm gì: dữ liệu bệnh lý đã xoá không khôi phục được (và mã cũ không còn hợp lệ ở schema API).
Không chạy downgrade thật; tests/test_medical_codes_migration.py chạy upgrade() trong transaction rồi rollback.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e4c1a8f2d905'
down_revision: Union[str, None] = 'b7d4e2a9c615'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text(
        "UPDATE user_profiles "
        "SET medical_conditions = '{}'::varchar[], medical_notes = NULL, medical_consent_at = NULL "
        "WHERE cardinality(medical_conditions) > 0 OR medical_notes IS NOT NULL OR medical_consent_at IS NOT NULL"
    ))


def downgrade() -> None:
    # Cố ý không làm gì: không khôi phục được dữ liệu bệnh lý đã xoá ở upgrade().
    pass
