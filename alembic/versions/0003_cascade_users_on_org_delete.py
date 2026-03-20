"""cascade users on org delete

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-20

"""
from typing import Sequence, Union
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Change users.organization_id from SET NULL to CASCADE
    # (org deleted → all members deleted too)
    op.drop_constraint("users_organization_id_fkey", "users", type_="foreignkey")
    op.create_foreign_key(None, "users", "organizations", ["organization_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint("users_organization_id_fkey", "users", type_="foreignkey")
    op.create_foreign_key(None, "users", "organizations", ["organization_id"], ["id"], ondelete="SET NULL")
