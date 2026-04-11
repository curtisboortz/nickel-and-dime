"""Add dashboard_layout column to user_settings.

Revision ID: d013
Revises: d012
"""
from alembic import op
import sqlalchemy as sa

revision = "d013"
down_revision = "d012"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.add_column(
            sa.Column("dashboard_layout", sa.JSON(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.drop_column("dashboard_layout")
