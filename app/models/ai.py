"""AI Advisor models — conversations, messages, and usage tracking."""

from datetime import datetime, date, timezone
from ..extensions import db


class AIConversation(db.Model):
    """A multi-turn AI advisor conversation."""
    __tablename__ = "ai_conversations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"),
        nullable=False, index=True,
    )
    title = db.Column(db.String(200), default="New conversation")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    messages = db.relationship(
        "AIMessage", backref="conversation",
        cascade="all, delete-orphan",
        order_by="AIMessage.created_at",
    )


class AIMessage(db.Model):
    """A single message in an AI conversation."""
    __tablename__ = "ai_messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey("ai_conversations.id"),
        nullable=False, index=True,
    )
    role = db.Column(db.String(20), nullable=False)  # user | assistant | system
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc),
    )


class AIUsage(db.Model):
    """Daily AI query counter per user for rate limiting."""
    __tablename__ = "ai_usage"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"),
        nullable=False, index=True,
    )
    date = db.Column(db.Date, nullable=False, default=date.today)
    query_count = db.Column(db.Integer, default=0)

    __table_args__ = (
        db.UniqueConstraint("user_id", "date", name="uq_ai_usage_user_date"),
    )
