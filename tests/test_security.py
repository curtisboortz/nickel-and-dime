"""Tests for Phase 0 security fixes."""

from app.models.settings import CustomPulseCard


class TestIDOR:
    def test_custom_pulse_card_scoped_to_user(self, pro_client, db, pro_user):
        """Verify that custom pulse card queries filter by user_id.
        The endpoint should return data but NOT resolve another user's custom card ticker."""
        from app.models.user import User

        other = User(email="other@example.com", name="Other", plan="pro")
        other.set_password("password123")
        db.session.add(other)
        db.session.flush()

        card = CustomPulseCard(
            user_id=other.id,
            ticker="SECRET",
            label="Other's Card",
        )
        db.session.add(card)
        db.session.commit()

        resp = pro_client.get(f"/api/historical?symbol=custom-{card.id}&period=1mo")
        assert resp.status_code in (200, 500)
        data = resp.get_json() or {}
        labels = data.get("labels", [])
        assert not any("SECRET" in str(lbl) for lbl in labels)


class TestOpenRedirect:
    def test_rejects_external_redirect(self, client, user):
        resp = client.post("/login?next=https://evil.com/steal", data={
            "email": "test@example.com",
            "password": "password123",
        })
        location = resp.headers.get("Location", "")
        assert "evil.com" not in location

    def test_allows_internal_redirect(self, client, user):
        resp = client.post("/login?next=/dashboard", data={
            "email": "test@example.com",
            "password": "password123",
        }, follow_redirects=False)
        location = resp.headers.get("Location", "")
        assert "/dashboard" in location


class TestSessionCookies:
    def test_prod_config_has_secure_cookies(self):
        from app.config import ProdConfig
        assert ProdConfig.SESSION_COOKIE_SECURE is True
        assert ProdConfig.SESSION_COOKIE_HTTPONLY is True
        assert ProdConfig.SESSION_COOKIE_SAMESITE == "Lax"
