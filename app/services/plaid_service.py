"""Plaid integration service.

Handles Link token creation, public token exchange, investment holdings sync,
and transaction sync.  Access tokens are encrypted at rest with Fernet.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone

import plaid
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode
from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest
from plaid.model.item_public_token_exchange_request import (
    ItemPublicTokenExchangeRequest,
)
from plaid.model.item_remove_request import ItemRemoveRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest

from ..extensions import db
from ..models.plaid import PlaidItem
from ..models.portfolio import CryptoHolding, Holding
from ..models.budget import Transaction
from ..utils.encryption import decrypt, encrypt

log = logging.getLogger(__name__)

_client: plaid_api.PlaidApi | None = None

PLAID_ENV_MAP = {
    "sandbox": plaid.Environment.Sandbox,
    "development": plaid.Environment.Development,
    "production": plaid.Environment.Production,
}

PLAID_CATEGORY_MAP = {
    "FOOD_AND_DRINK": "Food & Dining",
    "TRANSPORTATION": "Transportation",
    "TRAVEL": "Travel",
    "ENTERTAINMENT": "Entertainment",
    "GENERAL_MERCHANDISE": "Shopping",
    "GROCERIES": "Groceries",
    "RENT_AND_UTILITIES": "Bills & Utilities",
    "HOME_IMPROVEMENT": "Home",
    "MEDICAL": "Healthcare",
    "PERSONAL_CARE": "Personal Care",
    "GENERAL_SERVICES": "Services",
    "GOVERNMENT_AND_NON_PROFIT": "Government",
    "INCOME": "Income",
    "TRANSFER_IN": "Transfer",
    "TRANSFER_OUT": "Transfer",
    "LOAN_PAYMENTS": "Debt Payments",
    "BANK_FEES": "Fees & Charges",
}

CRYPTO_TICKERS = {
    "BTC", "ETH", "SOL", "ADA", "DOGE", "XRP", "XLM", "AVAX", "DOT",
    "LINK", "UNI", "AAVE", "ATOM", "LTC", "SHIB", "MATIC", "FIL",
}


def get_plaid_client() -> plaid_api.PlaidApi:
    """Return a module-level Plaid API client, creating it on first call."""
    global _client
    if _client is not None:
        return _client

    client_id = os.environ.get("PLAID_CLIENT_ID", "")
    secret = os.environ.get("PLAID_SECRET", "")
    env_name = os.environ.get("PLAID_ENV", "sandbox").lower()

    if not client_id or not secret:
        raise RuntimeError("PLAID_CLIENT_ID and PLAID_SECRET must be set")

    host = PLAID_ENV_MAP.get(env_name, plaid.Environment.Sandbox)
    configuration = plaid.Configuration(
        host=host,
        api_key={"clientId": client_id, "secret": secret, "plaidVersion": "2020-09-14"},
    )
    _client = plaid_api.PlaidApi(plaid.ApiClient(configuration))
    return _client


def create_link_token(user_id: int) -> dict:
    """Create a Plaid Link token for the given user."""
    client = get_plaid_client()
    webhook_url = os.environ.get("PLAID_WEBHOOK_URL", "")

    request_params = {
        "products": [Products("investments"), Products("transactions")],
        "client_name": "Nickel&Dime",
        "country_codes": [CountryCode("US")],
        "language": "en",
        "user": LinkTokenCreateRequestUser(client_user_id=str(user_id)),
    }
    if webhook_url:
        request_params["webhook"] = webhook_url

    req = LinkTokenCreateRequest(**request_params)
    resp = client.link_token_create(req)
    return resp.to_dict()


def exchange_public_token(user_id: int, public_token: str, metadata: dict) -> PlaidItem:
    """Exchange a public token for an access token and create a PlaidItem."""
    client = get_plaid_client()
    exchange_req = ItemPublicTokenExchangeRequest(public_token=public_token)
    exchange_resp = client.item_public_token_exchange(exchange_req)

    access_token = exchange_resp["access_token"]
    item_id = exchange_resp["item_id"]

    institution = metadata.get("institution", {})

    item = PlaidItem(
        user_id=user_id,
        item_id=item_id,
        access_token=encrypt(access_token),
        institution_id=institution.get("institution_id", ""),
        institution_name=institution.get("name", ""),
        products=["investments", "transactions"],
        status="good",
    )
    db.session.add(item)
    db.session.commit()
    return item


def remove_item(item: PlaidItem):
    """Remove a Plaid item: revoke token, delete holdings."""
    try:
        client = get_plaid_client()
        req = ItemRemoveRequest(access_token=decrypt(item.access_token))
        client.item_remove(req)
    except Exception as e:
        log.warning("Plaid item/remove failed (may already be removed): %s", e)

    Holding.query.filter_by(plaid_item_id=item.id).delete()
    src = f"plaid:{item.id}"
    CryptoHolding.query.filter_by(
        user_id=item.user_id, source=src).delete()
    Transaction.query.filter_by(
        user_id=item.user_id, source=src).delete()
    db.session.delete(item)
    db.session.commit()


def sync_investments(user_id: int, plaid_item: PlaidItem) -> dict:
    """Pull investment holdings from Plaid and upsert into Holding / CryptoHolding."""
    from .import_service import detect_bucket

    client = get_plaid_client()
    access_token = decrypt(plaid_item.access_token)

    try:
        req = InvestmentsHoldingsGetRequest(access_token=access_token)
        resp = client.investments_holdings_get(req)
    except plaid.ApiException as e:
        _handle_plaid_error(plaid_item, e)
        return {"error": str(e)}

    data = resp.to_dict()
    securities_map = {s["security_id"]: s for s in data.get("securities", [])}
    accounts_map = {a["account_id"]: a for a in data.get("accounts", [])}

    seen_tickers = set()
    seen_crypto = set()
    synced = 0

    for h in data.get("holdings", []):
        security = securities_map.get(h.get("security_id"))
        if not security:
            continue

        ticker = security.get("ticker_symbol") or ""
        if not ticker or ticker == "CUR:USD":
            continue

        quantity = h.get("quantity", 0) or 0
        cost_basis = h.get("cost_basis") or None
        account = accounts_map.get(h.get("account_id"), {})
        account_name = account.get("name", "")
        sec_type = (security.get("type") or "").lower()

        if sec_type == "cryptocurrency" or ticker.upper() in CRYPTO_TICKERS:
            sym = ticker.upper().replace("CUR:", "")
            seen_crypto.add(sym)
            source_tag = f"plaid:{plaid_item.id}"
            existing = CryptoHolding.query.filter_by(
                user_id=user_id, symbol=sym, source=source_tag
            ).first()
            if existing:
                existing.quantity = quantity
                if cost_basis is not None:
                    existing.cost_basis = cost_basis
            else:
                db.session.add(CryptoHolding(
                    user_id=user_id, symbol=sym, quantity=quantity,
                    coingecko_id=sym.lower(), cost_basis=cost_basis,
                    source=source_tag,
                ))
            synced += 1
            continue

        ticker = ticker.upper()
        seen_tickers.add((ticker, account_name))
        bucket = detect_bucket(ticker, security.get("name", ""))

        existing = Holding.query.filter_by(
            user_id=user_id, ticker=ticker, account=account_name,
            plaid_item_id=plaid_item.id,
        ).first()

        if existing:
            existing.shares = quantity
            if cost_basis is not None:
                existing.cost_basis = cost_basis
            existing.bucket = bucket
        else:
            db.session.add(Holding(
                user_id=user_id, ticker=ticker, shares=quantity,
                cost_basis=cost_basis, account=account_name,
                bucket=bucket, source="plaid", plaid_item_id=plaid_item.id,
            ))
        synced += 1

    removed = 0
    stale = Holding.query.filter_by(user_id=user_id, plaid_item_id=plaid_item.id).all()
    for h in stale:
        if (h.ticker, h.account) not in seen_tickers:
            db.session.delete(h)
            removed += 1

    source_tag = f"plaid:{plaid_item.id}"
    stale_crypto = CryptoHolding.query.filter_by(
        user_id=user_id, source=source_tag).all()
    for c in stale_crypto:
        if c.symbol not in seen_crypto:
            db.session.delete(c)
            removed += 1

    plaid_item.last_synced_at = datetime.now(timezone.utc)
    plaid_item.status = "good"
    plaid_item.error_code = None
    db.session.commit()

    log.info("Plaid investments sync user=%d item=%s: synced=%d removed=%d",
             user_id, plaid_item.item_id, synced, removed)
    return {"synced": synced, "removed": removed}


def sync_transactions(user_id: int, plaid_item: PlaidItem) -> dict:
    """Pull transactions from Plaid using cursor-based sync."""
    client = get_plaid_client()
    access_token = decrypt(plaid_item.access_token)
    cursor = plaid_item.cursor or ""
    source_tag = f"plaid:{plaid_item.id}"

    added_count = 0
    modified_count = 0
    removed_count = 0

    try:
        has_more = True
        while has_more:
            req = TransactionsSyncRequest(access_token=access_token, cursor=cursor)
            resp = client.transactions_sync(req).to_dict()
            cursor = resp.get("next_cursor", "")
            has_more = resp.get("has_more", False)

            if not cursor:
                break

            for txn in resp.get("added", []):
                _upsert_transaction(user_id, source_tag, txn)
                added_count += 1

            for txn in resp.get("modified", []):
                _upsert_transaction(user_id, source_tag, txn)
                modified_count += 1

            for txn in resp.get("removed", []):
                txn_id = txn.get("transaction_id", "")
                if txn_id:
                    h = hashlib.sha256(txn_id.encode()).hexdigest()
                    Transaction.query.filter_by(
                        user_id=user_id, source=source_tag, import_hash=h
                    ).delete()
                    removed_count += 1

    except plaid.ApiException as e:
        _handle_plaid_error(plaid_item, e)
        return {"error": str(e)}

    plaid_item.cursor = cursor
    plaid_item.last_synced_at = datetime.now(timezone.utc)
    plaid_item.status = "good"
    plaid_item.error_code = None
    db.session.commit()

    log.info("Plaid txn sync user=%d item=%s: added=%d modified=%d removed=%d",
             user_id, plaid_item.item_id, added_count, modified_count, removed_count)
    return {"added": added_count, "modified": modified_count, "removed": removed_count}


def _upsert_transaction(user_id: int, source_tag: str, txn: dict):
    """Insert or update a single Plaid transaction."""
    txn_id = txn.get("transaction_id", "")
    dedup_hash = hashlib.sha256(txn_id.encode()).hexdigest()

    amount = -(txn.get("amount") or 0)
    raw_cat = (txn.get("personal_finance_category") or {}).get("primary", "OTHER")
    category = PLAID_CATEGORY_MAP.get(raw_cat, "Other")
    txn_date = txn.get("date")
    description = txn.get("name") or txn.get("merchant_name") or ""
    account_id = txn.get("account_id", "")

    existing = Transaction.query.filter_by(
        user_id=user_id, source=source_tag, import_hash=dedup_hash
    ).first()

    if existing:
        existing.amount = amount
        existing.category = category
        existing.description = description[:500]
        existing.date = txn_date
    else:
        db.session.add(Transaction(
            user_id=user_id, date=txn_date, description=description[:500],
            amount=amount, category=category, account=account_id,
            source=source_tag, import_hash=dedup_hash,
        ))


def _handle_plaid_error(plaid_item: PlaidItem, exc: plaid.ApiException):
    """Update PlaidItem status on API error."""
    import json
    try:
        body = json.loads(exc.body)
        error_code = body.get("error_code", "UNKNOWN")
    except Exception:
        error_code = "UNKNOWN"

    plaid_item.status = "error"
    plaid_item.error_code = error_code
    db.session.commit()
    log.error("Plaid error for item %s: %s", plaid_item.item_id, error_code)


def sync_plaid_item(user_id: int, plaid_item: PlaidItem) -> dict:
    """Full sync: investments + transactions for one PlaidItem."""
    inv_result = sync_investments(user_id, plaid_item)
    txn_result = sync_transactions(user_id, plaid_item)
    return {"investments": inv_result, "transactions": txn_result}


def sync_all_plaid_items():
    """Sync all PlaidItems across all users. Called by the scheduler."""
    items = PlaidItem.query.filter(PlaidItem.status != "login_required").all()
    if not items:
        return

    for item in items:
        try:
            sync_plaid_item(item.user_id, item)
        except Exception as e:
            log.error("Plaid sync error for user %d item %s: %s",
                      item.user_id, item.item_id, e)
