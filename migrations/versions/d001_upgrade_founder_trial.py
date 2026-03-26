"""upgrade founder account to permanent pro

Revision ID: d001_founder
Revises: c667a18d8e68
Create Date: 2026-03-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

revision = 'd001_founder'
down_revision = 'c667a18d8e68'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Drop is_admin column if it exists from a previous partial migration
    try:
        conn.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS is_admin"))
    except Exception:
        pass

    row = conn.execute(
        sa.text("SELECT id FROM users WHERE email = 'crb1898@gmail.com'")
    ).fetchone()

    if not row:
        return

    user_id = row[0]

    conn.execute(
        sa.text("UPDATE users SET plan = 'pro' WHERE id = :uid"),
        {"uid": user_id},
    )

    existing = conn.execute(
        sa.text("SELECT id FROM subscriptions WHERE user_id = :uid"),
        {"uid": user_id},
    ).fetchone()

    now = datetime.now(timezone.utc)

    if existing:
        conn.execute(
            sa.text(
                "UPDATE subscriptions SET plan = 'pro', status = 'active', "
                "current_period_end = NULL, updated_at = :now WHERE user_id = :uid"
            ),
            {"uid": user_id, "now": now},
        )
    else:
        conn.execute(
            sa.text(
                "INSERT INTO subscriptions (user_id, plan, status, current_period_end, created_at) "
                "VALUES (:uid, 'pro', 'active', NULL, :now)"
            ),
            {"uid": user_id, "now": now},
        )


def downgrade():
    pass
