"""create events table

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("time_start", sa.Time(), nullable=True),
        sa.Column("time_end", sa.Time(), nullable=True),
        sa.Column("is_fixed", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("duration_min", sa.Integer(), nullable=True),
        sa.Column("find_before", sa.Date(), nullable=True),
        sa.Column("participants", ARRAY(sa.Integer()), nullable=False, server_default="{}"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_events_organization_date", "events", ["organization_id", "date"])


def downgrade():
    op.drop_index("ix_events_organization_date", "events")
    op.drop_table("events")
