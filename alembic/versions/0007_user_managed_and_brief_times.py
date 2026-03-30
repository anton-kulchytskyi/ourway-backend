"""add managed profile fields and daily brief times to users

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("is_managed", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("managed_by", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("morning_brief_time", sa.Time(), nullable=False, server_default="07:30:00"))
    op.add_column("users", sa.Column("evening_ritual_time", sa.Time(), nullable=False, server_default="21:00:00"))
    op.create_foreign_key(
        "fk_users_managed_by",
        "users", "users",
        ["managed_by"], ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("fk_users_managed_by", "users", type_="foreignkey")
    op.drop_column("users", "evening_ritual_time")
    op.drop_column("users", "morning_brief_time")
    op.drop_column("users", "managed_by")
    op.drop_column("users", "is_managed")
