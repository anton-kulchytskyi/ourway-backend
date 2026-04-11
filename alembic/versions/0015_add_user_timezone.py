"""add timezone field to users

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("timezone", sa.String(50), nullable=False, server_default="UTC"),
    )


def downgrade():
    op.drop_column("users", "timezone")
