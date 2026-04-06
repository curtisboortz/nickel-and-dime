"""add plaid_items table and source/plaid_item_id columns to holdings

Revision ID: d004_plaid_support
Revises: d003_snapshot_breakdown
Create Date: 2026-04-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'd004_plaid_support'
down_revision = 'd003_snapshot_breakdown'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "plaid_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("item_id", sa.String(120), nullable=False, unique=True),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("institution_id", sa.String(80), server_default=""),
        sa.Column("institution_name", sa.String(200), server_default=""),
        sa.Column("products", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(30), server_default="good"),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_plaid_user", "plaid_items", ["user_id"])

    with op.batch_alter_table("holdings") as batch_op:
        batch_op.add_column(sa.Column("source", sa.String(50), server_default="manual"))
        batch_op.add_column(sa.Column("plaid_item_id", sa.Integer(),
                                      sa.ForeignKey("plaid_items.id"), nullable=True))


def downgrade():
    with op.batch_alter_table("holdings") as batch_op:
        batch_op.drop_column("plaid_item_id")
        batch_op.drop_column("source")

    op.drop_index("ix_plaid_user", table_name="plaid_items")
    op.drop_table("plaid_items")
