"""make users.email nullable for telegram-only accounts

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-31
"""
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("users", "email", nullable=True)


def downgrade():
    # Note: will fail if any email IS NULL
    op.alter_column("users", "email", nullable=False)
