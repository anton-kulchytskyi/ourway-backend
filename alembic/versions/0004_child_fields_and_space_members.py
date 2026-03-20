"""child fields and space members

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    # Add child-related fields to users
    op.add_column("users", sa.Column("autonomy_level", sa.Integer(), nullable=True))
    op.add_column(
        "users",
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )

    # Create space_members table
    op.create_table(
        "space_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("space_id", sa.Integer(), sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "role",
            sa.Enum("owner", "editor", "viewer", name="spacememberrole"),
            nullable=False,
            server_default="editor",
        ),
        sa.UniqueConstraint("space_id", "user_id", name="uq_space_members"),
    )
    op.create_index("ix_space_members_space_id", "space_members", ["space_id"])
    op.create_index("ix_space_members_user_id", "space_members", ["user_id"])

    # Create invitations table
    op.create_table(
        "invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(64), unique=True, nullable=False),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("space_id", sa.Integer(), sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=True),
        sa.Column("invited_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "role",
            sa.Enum("editor", "viewer", name="invitationrole"),
            nullable=False,
            server_default="editor",
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "accepted", "expired", name="invitationstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("invitations")
    op.drop_index("ix_space_members_user_id", "space_members")
    op.drop_index("ix_space_members_space_id", "space_members")
    op.drop_table("space_members")
    op.drop_column("users", "created_by_id")
    op.drop_column("users", "autonomy_level")
    op.execute("DROP TYPE IF EXISTS spacememberrole")
    op.execute("DROP TYPE IF EXISTS invitationrole")
    op.execute("DROP TYPE IF EXISTS invitationstatus")
