"""add sources to chat_messages

Revision ID: 77171de75434
Revises: fc31f7797355
Create Date: 2026-10-23 15:09:49.116065

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '77171de75434'
down_revision: Union[str, None] = 'fc31f7797355'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nguồn trích dẫn (RAG) lưu cùng tin nhắn AI; tin nhắn cũ để NULL
    op.add_column(
        "chat_messages",
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "sources")
