"""Add drift-aware rebalancing columns.

- MonthlyInvestment: bucket (asset class mapping), monthly_budget (persisted per-month)
- UserSettings: rebalance_months (timeline for drift closure)

Revision ID: d010
Revises: d009
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa

revision = "d010"
down_revision = "d009"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    mi_cols = [c["name"] for c in inspector.get_columns("monthly_investments")]
    if "bucket" not in mi_cols:
        op.add_column("monthly_investments", sa.Column("bucket", sa.String(50), nullable=True))
    if "monthly_budget" not in mi_cols:
        op.add_column("monthly_investments", sa.Column("monthly_budget", sa.Float(), server_default="0", nullable=True))

    us_cols = [c["name"] for c in inspector.get_columns("user_settings")]
    if "rebalance_months" not in us_cols:
        op.add_column("user_settings", sa.Column("rebalance_months", sa.Integer(), server_default="12", nullable=True))


def downgrade():
    op.drop_column("monthly_investments", "monthly_budget")
    op.drop_column("monthly_investments", "bucket")
    op.drop_column("user_settings", "rebalance_months")
