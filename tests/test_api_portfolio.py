"""Tests for portfolio API routes."""

import json

from app.models.portfolio import Holding, CryptoHolding, PhysicalMetal, BlendedAccount
from app.models.market import PriceCache


class TestHoldings:
    def test_holdings_requires_login(self, client):
        resp = client.get("/api/holdings")
        assert resp.status_code in (302, 401, 403)

    def test_holdings_requires_pro(self, auth_client, db, user):
        resp = auth_client.get("/api/holdings")
        assert resp.status_code == 403

    def test_holdings_returns_data(self, pro_client, db, pro_user):
        h = Holding(user_id=pro_user.id, ticker="AAPL", shares=10.0, bucket="Equities")
        db.session.add(h)
        PriceCache.query.filter_by(symbol="AAPL").delete()
        p = PriceCache(symbol="AAPL", price=175.0, source="yfinance")
        db.session.add(p)
        db.session.commit()

        resp = pro_client.get("/api/holdings")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "holdings" in data
        found = [x for x in data["holdings"] if x["ticker"] == "AAPL"]
        assert len(found) == 1
        assert found[0]["shares"] == 10.0


class TestBalances:
    def test_balances_accessible_to_free(self, auth_client, db, user):
        b = BlendedAccount(user_id=user.id, name="Savings", value=1000.0, allocations={})
        db.session.add(b)
        db.session.commit()

        resp = auth_client.get("/api/balances")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "accounts" in data
        assert len(data["accounts"]) == 1

    def test_add_balance(self, auth_client, db, user):
        resp = auth_client.post("/api/balances", json={
            "new_account": {
                "name": "Emergency Fund",
                "value": 5000,
                "allocations": {"Cash": 100},
            },
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("success") is True

    def test_update_balance_value(self, auth_client, db, user):
        b = BlendedAccount(user_id=user.id, name="Old Name", value=100.0, allocations={})
        db.session.add(b)
        db.session.commit()

        resp = auth_client.post("/api/balances", json={
            "updates": {str(b.id): {"value": 500}},
        })
        assert resp.status_code == 200

    def test_delete_balance(self, auth_client, db, user):
        b = BlendedAccount(user_id=user.id, name="ToDelete", value=100.0, allocations={})
        db.session.add(b)
        db.session.commit()
        bid = b.id

        resp = auth_client.delete(f"/api/balances/{bid}")
        assert resp.status_code == 200
        assert db.session.get(BlendedAccount, bid) is None


class TestAllocationTargets:
    def test_get_targets(self, auth_client, db, user):
        resp = auth_client.get("/api/allocation-targets")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "rows" in data


class TestTaxLossHarvesting:
    def test_tlh_returns_losses(self, auth_client, db, user):
        user.plan = "free"
        db.session.commit()

        h = Holding(
            user_id=user.id,
            ticker="LOSS",
            shares=100.0,
            cost_basis=200.0,
            bucket="Equities",
        )
        db.session.add(h)
        p = PriceCache(symbol="LOSS", price=100.0, source="yfinance")
        db.session.add(p)
        db.session.commit()

        resp = auth_client.get("/api/tax-loss-harvesting")
        assert resp.status_code == 200
        data = resp.get_json()
        rows = data.get("rows", [])
        assert len(rows) >= 1
        assert rows[0]["ticker"] == "LOSS"
        assert rows[0]["unrealized"] < 0

    def test_tlh_skips_small_losses(self, auth_client, db, user):
        h = Holding(
            user_id=user.id,
            ticker="SMALL",
            shares=1.0,
            cost_basis=102.0,
            bucket="Equities",
        )
        db.session.add(h)
        p = PriceCache(symbol="SMALL", price=100.0, source="yfinance")
        db.session.add(p)
        db.session.commit()

        resp = auth_client.get("/api/tax-loss-harvesting")
        data = resp.get_json()
        tickers = [r["ticker"] for r in data.get("rows", [])]
        assert "SMALL" not in tickers
