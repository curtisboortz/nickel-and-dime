"""Phase 5: Plaid enrichment — PlaidAccount, holding columns, investment txns, tax lots, balance source.

Revision ID: d008
Revises: d007
Create Date: 2026-04-08
"""

from alembic import op
import sqlalchemy as sa

revision = "d008"
down_revision = "d007"
branch_labels = None
depends_on = None


def _table_exists(name):
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name = :t"
    ), {"t": name})
    return result.fetchone() is not None


def _column_exists(table, column):
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = :t AND column_name = :c"
    ), {"t": table, "c": column})
    return result.fetchone() is not None


def upgrade():
    # ── PlaidAccount table ──
    if not _table_exists("plaid_accounts"):
        op.create_table(
            "plaid_accounts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("plaid_item_id", sa.Integer(),
                       sa.ForeignKey("plaid_items.id"), nullable=False),
            sa.Column("account_id", sa.String(120), nullable=False, unique=True),
            sa.Column("name", sa.String(200), server_default=""),
            sa.Column("official_name", sa.String(300), nullable=True),
            sa.Column("mask", sa.String(10), nullable=True),
            sa.Column("type", sa.String(50), server_default=""),
            sa.Column("subtype", sa.String(50), server_default=""),
            sa.Column("balance_current", sa.Float(), nullable=True),
            sa.Column("balance_available", sa.Float(), nullable=True),
            sa.Column("balance_limit", sa.Float(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_plaid_accounts_plaid_item_id",
                        "plaid_accounts", ["plaid_item_id"])

    # ── Holding enrichment columns ──
    with op.batch_alter_table("holdings") as batch_op:
        if not _column_exists("holdings", "plaid_account_id"):
            batch_op.add_column(sa.Column(
                "plaid_account_id", sa.Integer(), nullable=True))
        if not _column_exists("holdings", "security_name"):
            batch_op.add_column(sa.Column(
                "security_name", sa.String(255), nullable=True))
        if not _column_exists("holdings", "security_type"):
            batch_op.add_column(sa.Column(
                "security_type", sa.String(50), nullable=True))
        if not _column_exists("holdings", "isin"):
            batch_op.add_column(sa.Column(
                "isin", sa.String(20), nullable=True))
        if not _column_exists("holdings", "cusip"):
            batch_op.add_column(sa.Column(
                "cusip", sa.String(20), nullable=True))

    # ── BlendedAccount.source column ──
    if not _column_exists("blended_accounts", "source"):
        with op.batch_alter_table("blended_accounts") as batch_op:
            batch_op.add_column(sa.Column(
                "source", sa.String(50), server_default="manual"))

    # ── InvestmentTransaction table ──
    if not _table_exists("investment_transactions"):
        op.create_table(
            "investment_transactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(),
                       sa.ForeignKey("users.id"), nullable=False),
            sa.Column("plaid_item_id", sa.Integer(),
                       sa.ForeignKey("plaid_items.id"), nullable=True),
            sa.Column("plaid_account_id", sa.Integer(),
                       sa.ForeignKey("plaid_accounts.id"), nullable=True),
            sa.Column("investment_transaction_id", sa.String(120),
                       nullable=False, unique=True),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("type", sa.String(30), nullable=False),
            sa.Column("subtype", sa.String(50), nullable=True),
            sa.Column("ticker", sa.String(20), nullable=True),
            sa.Column("security_name", sa.String(255), nullable=True),
            sa.Column("quantity", sa.Float(), nullable=True),
            sa.Column("amount", sa.Float(), nullable=True),
            sa.Column("price", sa.Float(), nullable=True),
            sa.Column("fees", sa.Float(), nullable=True),
            sa.Column("description", sa.String(500), server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_investment_transactions_user_id",
                        "investment_transactions", ["user_id"])
        op.create_index("ix_investment_transactions_plaid_account_id",
                        "investment_transactions", ["plaid_account_id"])

    # ── TaxLot table ──
    if not _table_exists("tax_lots"):
        op.create_table(
            "tax_lots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(),
                       sa.ForeignKey("users.id"), nullable=False),
            sa.Column("holding_id", sa.Integer(),
                       sa.ForeignKey("holdings.id"), nullable=True),
            sa.Column("date_acquired", sa.Date(), nullable=False),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("cost_per_share", sa.Float(), nullable=False),
            sa.Column("investment_transaction_id", sa.Integer(),
                       sa.ForeignKey("investment_transactions.id"), nullable=True),
            sa.Column("sold_quantity", sa.Float(), server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_tax_lots_user_id", "tax_lots", ["user_id"])
        op.create_index("ix_tax_lots_holding_id", "tax_lots", ["holding_id"])


def downgrade():
    op.drop_table("tax_lots")
    op.drop_table("investment_transactions")

    with op.batch_alter_table("blended_accounts") as batch_op:
        batch_op.drop_column("source")

    with op.batch_alter_table("holdings") as batch_op:
        batch_op.drop_column("cusip")
        batch_op.drop_column("isin")
        batch_op.drop_column("security_type")
        batch_op.drop_column("security_name")
        batch_op.drop_column("plaid_account_id")

    op.drop_table("plaid_accounts")
