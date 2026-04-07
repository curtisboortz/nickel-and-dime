"""Add institution branding columns to plaid_items.

Revision ID: d006
Revises: d005
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa

revision = "d006"
down_revision = "d005"
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
    with op.batch_alter_table("plaid_items") as batch_op:
        if not _column_exists("plaid_items", "logo_base64"):
            batch_op.add_column(sa.Column(
                "logo_base64", sa.Text(), nullable=True,
            ))
        if not _column_exists("plaid_items", "primary_color"):
            batch_op.add_column(sa.Column(
                "primary_color", sa.String(20),
                server_default="", nullable=True,
            ))


def downgrade():
    with op.batch_alter_table("plaid_items") as batch_op:
        batch_op.drop_column("primary_color")
        batch_op.drop_column("logo_base64")
