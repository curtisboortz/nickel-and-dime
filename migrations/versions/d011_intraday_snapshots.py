"""Add intraday_snapshots table for hourly portfolio granularity.

Revision ID: d011
Revises: d010
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa

revision = "d011"
down_revision = "d010"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "intraday_snapshots" not in inspector.get_table_names():
        op.create_table(
            "intraday_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
            sa.Column("total", sa.Float(), nullable=False),
        )
        op.create_index("ix_intraday_user_ts", "intraday_snapshots", ["user_id", "timestamp"])


def downgrade():
    op.drop_index("ix_intraday_user_ts", table_name="intraday_snapshots")
    op.drop_table("intraday_snapshots")
