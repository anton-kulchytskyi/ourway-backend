"""cascade delete

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-20

"""
from typing import Sequence, Union
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # spaces.organization_id → CASCADE (org deleted → spaces deleted)
    op.drop_constraint("spaces_organization_id_fkey", "spaces", type_="foreignkey")
    op.create_foreign_key(None, "spaces", "organizations", ["organization_id"], ["id"], ondelete="CASCADE")

    # tasks.space_id → CASCADE (space deleted → tasks deleted)
    op.drop_constraint("tasks_space_id_fkey", "tasks", type_="foreignkey")
    op.create_foreign_key(None, "tasks", "spaces", ["space_id"], ["id"], ondelete="CASCADE")

    # tasks.creator_id → SET NULL (user deleted → task stays, creator = null)
    op.drop_constraint("tasks_creator_id_fkey", "tasks", type_="foreignkey")
    op.create_foreign_key(None, "tasks", "users", ["creator_id"], ["id"], ondelete="SET NULL")

    # tasks.assignee_id → SET NULL
    op.drop_constraint("tasks_assignee_id_fkey", "tasks", type_="foreignkey")
    op.create_foreign_key(None, "tasks", "users", ["assignee_id"], ["id"], ondelete="SET NULL")

    # users.organization_id → SET NULL (org deleted → user залишається без орг)
    op.drop_constraint("users_organization_id_fkey", "users", type_="foreignkey")
    op.create_foreign_key(None, "users", "organizations", ["organization_id"], ["id"], ondelete="SET NULL")

    # gamification_profiles.user_id → CASCADE (user deleted → profile deleted)
    op.drop_constraint("gamification_profiles_user_id_fkey", "gamification_profiles", type_="foreignkey")
    op.create_foreign_key(None, "gamification_profiles", "users", ["user_id"], ["id"], ondelete="CASCADE")

    # rewards.profile_id → CASCADE (profile deleted → rewards deleted)
    op.drop_constraint("rewards_profile_id_fkey", "rewards", type_="foreignkey")
    op.create_foreign_key(None, "rewards", "gamification_profiles", ["profile_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    pass
