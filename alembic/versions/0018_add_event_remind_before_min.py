"""add remind_before_min to events

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("events", sa.Column("remind_before_min", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("events", "remind_before_min")
