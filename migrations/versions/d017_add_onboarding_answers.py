"""Add onboarding_answers JSON column to user_settings.

Stores the raw wizard survey responses (experience, interests, risk, allocation
preset, monthly contribution) so we can re-personalize later without re-asking.

Revision ID: d017
Revises: d016
"""
from alembic import op
import sqlalchemy as sa

revision = "d017"
down_revision = "d016"
branch_labels = None
depends_on = None


def _column_exists(table, column):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in [c["name"] for c in insp.get_columns(table)]


def upgrade():
    if not _column_exists("user_settings", "onboarding_answers"):
        with op.batch_alter_table("user_settings") as batch_op:
            batch_op.add_column(
                sa.Column("onboarding_answers", sa.JSON(), nullable=True)
            )


def downgrade():
    if _column_exists("user_settings", "onboarding_answers"):
        with op.batch_alter_table("user_settings") as batch_op:
            batch_op.drop_column("onboarding_answers")
