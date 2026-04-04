"""add bucket_rollup to user_settings

Revision ID: d002_bucket_rollup
Revises: d001_founder
Create Date: 2026-03-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'd002_bucket_rollup'
down_revision = 'd001_founder'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.add_column(
            sa.Column("bucket_rollup", sa.JSON(), nullable=True, server_default="{}")
        )


def downgrade():
    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.drop_column("bucket_rollup")
