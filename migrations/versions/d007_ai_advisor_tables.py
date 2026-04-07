"""Add AI advisor tables: conversations, messages, usage.

Revision ID: d007
Revises: d006
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa

revision = "d007"
down_revision = "d006"
branch_labels = None
depends_on = None


def _table_exists(name):
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name = :t"
    ), {"t": name})
    return result.fetchone() is not None


def upgrade():
    if not _table_exists("ai_conversations"):
        op.create_table(
            "ai_conversations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(),
                       sa.ForeignKey("users.id"), nullable=False),
            sa.Column("title", sa.String(200), server_default="New conversation"),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
        )
        op.create_index("ix_ai_conversations_user_id",
                        "ai_conversations", ["user_id"])

    if not _table_exists("ai_messages"):
        op.create_table(
            "ai_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("conversation_id", sa.Integer(),
                       sa.ForeignKey("ai_conversations.id"), nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime()),
        )
        op.create_index("ix_ai_messages_conversation_id",
                        "ai_messages", ["conversation_id"])

    if not _table_exists("ai_usage"):
        op.create_table(
            "ai_usage",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(),
                       sa.ForeignKey("users.id"), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("query_count", sa.Integer(), server_default="0"),
            sa.UniqueConstraint("user_id", "date", name="uq_ai_usage_user_date"),
        )
        op.create_index("ix_ai_usage_user_id", "ai_usage", ["user_id"])


def downgrade():
    op.drop_table("ai_usage")
    op.drop_table("ai_messages")
    op.drop_table("ai_conversations")
