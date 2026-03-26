"""Coinbase Advanced Trade API integration.

Fetches live balances from a user's Coinbase account and syncs them
into the crypto_holdings table.  Keys are stored per-user in user_settings.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..extensions import db
from ..models.portfolio import CryptoHolding
from ..models.settings import UserSettings

log = logging.getLogger(__name__)

COINGECKO_MAP = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
    "ADA": "cardano", "DOGE": "dogecoin", "XRP": "ripple",
    "XLM": "stellar", "XTZ": "tezos", "USDC": "usd-coin",
    "DAI": "dai", "GRT": "the-graph", "AMP": "amp-token",
    "CBETH": "coinbase-wrapped-staked-eth", "VARA": "vara-network",
    "VET": "vechain", "MLN": "enzyme", "SKL": "skale",
    "RLY": "rally-2", "CLV": "clover-finance", "AVAX": "avalanche-2",
    "MATIC": "matic-network", "DOT": "polkadot", "LINK": "chainlink",
    "UNI": "uniswap", "AAVE": "aave", "ATOM": "cosmos",
    "LTC": "litecoin", "SHIB": "shiba-inu", "FIL": "filecoin",
    "NEAR": "near", "APT": "aptos", "ARB": "arbitrum",
    "OP": "optimism", "SUI": "sui", "SEI": "sei-network",
}


def fetch_coinbase_balances(
    api_key_name: str,
    private_key_pem: str,
) -> Optional[list[dict]]:
    """Fetch crypto balances from Coinbase Advanced Trade API.

    Returns list of {"symbol": "BTC", "qty": 0.5} or None on failure.
    """
    if not (api_key_name and api_key_name.strip()
            and private_key_pem and private_key_pem.strip()):
        return None

    key_pem = private_key_pem.strip()
    if "\\n" in key_pem:
        key_pem = key_pem.replace("\\n", "\n")

    try:
        from coinbase.rest import RESTClient

        client = RESTClient(api_key=api_key_name.strip(), api_secret=key_pem)
        out: list[dict] = []
        cursor = None

        while True:
            resp = client.get_accounts(limit=250, cursor=cursor)
            if hasattr(resp, "get"):
                accounts = resp.get("accounts", [])
                cursor = resp.get("cursor")
                has_next = resp.get("has_next", False)
            else:
                accounts = getattr(resp, "accounts", []) or []
                cursor = getattr(resp, "cursor", None)
                has_next = getattr(resp, "has_next", False)

            for acc in accounts:
                if hasattr(acc, "get"):
                    currency = acc.get("currency", "")
                    bal = acc.get("available_balance") or acc.get("balance") or {}
                    val = bal.get("value") if isinstance(bal, dict) else getattr(bal, "value", None)
                else:
                    currency = getattr(acc, "currency", "")
                    bal = getattr(acc, "available_balance", None) or getattr(acc, "balance", None)
                    val = (bal.get("value") if isinstance(bal, dict)
                           else (getattr(bal, "value", None) if bal else None))

                if not currency or currency.upper() == "USD":
                    continue
                try:
                    qty = float(val) if val is not None else 0.0
                except (TypeError, ValueError):
                    qty = 0.0
                if qty > 0:
                    out.append({"symbol": currency.upper(), "qty": qty})

            if not has_next or not cursor:
                break

        return out if out else None
    except Exception as e:
        log.error("Coinbase fetch error: %s", e)
        return None


def sync_user_coinbase(user_id: int) -> dict:
    """Sync a single user's Coinbase balances into crypto_holdings.

    Returns {"synced": N, "removed": M} or {"error": "..."}.
    """
    settings = UserSettings.query.filter_by(user_id=user_id).first()
    if not settings or not settings.coinbase_key_name or not settings.coinbase_private_key:
        return {"error": "No Coinbase API keys configured"}

    balances = fetch_coinbase_balances(
        settings.coinbase_key_name,
        settings.coinbase_private_key,
    )
    if balances is None:
        return {"error": "Failed to fetch Coinbase balances. Check your API keys."}

    cb_symbols = set()
    synced = 0

    for item in balances:
        sym = item["symbol"]
        qty = item["qty"]
        cb_symbols.add(sym)

        existing = CryptoHolding.query.filter_by(
            user_id=user_id, symbol=sym,
        ).first()

        cg_id = COINGECKO_MAP.get(sym, sym.lower())

        if existing:
            existing.quantity = qty
            existing.coingecko_id = cg_id
            existing.source = "coinbase"
        else:
            db.session.add(CryptoHolding(
                user_id=user_id,
                symbol=sym,
                quantity=qty,
                coingecko_id=cg_id,
                source="coinbase",
            ))
        synced += 1

    removed = 0
    old_cb = CryptoHolding.query.filter_by(
        user_id=user_id, source="coinbase",
    ).all()
    for h in old_cb:
        if h.symbol not in cb_symbols:
            db.session.delete(h)
            removed += 1

    db.session.commit()
    log.info("Coinbase sync for user %d: synced=%d removed=%d", user_id, synced, removed)
    return {"synced": synced, "removed": removed}


def sync_all_coinbase_users():
    """Sync Coinbase balances for every user who has keys stored.

    Called by the background scheduler.
    """
    users_with_keys = (
        UserSettings.query
        .filter(
            UserSettings.coinbase_key_name.isnot(None),
            UserSettings.coinbase_key_name != "",
            UserSettings.coinbase_private_key.isnot(None),
            UserSettings.coinbase_private_key != "",
        )
        .all()
    )
    if not users_with_keys:
        return

    for settings in users_with_keys:
        try:
            result = sync_user_coinbase(settings.user_id)
            if "error" in result:
                log.warning("Coinbase sync failed for user %d: %s",
                            settings.user_id, result["error"])
        except Exception as e:
            log.error("Coinbase sync error for user %d: %s", settings.user_id, e)
