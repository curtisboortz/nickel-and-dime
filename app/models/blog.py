"""Blog post model."""

from datetime import datetime, timezone
from ..extensions import db


class BlogPost(db.Model):
    __tablename__ = "blog_posts"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(
        db.String(200), nullable=False, unique=True,
    )
    title = db.Column(db.String(300), nullable=False)
    excerpt = db.Column(db.String(500), default="")
    body = db.Column(db.Text, nullable=False)
    author_id = db.Column(
        db.Integer, db.ForeignKey("users.id"),
        nullable=True,
    )
    published = db.Column(db.Boolean, default=False)
    meta_description = db.Column(
        db.String(300), default="",
    )
    og_image = db.Column(db.String(500), default="")
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
