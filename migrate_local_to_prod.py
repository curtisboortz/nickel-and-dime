"""Migrate local JSON data (config.json, price_history.json) to production PostgreSQL.

Usage:
    set DATABASE_URL=postgresql://...
    python migrate_local_to_prod.py

This script is READ-ONLY on local files (never modifies them).
It inserts data under the user account matching ADMIN_EMAIL (default crb1898@gmail.com).
"""

import json
import os
import sys
from datetime import datetime, timezone

TARGET_EMAIL = os.environ.get("ADMIN_EMAIL", "crb1898@gmail.com")
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: Set DATABASE_URL environment variable to your production PostgreSQL URL.")
    print("  Example: set DATABASE_URL=postgresql://user:pass@host:port/dbname")
    sys.exit(1)

from sqlalchemy import create_engine, text

engine = create_engine(DATABASE_URL)


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def main():
    config = load_json("config.json")
    price_history = load_json("price_history.json")

    with engine.connect() as conn:
        # Find user
        row = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": TARGET_EMAIL}).fetchone()
        if not row:
            print(f"ERROR: User {TARGET_EMAIL} not found in production DB.")
            sys.exit(1)
        user_id = row[0]
        print(f"Found user {TARGET_EMAIL} (id={user_id})")

        # --- Holdings ---
        existing_holdings = conn.execute(
            text("SELECT COUNT(*) FROM holdings WHERE user_id = :uid"), {"uid": user_id}
        ).scalar()
        if existing_holdings > 0:
            print(f"  Holdings: {existing_holdings} already exist, skipping (delete manually to re-import)")
        else:
            holdings = config.get("holdings", [])
            for h in holdings:
                conn.execute(text(
                    "INSERT INTO holdings (user_id, ticker, shares, bucket, account, value_override, notes) "
                    "VALUES (:uid, :ticker, :shares, :bucket, :account, :vo, :notes)"
                ), {
                    "uid": user_id,
                    "ticker": h.get("ticker", ""),
                    "shares": h.get("qty"),
                    "bucket": h.get("asset_class", ""),
                    "account": h.get("account", ""),
                    "vo": h.get("value_override"),
                    "notes": h.get("notes", ""),
                })
            print(f"  Holdings: inserted {len(holdings)} rows")

        # --- Blended Accounts ---
        existing_blended = conn.execute(
            text("SELECT COUNT(*) FROM blended_accounts WHERE user_id = :uid"), {"uid": user_id}
        ).scalar()
        if existing_blended > 0:
            print(f"  Blended accounts: {existing_blended} already exist, skipping")
        else:
            blended = config.get("blended_accounts", [])
            for b in blended:
                conn.execute(text(
                    "INSERT INTO blended_accounts (user_id, name, value, allocations) "
                    "VALUES (:uid, :name, :value, :alloc)"
                ), {
                    "uid": user_id,
                    "name": b.get("name", ""),
                    "value": b.get("value", 0),
                    "alloc": json.dumps({"asset_class": b.get("asset_class", "")}),
                })
            print(f"  Blended accounts: inserted {len(blended)} rows")

        # --- Crypto Holdings ---
        existing_crypto = conn.execute(
            text("SELECT COUNT(*) FROM crypto_holdings WHERE user_id = :uid"), {"uid": user_id}
        ).scalar()
        if existing_crypto > 0:
            print(f"  Crypto holdings: {existing_crypto} already exist, skipping")
        else:
            # Map common symbols to CoinGecko IDs
            cg_map = {
                "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
                "ADA": "cardano", "DOGE": "dogecoin", "XRP": "ripple",
                "XLM": "stellar", "XTZ": "tezos", "USDC": "usd-coin",
                "DAI": "dai", "GRT": "the-graph", "AMP": "amp-token",
                "CBETH": "coinbase-wrapped-staked-eth", "VARA": "vara-network",
                "VET": "vechain", "MLN": "enzyme", "SKL": "skale",
                "RLY": "rally-2", "CLV": "clover-finance",
            }
            crypto = config.get("crypto_holdings", [])
            for c in crypto:
                sym = c.get("symbol", "")
                conn.execute(text(
                    "INSERT INTO crypto_holdings (user_id, symbol, quantity, coingecko_id) "
                    "VALUES (:uid, :sym, :qty, :cgid)"
                ), {
                    "uid": user_id,
                    "sym": sym,
                    "qty": c.get("qty", 0),
                    "cgid": cg_map.get(sym, sym.lower()),
                })
            print(f"  Crypto holdings: inserted {len(crypto)} rows")

        # --- Physical Metals ---
        existing_metals = conn.execute(
            text("SELECT COUNT(*) FROM physical_metals WHERE user_id = :uid"), {"uid": user_id}
        ).scalar()
        if existing_metals > 0:
            print(f"  Physical metals: {existing_metals} already exist, skipping")
        else:
            metals = config.get("physical_metals", [])
            for m in metals:
                conn.execute(text(
                    "INSERT INTO physical_metals (user_id, metal, form, oz, purchase_price, description, date, note) "
                    "VALUES (:uid, :metal, :form, :oz, :price, :desc, :date, :note)"
                ), {
                    "uid": user_id,
                    "metal": m.get("metal", "Gold"),
                    "form": m.get("form", ""),
                    "oz": m.get("qty_oz", 0),
                    "price": m.get("cost_per_oz", 0),
                    "desc": m.get("note", ""),
                    "date": m.get("date", ""),
                    "note": m.get("note", ""),
                })
            print(f"  Physical metals: inserted {len(metals)} rows")

        # --- Portfolio Snapshots ---
        existing_snaps = conn.execute(
            text("SELECT COUNT(*) FROM portfolio_snapshots WHERE user_id = :uid"), {"uid": user_id}
        ).scalar()
        if existing_snaps > 0:
            print(f"  Snapshots: {existing_snaps} already exist, skipping")
        else:
            history = price_history.get("history", [])
            for h in history:
                conn.execute(text(
                    "INSERT INTO portfolio_snapshots (user_id, date, total, open_val, high, low, close, gold_price, silver_price) "
                    "VALUES (:uid, :date, :total, :open, :high, :low, :close, :gold, :silver)"
                ), {
                    "uid": user_id,
                    "date": h.get("date"),
                    "total": h.get("total", 0),
                    "open": h.get("open", 0),
                    "high": h.get("high", 0),
                    "low": h.get("low", 0),
                    "close": h.get("close", 0),
                    "gold": h.get("gold"),
                    "silver": h.get("silver"),
                })
            print(f"  Snapshots: inserted {len(history)} rows")

        # --- User Settings (pulse order, custom cards) ---
        settings = conn.execute(
            text("SELECT id FROM user_settings WHERE user_id = :uid"), {"uid": user_id}
        ).fetchone()
        pulse_order = config.get("pulse_card_order", [])
        if settings:
            conn.execute(text(
                "UPDATE user_settings SET pulse_order = :po WHERE user_id = :uid"
            ), {"uid": user_id, "po": json.dumps(pulse_order)})
            print(f"  Settings: updated pulse_order")
        else:
            conn.execute(text(
                "INSERT INTO user_settings (user_id, pulse_order) VALUES (:uid, :po)"
            ), {"uid": user_id, "po": json.dumps(pulse_order)})
            print(f"  Settings: inserted with pulse_order")

        # --- Custom Pulse Cards ---
        existing_custom = conn.execute(
            text("SELECT COUNT(*) FROM custom_pulse_cards WHERE user_id = :uid"), {"uid": user_id}
        ).scalar()
        if existing_custom == 0:
            custom = config.get("custom_pulse_cards", [])
            for c in custom:
                conn.execute(text(
                    "INSERT INTO custom_pulse_cards (user_id, ticker, label, card_type) "
                    "VALUES (:uid, :ticker, :label, :ctype)"
                ), {
                    "uid": user_id,
                    "ticker": c.get("ticker", ""),
                    "label": c.get("label", ""),
                    "ctype": c.get("type", "stock"),
                })
            print(f"  Custom pulse cards: inserted {len(custom)} rows")

        # --- Budget Config ---
        existing_budget = conn.execute(
            text("SELECT COUNT(*) FROM budget_configs WHERE user_id = :uid"), {"uid": user_id}
        ).scalar()
        if existing_budget == 0:
            budget = config.get("budget", {})
            if budget:
                conn.execute(text(
                    "INSERT INTO budget_configs (user_id, monthly_income, categories, month) "
                    "VALUES (:uid, :income, :cats, :month)"
                ), {
                    "uid": user_id,
                    "income": budget.get("monthly_income", 0),
                    "cats": json.dumps(budget.get("categories", [])),
                    "month": budget.get("month", ""),
                })
                print(f"  Budget config: inserted")

        conn.commit()
        print("\nMigration complete!")


if __name__ == "__main__":
    main()
