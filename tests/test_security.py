"""Tests for security fixes and IDOR coverage."""

from datetime import date

from app.models.settings import CustomPulseCard, WatchlistItem, PriceAlert, FinancialGoal
from app.models.user import User, Subscription
from app.models.ai import AIConversation
from app.models.budget import Transaction
from app.models.portfolio import Holding
from app.models.plaid import PlaidItem


def _create_other_pro_user(db):
    """Helper: create a second pro user for IDOR tests."""
    other = User(email="other@example.com", name="Other", plan="pro")
    other.set_password("password123")
    db.session.add(other)
    db.session.flush()
    from datetime import datetime, timezone, timedelta
    sub = Subscription(
        user_id=other.id, plan="pro", status="trialing",
        current_period_end=datetime.now(timezone.utc) + timedelta(days=14),
    )
    db.session.add(sub)
    db.session.flush()
    return other


class TestIDOR:
    def test_custom_pulse_card_scoped_to_user(self, pro_client, db, pro_user):
        """Verify that custom pulse card queries filter by user_id.
        The endpoint should return data but NOT resolve another user's custom card ticker."""
        other = _create_other_pro_user(db)

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

    def test_cannot_read_other_users_ai_conversation(self, pro_client, db, pro_user):
        other = _create_other_pro_user(db)
        conv = AIConversation(user_id=other.id, title="Secret Chat")
        db.session.add(conv)
        db.session.commit()

        resp = pro_client.get(f"/api/ai/conversations/{conv.id}")
        assert resp.status_code == 404

    def test_cannot_delete_other_users_ai_conversation(self, pro_client, db, pro_user):
        other = _create_other_pro_user(db)
        conv = AIConversation(user_id=other.id, title="Secret Chat")
        db.session.add(conv)
        db.session.commit()

        resp = pro_client.delete(f"/api/ai/conversations/{conv.id}")
        assert resp.status_code == 404
        assert db.session.get(AIConversation, conv.id) is not None

    def test_cannot_delete_other_users_transaction(self, pro_client, db, pro_user):
        other = _create_other_pro_user(db)
        txn = Transaction(
            user_id=other.id, date=date(2025, 1, 1),
            description="Secret", amount=-50.0, category="Other",
        )
        db.session.add(txn)
        db.session.commit()

        resp = pro_client.delete(f"/api/transactions/{txn.id}")
        assert resp.status_code == 200
        assert db.session.get(Transaction, txn.id) is not None

    def test_cannot_delete_other_users_holding(self, pro_client, db, pro_user):
        other = _create_other_pro_user(db)
        h = Holding(user_id=other.id, ticker="AAPL", shares=10, account="Brokerage")
        db.session.add(h)
        db.session.commit()

        resp = pro_client.delete(f"/api/holdings/{h.id}")
        assert resp.status_code == 200
        assert db.session.get(Holding, h.id) is not None

    def test_cannot_delete_other_users_plaid_account(self, pro_client, db, pro_user):
        other = _create_other_pro_user(db)
        item = PlaidItem(
            user_id=other.id, item_id="test_item_other",
            access_token="tok_other", institution_name="OtherBank",
        )
        db.session.add(item)
        db.session.commit()

        resp = pro_client.delete(f"/api/plaid/accounts/{item.id}")
        assert resp.status_code == 404
        assert db.session.get(PlaidItem, item.id) is not None

    def test_cannot_sync_other_users_plaid_item(self, pro_client, db, pro_user):
        other = _create_other_pro_user(db)
        item = PlaidItem(
            user_id=other.id, item_id="test_item_sync",
            access_token="tok_sync", institution_name="OtherBank",
        )
        db.session.add(item)
        db.session.commit()

        resp = pro_client.post(f"/api/plaid/sync/{item.id}")
        assert resp.status_code == 404

    def test_cannot_delete_other_users_watchlist_item(self, pro_client, db, pro_user):
        other = _create_other_pro_user(db)
        item = WatchlistItem(user_id=other.id, ticker="SPY", label="S&P 500")
        db.session.add(item)
        db.session.commit()

        resp = pro_client.delete(f"/api/watchlist/{item.id}")
        assert resp.status_code == 404
        assert db.session.get(WatchlistItem, item.id) is not None

    def test_cannot_delete_other_users_price_alert(self, pro_client, db, pro_user):
        other = _create_other_pro_user(db)
        alert = PriceAlert(
            user_id=other.id, ticker="AAPL",
            condition="above", target_price=200.0,
        )
        db.session.add(alert)
        db.session.commit()

        resp = pro_client.delete(f"/api/price-alerts/{alert.id}")
        assert resp.status_code == 404
        assert db.session.get(PriceAlert, alert.id) is not None

    def test_cannot_delete_other_users_goal(self, pro_client, db, pro_user):
        other = _create_other_pro_user(db)
        goal = FinancialGoal(
            user_id=other.id, name="Secret Goal", target_amount=10000.0,
        )
        db.session.add(goal)
        db.session.commit()

        resp = pro_client.delete(f"/api/goals/{goal.id}")
        assert resp.status_code == 404
        assert db.session.get(FinancialGoal, goal.id) is not None


class TestAdminForbidden:
    def test_admin_endpoint_forbidden_for_non_admin(self, pro_client, db, pro_user):
        """Non-admin users cannot access admin promo-code deletion."""
        from app.models.user import PromoCode
        promo = PromoCode(code="TESTCODE", trial_days=14, active=True)
        db.session.add(promo)
        db.session.commit()

        resp = pro_client.delete(f"/api/admin/promo-codes/{promo.id}")
        assert resp.status_code == 403
        assert db.session.get(PromoCode, promo.id).active is True


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
