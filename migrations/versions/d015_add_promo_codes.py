"""Add promo_codes table.

Revision ID: d015
Revises: d014
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa

revision = "d015"
down_revision = "d014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "promo_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("trial_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("times_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True, server_default="1"),
        sa.Column("note", sa.String(255), nullable=True),
    )


def downgrade():
    op.drop_table("promo_codes")
