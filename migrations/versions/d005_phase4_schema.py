"""Phase 4 schema: onboarding flag, referral codes, blog posts.

Revision ID: d005
Revises: d004
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa

revision = "d005"
down_revision = "d004"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.add_column(sa.Column(
            "onboarding_completed", sa.Boolean(),
            server_default=sa.text("false"),
            nullable=True,
        ))

    op.create_table(
        "referral_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(),
            sa.ForeignKey("users.id"), nullable=False,
        ),
        sa.Column(
            "code", sa.String(20),
            nullable=False, unique=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(),
            server_default=sa.func.now(),
        ),
    )
    op.create_table(
        "referral_redemptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "code_id", sa.Integer(),
            sa.ForeignKey("referral_codes.id"), nullable=False,
        ),
        sa.Column(
            "redeemed_by", sa.Integer(),
            sa.ForeignKey("users.id"), nullable=False,
        ),
        sa.Column(
            "redeemed_at", sa.DateTime(),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "credit_months", sa.Integer(),
            server_default=sa.text("1"),
        ),
    )
    op.create_index(
        "ix_referral_codes_user",
        "referral_codes", ["user_id"],
    )
    op.create_index(
        "ix_referral_redemptions_code",
        "referral_redemptions", ["code_id"],
    )

    op.create_table(
        "blog_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "slug", sa.String(200),
            nullable=False, unique=True,
        ),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column(
            "excerpt", sa.String(500), server_default="",
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "author_id", sa.Integer(),
            sa.ForeignKey("users.id"), nullable=True,
        ),
        sa.Column(
            "published", sa.Boolean(),
            server_default=sa.text("false"),
        ),
        sa.Column(
            "meta_description", sa.String(300),
            server_default="",
        ),
        sa.Column(
            "og_image", sa.String(500), server_default="",
        ),
        sa.Column(
            "created_at", sa.DateTime(),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_blog_posts_published",
        "blog_posts", ["published"],
    )


def downgrade():
    op.drop_table("blog_posts")
    op.drop_table("referral_redemptions")
    op.drop_table("referral_codes")
    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.drop_column("onboarding_completed")
