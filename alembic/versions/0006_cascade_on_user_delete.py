"""cascade delete tasks and gamification profile when user deleted

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-21
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    # tasks.creator_id: SET NULL → CASCADE (creator's tasks deleted with them)
    op.execute("""
        ALTER TABLE tasks
            DROP CONSTRAINT IF EXISTS tasks_creator_id_fkey,
            ADD CONSTRAINT tasks_creator_id_fkey
                FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE CASCADE
    """)

    # gamification_profiles.user_id: no ondelete → CASCADE
    op.execute("""
        ALTER TABLE gamification_profiles
            DROP CONSTRAINT IF EXISTS gamification_profiles_user_id_fkey,
            ADD CONSTRAINT gamification_profiles_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    """)


def downgrade():
    op.execute("""
        ALTER TABLE tasks
            DROP CONSTRAINT IF EXISTS tasks_creator_id_fkey,
            ADD CONSTRAINT tasks_creator_id_fkey
                FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE SET NULL
    """)

    op.execute("""
        ALTER TABLE gamification_profiles
            DROP CONSTRAINT IF EXISTS gamification_profiles_user_id_fkey,
            ADD CONSTRAINT gamification_profiles_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users(id)
    """)
