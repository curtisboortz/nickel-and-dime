"""Add institution_value column to holdings for Plaid broker valuation fallback.

Revision ID: d009
Revises: d008
Create Date: 2026-04-08
"""

from alembic import op
import sqlalchemy as sa

revision = "d009"
down_revision = "d008"
branch_labels = None
depends_on = None


def _column_exists(table, column):
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = :t AND column_name = :c"
    ), {"t": table, "c": column})
    return result.fetchone() is not None


def upgrade():
    if not _column_exists("holdings", "institution_value"):
        with op.batch_alter_table("holdings") as batch_op:
            batch_op.add_column(sa.Column(
                "institution_value", sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table("holdings") as batch_op:
        batch_op.drop_column("institution_value")
