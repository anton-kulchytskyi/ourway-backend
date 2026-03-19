"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("default_locale", sa.String(10), nullable=False, server_default="en"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "role",
            sa.Enum("owner", "member", "child", name="userrole"),
            nullable=False,
            server_default="member",
        ),
        sa.Column("locale", sa.String(10), nullable=False, server_default="en"),
        sa.Column("telegram_id", sa.Integer(), nullable=True, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
    )

    op.create_table(
        "spaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("emoji", sa.String(10), nullable=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("backlog", "todo", "in_progress", "blocked", "done", name="taskstatus"),
            nullable=False,
            server_default="backlog",
        ),
        sa.Column(
            "priority",
            sa.Enum("low", "medium", "high", name="taskpriority"),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("space_id", sa.Integer(), sa.ForeignKey("spaces.id"), nullable=False),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )

    op.create_table(
        "gamification_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("points_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("streak_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_activity", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
    )

    op.create_table(
        "rewards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("points_cost", sa.Integer(), nullable=False),
        sa.Column("is_claimed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("gamification_profiles.id"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("rewards")
    op.drop_table("gamification_profiles")
    op.drop_table("tasks")
    op.drop_table("spaces")
    op.drop_table("users")
    op.drop_table("organizations")
    op.execute("DROP TYPE IF EXISTS taskpriority")
    op.execute("DROP TYPE IF EXISTS taskstatus")
    op.execute("DROP TYPE IF EXISTS userrole")
