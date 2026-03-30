"""add daily flow fields to tasks

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tasks", sa.Column("scheduled_date", sa.Date(), nullable=True))
    op.add_column("tasks", sa.Column("time_start", sa.Time(), nullable=True))
    op.add_column("tasks", sa.Column(
        "source",
        sa.Enum("manual", "schedule", "family_space", name="tasksource"),
        nullable=False,
        server_default="manual",
    ))


def downgrade():
    op.drop_column("tasks", "source")
    op.drop_column("tasks", "time_start")
    op.drop_column("tasks", "scheduled_date")
    op.execute("DROP TYPE IF EXISTS tasksource")
