"""Tests for authentication routes."""

from app.models.user import User, Subscription


class TestRegister:
    def test_register_page_loads(self, client):
        resp = client.get("/register")
        assert resp.status_code == 200
        assert b"register" in resp.data.lower() or b"sign up" in resp.data.lower()

    def test_register_creates_user(self, client, db):
        resp = client.post("/register", data={
            "email": "new@example.com",
            "password": "securepass1",
            "name": "New User",
        }, follow_redirects=True)

        assert resp.status_code == 200
        u = User.query.filter_by(email="new@example.com").first()
        assert u is not None
        assert u.plan == "pro"

    def test_register_creates_trial(self, client, db):
        client.post("/register", data={
            "email": "trial@example.com",
            "password": "securepass1",
            "name": "Trial User",
        }, follow_redirects=True)

        u = User.query.filter_by(email="trial@example.com").first()
        sub = Subscription.query.filter_by(user_id=u.id).first()
        assert sub is not None
        assert sub.status == "trialing"

    def test_register_duplicate_email(self, client, db, user):
        resp = client.post("/register", data={
            "email": "test@example.com",
            "password": "securepass1",
            "name": "Duplicate",
        }, follow_redirects=True)

        assert b"already exists" in resp.data.lower()

    def test_register_short_password(self, client, db):
        resp = client.post("/register", data={
            "email": "short@example.com",
            "password": "abc",
            "name": "Short",
        }, follow_redirects=True)

        assert b"at least 8" in resp.data.lower()
        assert User.query.filter_by(email="short@example.com").first() is None

    def test_register_missing_fields(self, client, db):
        resp = client.post("/register", data={
            "email": "",
            "password": "",
        }, follow_redirects=True)

        assert b"required" in resp.data.lower()


class TestLogin:
    def test_login_page_loads(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200

    def test_login_valid_credentials(self, client, user):
        resp = client.post("/login", data={
            "email": "test@example.com",
            "password": "password123",
        }, follow_redirects=True)

        assert resp.status_code == 200

    def test_login_invalid_password(self, client, user):
        resp = client.post("/login", data={
            "email": "test@example.com",
            "password": "wrong",
        }, follow_redirects=True)

        assert b"invalid" in resp.data.lower()

    def test_login_nonexistent_user(self, client, db):
        resp = client.post("/login", data={
            "email": "nobody@example.com",
            "password": "password123",
        }, follow_redirects=True)

        assert b"invalid" in resp.data.lower()

    def test_login_open_redirect_blocked(self, client, user):
        resp = client.post("/login?next=https://evil.com", data={
            "email": "test@example.com",
            "password": "password123",
        })

        assert resp.status_code in (302, 303)
        assert "evil.com" not in resp.headers.get("Location", "")


class TestLogout:
    def test_logout(self, auth_client):
        resp = auth_client.get("/logout", follow_redirects=True)
        assert resp.status_code == 200

    def test_logout_requires_login(self, client):
        resp = client.get("/logout")
        assert resp.status_code in (302, 401)


class TestPasswordReset:
    def test_forgot_password_page(self, client):
        resp = client.get("/forgot-password")
        assert resp.status_code == 200

    def test_forgot_password_sets_token(self, client, user, db):
        resp = client.post("/forgot-password", data={
            "email": "test@example.com",
        }, follow_redirects=True)

        assert resp.status_code == 200
        u = db.session.get(User, user.id)
        assert u.reset_token is not None

    def test_forgot_password_unknown_email(self, client, db):
        resp = client.post("/forgot-password", data={
            "email": "nobody@example.com",
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert b"reset link" in resp.data.lower()

    def test_reset_password_valid_token(self, client, user, db):
        import secrets
        from datetime import datetime, timezone, timedelta
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        db.session.commit()

        resp = client.post(f"/reset-password/{token}", data={
            "password": "newpass123",
        }, follow_redirects=True)

        assert resp.status_code == 200
        u = db.session.get(User, user.id)
        assert u.check_password("newpass123")
        assert u.reset_token is None

    def test_reset_password_expired_token(self, client, user, db):
        import secrets
        from datetime import datetime, timezone, timedelta
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expiry = datetime.now(timezone.utc) - timedelta(hours=2)
        db.session.commit()

        resp = client.get(f"/reset-password/{token}", follow_redirects=True)
        assert b"expired" in resp.data.lower() or b"invalid" in resp.data.lower()
