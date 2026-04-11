"""Add watchlist_items table for user ticker watchlists.

Revision ID: d012
Revises: d011
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa

revision = "d012"
down_revision = "d011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("label", sa.String(length=50), server_default=""),
        sa.Column("position", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),
    )
    with op.batch_alter_table("watchlist_items", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_watchlist_items_user_id"), ["user_id"], unique=False
        )


def downgrade():
    with op.batch_alter_table("watchlist_items", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_watchlist_items_user_id"))
    op.drop_table("watchlist_items")
