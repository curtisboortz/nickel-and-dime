"""drop unused goldapi_key column from user_settings

Revision ID: cb79b44358dc
Revises: d015
Create Date: 2026-04-13 21:45:01.614959

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cb79b44358dc'
down_revision = 'd015'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user_settings', schema=None) as batch_op:
        batch_op.drop_column('goldapi_key')


def downgrade():
    with op.batch_alter_table('user_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('goldapi_key', sa.VARCHAR(length=255), nullable=True))
