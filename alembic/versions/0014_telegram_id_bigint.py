"""change users.telegram_id from INTEGER to BIGINT

Telegram user IDs can exceed int32 range (max ~2.1B).

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "users", "telegram_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        "users", "telegram_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
