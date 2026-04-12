"""Add digest preference columns to user_settings.

Revision ID: d014
Revises: d013
"""
from alembic import op
import sqlalchemy as sa

revision = "d014"
down_revision = "d013"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.add_column(sa.Column("digest_enabled", sa.Boolean(), server_default="0", nullable=True))
        batch_op.add_column(sa.Column("digest_frequency", sa.String(10), server_default="weekly", nullable=True))
        batch_op.add_column(sa.Column("digest_day", sa.String(10), server_default="monday", nullable=True))
        batch_op.add_column(sa.Column("last_digest_sent", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.drop_column("last_digest_sent")
        batch_op.drop_column("digest_day")
        batch_op.drop_column("digest_frequency")
        batch_op.drop_column("digest_enabled")
