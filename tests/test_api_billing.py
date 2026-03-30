"""Tests for billing API routes."""

from app.models.user import Subscription


class TestSubscriptionStatus:
    def test_status_requires_login(self, client):
        resp = client.get("/api/subscription-status")
        assert resp.status_code in (302, 401)

    def test_status_free_user(self, auth_client, user):
        resp = auth_client.get("/api/subscription-status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["plan"] == "free"

    def test_status_pro_user(self, pro_client, pro_user):
        resp = pro_client.get("/api/subscription-status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["plan"] == "pro"
        assert data["status"] == "trialing"
        assert data["trial_end"] is not None


class TestCheckout:
    def test_checkout_requires_login(self, client):
        resp = client.post("/api/create-checkout")
        assert resp.status_code in (302, 401)

    def test_checkout_no_stripe_config(self, auth_client, app):
        app.config["STRIPE_SECRET_KEY"] = ""
        resp = auth_client.post("/api/create-checkout")
        assert resp.status_code == 503

    def test_checkout_already_pro(self, pro_client, app):
        app.config["STRIPE_SECRET_KEY"] = "sk_test_fake"
        app.config["STRIPE_PRO_PRICE_ID"] = "price_fake"
        resp = pro_client.post("/api/create-checkout")
        assert resp.status_code == 400


class TestTrialDetection:
    def test_app_trial_does_not_block_stripe_trial(self, db, user):
        """The app-created trial (no stripe_subscription_id) should not
        prevent a Stripe checkout from including a trial period."""
        sub = Subscription(
            user_id=user.id,
            plan="pro",
            status="trialing",
            stripe_subscription_id=None,
        )
        db.session.add(sub)
        db.session.commit()

        had_stripe_trial = Subscription.query.filter_by(
            user_id=user.id
        ).filter(Subscription.stripe_subscription_id.isnot(None)).first()

        assert had_stripe_trial is None
