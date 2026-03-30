"""add auto_add_to_child_day to space_members

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "space_members",
        sa.Column("auto_add_to_child_day", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade():
    op.drop_column("space_members", "auto_add_to_child_day")
