"""create daily_plans table

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "daily_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "confirmed", "completed", name="dailyplanstatus"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_daily_plans_user_date", "daily_plans", ["user_id", "date"])
    op.create_unique_constraint("uq_daily_plans_user_date", "daily_plans", ["user_id", "date"])


def downgrade():
    op.drop_constraint("uq_daily_plans_user_date", "daily_plans", type_="unique")
    op.drop_index("ix_daily_plans_user_date", "daily_plans")
    op.drop_table("daily_plans")
    op.execute("DROP TYPE IF EXISTS dailyplanstatus")
