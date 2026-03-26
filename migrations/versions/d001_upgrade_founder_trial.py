"""upgrade founder account to pro trial

Revision ID: d001_founder
Revises: c667a18d8e68
Create Date: 2026-03-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone, timedelta

revision = 'd001_founder'
down_revision = 'c667a18d8e68'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    row = conn.execute(
        sa.text("SELECT id, plan FROM users WHERE email = :e"),
        {"e": "crb1898@gmail.com"},
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

    if not existing:
        trial_end = datetime.now(timezone.utc) + timedelta(days=14)
        conn.execute(
            sa.text(
                "INSERT INTO subscriptions (user_id, plan, status, current_period_end, created_at) "
                "VALUES (:uid, 'pro', 'trialing', :end, :now)"
            ),
            {"uid": user_id, "end": trial_end, "now": datetime.now(timezone.utc)},
        )


def downgrade():
    pass
