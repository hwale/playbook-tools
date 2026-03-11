"""add users and update sessions

Revision ID: 0002
Revises: 0001
Create Date: 2025-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import TIMESTAMP

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users ---
    # Stores email + bcrypt hashed password. Never store plaintext passwords.
    # gen_random_uuid() is a PostgreSQL function that generates v4 UUIDs server-side.
    op.create_table(
        "users",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("hashed_password", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- update chat_sessions ---
    # Make document_id nullable — sessions now represent a playbook conversation,
    # not necessarily a specific document. Document gets attached when user uploads.
    op.alter_column("chat_sessions", "document_id", nullable=True)

    # user_id: who owns this session. Nullable so dev/unauthenticated use still works.
    op.add_column(
        "chat_sessions",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # playbook_name: which playbook this session belongs to.
    # Used to filter the sidebar — each playbook shows its own session list.
    op.add_column(
        "chat_sessions",
        sa.Column("playbook_name", sa.Text, nullable=True),
    )

    # title: auto-set from the first user message (truncated to 60 chars).
    # Shown in the sidebar so users can identify conversations at a glance.
    op.add_column(
        "chat_sessions",
        sa.Column("title", sa.Text, nullable=True),
    )

    # Index for the common query: "show me all sessions for this user + playbook"
    op.create_index(
        "ix_chat_sessions_user_playbook",
        "chat_sessions",
        ["user_id", "playbook_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_user_playbook", table_name="chat_sessions")
    op.drop_column("chat_sessions", "title")
    op.drop_column("chat_sessions", "playbook_name")
    op.drop_column("chat_sessions", "user_id")
    op.alter_column("chat_sessions", "document_id", nullable=False)
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
