"""make task creator_id nullable with SET NULL on delete

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    # Drop FKs, make creator_id nullable, recreate with ON DELETE SET NULL
    op.execute("""
        ALTER TABLE tasks
            DROP CONSTRAINT IF EXISTS tasks_creator_id_fkey,
            ALTER COLUMN creator_id DROP NOT NULL,
            ADD CONSTRAINT tasks_creator_id_fkey
                FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE SET NULL
    """)

    op.execute("""
        ALTER TABLE tasks
            DROP CONSTRAINT IF EXISTS tasks_assignee_id_fkey,
            ADD CONSTRAINT tasks_assignee_id_fkey
                FOREIGN KEY (assignee_id) REFERENCES users(id) ON DELETE SET NULL
    """)


def downgrade():
    op.execute("""
        ALTER TABLE tasks
            DROP CONSTRAINT IF EXISTS tasks_creator_id_fkey,
            ALTER COLUMN creator_id SET NOT NULL,
            ADD CONSTRAINT tasks_creator_id_fkey
                FOREIGN KEY (creator_id) REFERENCES users(id)
    """)

    op.execute("""
        ALTER TABLE tasks
            DROP CONSTRAINT IF EXISTS tasks_assignee_id_fkey,
            ADD CONSTRAINT tasks_assignee_id_fkey
                FOREIGN KEY (assignee_id) REFERENCES users(id)
    """)
