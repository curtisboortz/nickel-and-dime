"""Shared pytest fixtures for the Nickel&Dime test suite."""

import os
import pytest

os.environ.setdefault("FLASK_ENV", "test")

from app import create_app
from app.extensions import db as _db
from app.models.user import User, Subscription


@pytest.fixture(scope="session")
def app():
    """Create application for the entire test session."""
    application = create_app("test")
    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture(scope="function")
def db(app):
    """Provide a clean DB for each test function."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.rollback()
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture
def client(app, db):
    """Flask test client with active app context."""
    with app.test_client() as c:
        with app.app_context():
            yield c


@pytest.fixture
def user(db):
    """Create a default free-tier user."""
    u = User(email="test@example.com", name="Test User", plan="free")
    u.set_password("password123")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def pro_user(db):
    """Create a Pro user with an active subscription."""
    u = User(email="pro@example.com", name="Pro User", plan="pro")
    u.set_password("password123")
    db.session.add(u)
    db.session.flush()

    from datetime import datetime, timezone, timedelta
    sub = Subscription(
        user_id=u.id,
        plan="pro",
        status="trialing",
        current_period_end=datetime.now(timezone.utc) + timedelta(days=14),
    )
    db.session.add(sub)
    db.session.commit()
    return u


@pytest.fixture
def auth_client(client, user):
    """Test client logged in as the free user."""
    client.post("/login", data={
        "email": "test@example.com",
        "password": "password123",
    }, follow_redirects=True)
    return client


@pytest.fixture
def pro_client(client, pro_user):
    """Test client logged in as the Pro user."""
    client.post("/login", data={
        "email": "pro@example.com",
        "password": "password123",
    }, follow_redirects=True)
    return client
