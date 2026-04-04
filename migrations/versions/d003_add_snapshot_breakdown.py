"""add breakdown JSON column to portfolio_snapshots

Revision ID: d003_snapshot_breakdown
Revises: d002_bucket_rollup
Create Date: 2026-04-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'd003_snapshot_breakdown'
down_revision = 'd002_bucket_rollup'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("portfolio_snapshots") as batch_op:
        batch_op.add_column(
            sa.Column("breakdown", sa.JSON(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("portfolio_snapshots") as batch_op:
        batch_op.drop_column("breakdown")
