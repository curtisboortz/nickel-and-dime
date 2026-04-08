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
from plaid.model.institutions_get_by_id_request import (
    InstitutionsGetByIdRequest,
)
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import (
    LinkTokenCreateRequestUser,
)
from plaid.model.products import Products
from plaid.model.investments_transactions_get_request import (
    InvestmentsTransactionsGetRequest,
)
from plaid.model.transactions_sync_request import TransactionsSyncRequest

from ..extensions import db
from ..models.plaid import PlaidItem, PlaidAccount
from ..models.portfolio import (
    CryptoHolding, Holding, BlendedAccount,
    InvestmentTransaction, TaxLot,
)
from ..models.budget import Transaction
from ..utils.encryption import decrypt, encrypt

log = logging.getLogger(__name__)

_client: plaid_api.PlaidApi | None = None

PLAID_ENV_MAP = {
    "sandbox": plaid.Environment.Sandbox,
    "development": plaid.Environment.Sandbox,
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

    inst_id = institution.get("institution_id", "")
    item = PlaidItem(
        user_id=user_id,
        item_id=item_id,
        access_token=encrypt(access_token),
        institution_id=inst_id,
        institution_name=institution.get("name", ""),
        products=["investments", "transactions"],
        status="good",
    )

    if inst_id:
        try:
            branding = _fetch_institution_branding(client, inst_id)
            item.logo_base64 = branding.get("logo")
            item.primary_color = branding.get("primary_color", "")
        except Exception as e:
            log.warning("Could not fetch branding for %s: %s", inst_id, e)

    db.session.add(item)
    db.session.commit()
    return item


def _fetch_institution_branding(
    client: plaid_api.PlaidApi, institution_id: str
) -> dict:
    """Fetch name, logo, and primary_color from Plaid for an institution."""
    req = InstitutionsGetByIdRequest(
        institution_id=institution_id,
        country_codes=[CountryCode("US")],
        options={"include_optional_metadata": True},
    )
    resp = client.institutions_get_by_id(req).to_dict()
    inst = resp.get("institution", {})
    return {
        "name": inst.get("name", ""),
        "logo": inst.get("logo"),
        "primary_color": inst.get("primary_color", ""),
    }


def remove_item(item: PlaidItem):
    """Remove a Plaid item: revoke token, delete holdings and related data."""
    try:
        client = get_plaid_client()
        req = ItemRemoveRequest(access_token=decrypt(item.access_token))
        client.item_remove(req)
    except Exception as e:
        log.warning("Plaid item/remove failed (may already be removed): %s", e)

    for h in Holding.query.filter_by(plaid_item_id=item.id).all():
        TaxLot.query.filter_by(holding_id=h.id).delete()
    InvestmentTransaction.query.filter_by(plaid_item_id=item.id).delete()
    Holding.query.filter_by(plaid_item_id=item.id).delete()

    src = f"plaid:{item.id}"
    CryptoHolding.query.filter_by(
        user_id=item.user_id, source=src).delete()
    Transaction.query.filter_by(
        user_id=item.user_id, source=src).delete()

    for pa in PlaidAccount.query.filter_by(plaid_item_id=item.id).all():
        bal_src = f"plaid:{item.id}:{pa.account_id}"
        BlendedAccount.query.filter_by(
            user_id=item.user_id, source=bal_src).delete()

    PlaidAccount.query.filter_by(plaid_item_id=item.id).delete()
    db.session.delete(item)
    db.session.commit()


def _backfill_branding_if_needed(client, plaid_item: PlaidItem):
    """Fetch institution branding for PlaidItems that are missing name or logo."""
    if not plaid_item.institution_id:
        return
    needs_name = not plaid_item.institution_name
    needs_logo = not getattr(plaid_item, "logo_base64", None)
    if not needs_name and not needs_logo:
        return
    try:
        branding = _fetch_institution_branding(client, plaid_item.institution_id)
        if needs_name and branding.get("name"):
            plaid_item.institution_name = branding["name"]
        if needs_logo and branding.get("logo"):
            plaid_item.logo_base64 = branding["logo"]
        if branding.get("primary_color"):
            plaid_item.primary_color = branding["primary_color"]
    except Exception as e:
        log.warning("Branding backfill failed for %s: %s", plaid_item.institution_id, e)


def _upsert_plaid_accounts(plaid_item: PlaidItem, accounts_map: dict) -> dict:
    """Upsert PlaidAccount rows and return {plaid_account_id_str: PlaidAccount.id}."""
    id_map = {}
    for acct_id, acct_data in accounts_map.items():
        pa = PlaidAccount.query.filter_by(account_id=acct_id).first()
        if not pa:
            pa = PlaidAccount(
                plaid_item_id=plaid_item.id,
                account_id=acct_id,
            )
            db.session.add(pa)

        pa.name = acct_data.get("name", "")
        pa.official_name = acct_data.get("official_name")
        pa.mask = acct_data.get("mask")
        pa.type = (acct_data.get("type") or "")
        pa.subtype = (acct_data.get("subtype") or "")

        balances = acct_data.get("balances") or {}
        pa.balance_current = balances.get("current")
        pa.balance_available = balances.get("available")
        pa.balance_limit = balances.get("limit")

        db.session.flush()
        id_map[acct_id] = pa.id
    return id_map


def sync_investments(user_id: int, plaid_item: PlaidItem) -> dict:
    """Pull investment holdings from Plaid and upsert into Holding / CryptoHolding."""
    from .import_service import detect_bucket

    client = get_plaid_client()
    access_token = decrypt(plaid_item.access_token)

    _backfill_branding_if_needed(client, plaid_item)

    try:
        req = InvestmentsHoldingsGetRequest(access_token=access_token)
        resp = client.investments_holdings_get(req)
    except plaid.ApiException as e:
        _handle_plaid_error(plaid_item, e)
        return {"error": str(e)}

    data = resp.to_dict()
    securities_map = {s["security_id"]: s for s in data.get("securities", [])}
    accounts_map = {a["account_id"]: a for a in data.get("accounts", [])}

    pa_id_map = _upsert_plaid_accounts(plaid_item, accounts_map)

    seen_tickers = set()
    seen_crypto = set()
    synced = 0

    for h in data.get("holdings", []):
        security = securities_map.get(h.get("security_id"))
        if not security:
            continue

        ticker = security.get("ticker_symbol") or ""

        quantity = h.get("quantity", 0) or 0
        total_cost = h.get("cost_basis") or None
        cost_basis = (total_cost / quantity) if total_cost and quantity else None
        inst_value = h.get("institution_value") or None
        raw_account_id = h.get("account_id", "")
        account = accounts_map.get(raw_account_id, {})
        account_name = account.get("name", "")
        sec_type = (security.get("type") or "").lower()
        sec_name = security.get("name") or ""
        sec_isin = security.get("isin") or None
        sec_cusip = security.get("cusip") or None
        pa_db_id = pa_id_map.get(raw_account_id)

        if ticker == "CUR:USD":
            cash_val = inst_value or quantity or 0
            if cash_val <= 0:
                continue
            seen_tickers.add(("CASH:USD", account_name))
            existing = Holding.query.filter_by(
                user_id=user_id, ticker="CASH:USD", account=account_name,
                plaid_item_id=plaid_item.id,
            ).first()
            if existing:
                existing.shares = cash_val
                existing.value_override = cash_val
                existing.institution_value = cash_val
                existing.plaid_account_id = pa_db_id
            else:
                db.session.add(Holding(
                    user_id=user_id, ticker="CASH:USD", shares=cash_val,
                    cost_basis=None, account=account_name,
                    bucket="Cash", source="plaid",
                    plaid_item_id=plaid_item.id,
                    plaid_account_id=pa_db_id,
                    value_override=cash_val,
                    institution_value=cash_val,
                    security_name="Cash",
                    security_type="cash",
                ))
            synced += 1
            continue

        if not ticker:
            slug = sec_name[:14].upper().replace(" ", "_").rstrip("_") or "PRIV"
            ticker = f"PRIV:{slug}"

        if sec_type == "cryptocurrency" or ticker.upper() in CRYPTO_TICKERS:
            sym = ticker.upper().replace("CUR:", "")
            seen_crypto.add(sym)
            source_tag = f"plaid:{plaid_item.id}"
            crypto_cost = total_cost if total_cost else None
            existing = CryptoHolding.query.filter_by(
                user_id=user_id, symbol=sym, source=source_tag
            ).first()
            if existing:
                existing.quantity = quantity
                if crypto_cost is not None:
                    existing.cost_basis = crypto_cost
            else:
                db.session.add(CryptoHolding(
                    user_id=user_id, symbol=sym, quantity=quantity,
                    coingecko_id=sym.lower(), cost_basis=crypto_cost,
                    source=source_tag,
                ))
            synced += 1
            continue

        ticker = ticker.upper()
        is_private = ticker.startswith("PRIV:")
        seen_tickers.add((ticker, account_name))
        if is_private:
            detected = detect_bucket("", sec_name)
            bucket = detected if detected != "Equities" else "Alternatives"
        else:
            bucket = detect_bucket(ticker, sec_name)

        existing = Holding.query.filter_by(
            user_id=user_id, ticker=ticker, account=account_name,
            plaid_item_id=plaid_item.id,
        ).first()

        if existing:
            existing.shares = quantity
            if cost_basis is not None:
                existing.cost_basis = cost_basis
            existing.bucket = bucket
            if is_private and inst_value:
                existing.value_override = inst_value
            existing.institution_value = inst_value
            existing.plaid_account_id = pa_db_id
            existing.security_name = sec_name or existing.security_name
            existing.security_type = sec_type or existing.security_type
            existing.isin = sec_isin or existing.isin
            existing.cusip = sec_cusip or existing.cusip
        else:
            db.session.add(Holding(
                user_id=user_id, ticker=ticker, shares=quantity,
                cost_basis=cost_basis, account=account_name,
                bucket=bucket, source="plaid",
                plaid_item_id=plaid_item.id,
                plaid_account_id=pa_db_id,
                value_override=inst_value if is_private else None,
                institution_value=inst_value,
                notes=sec_name if is_private else "",
                security_name=sec_name,
                security_type=sec_type,
                isin=sec_isin,
                cusip=sec_cusip,
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


def sync_investment_transactions(user_id: int, plaid_item: PlaidItem) -> dict:
    """Pull investment transactions from Plaid and upsert into InvestmentTransaction."""
    from datetime import date, timedelta

    client = get_plaid_client()
    access_token = decrypt(plaid_item.access_token)

    existing_count = InvestmentTransaction.query.filter_by(
        plaid_item_id=plaid_item.id
    ).count()
    lookback_days = 90 if existing_count == 0 else 30
    start_date = date.today() - timedelta(days=lookback_days)
    end_date = date.today()

    total_added = 0
    offset = 0
    batch_size = 100

    try:
        while True:
            req = InvestmentsTransactionsGetRequest(
                access_token=access_token,
                start_date=start_date,
                end_date=end_date,
                options={"count": batch_size, "offset": offset},
            )
            resp = client.investments_transactions_get(req)
            data = resp.to_dict()

            securities_map = {s["security_id"]: s for s in data.get("securities", [])}
            accounts_map = {a["account_id"]: a for a in data.get("accounts", [])}

            for txn in data.get("investment_transactions", []):
                inv_txn_id = txn.get("investment_transaction_id", "")
                if not inv_txn_id:
                    continue

                security = securities_map.get(txn.get("security_id")) or {}
                ticker = (security.get("ticker_symbol") or "").upper() or None
                sec_name = security.get("name") or txn.get("name") or ""
                raw_account_id = txn.get("account_id", "")
                pa = PlaidAccount.query.filter_by(account_id=raw_account_id).first()
                pa_db_id = pa.id if pa else None

                existing = InvestmentTransaction.query.filter_by(
                    investment_transaction_id=inv_txn_id
                ).first()

                txn_type = (txn.get("type") or "").lower()
                txn_subtype = (txn.get("subtype") or "").lower() or None
                txn_date = txn.get("date")
                amount = txn.get("amount") or 0
                quantity = txn.get("quantity") or 0
                price = txn.get("price") or 0
                fees = txn.get("fees") or 0

                if existing:
                    existing.date = txn_date
                    existing.type = txn_type
                    existing.subtype = txn_subtype
                    existing.ticker = ticker
                    existing.security_name = sec_name[:255] if sec_name else None
                    existing.quantity = quantity
                    existing.amount = amount
                    existing.price = price
                    existing.fees = fees
                    existing.description = (txn.get("name") or "")[:500]
                else:
                    db.session.add(InvestmentTransaction(
                        user_id=user_id,
                        plaid_item_id=plaid_item.id,
                        plaid_account_id=pa_db_id,
                        investment_transaction_id=inv_txn_id,
                        date=txn_date,
                        type=txn_type,
                        subtype=txn_subtype,
                        ticker=ticker,
                        security_name=sec_name[:255] if sec_name else None,
                        quantity=quantity,
                        amount=amount,
                        price=price,
                        fees=fees,
                        description=(txn.get("name") or "")[:500],
                    ))
                    total_added += 1

            total_txns = data.get("total_investment_transactions", 0)
            offset += len(data.get("investment_transactions", []))
            if offset >= total_txns:
                break

    except plaid.ApiException as e:
        log.warning("Investment transactions sync failed for item %s: %s",
                    plaid_item.item_id, e)
        db.session.rollback()
        return {"error": str(e)}

    db.session.commit()
    log.info("Investment txn sync user=%d item=%s: added=%d",
             user_id, plaid_item.item_id, total_added)
    return {"added": total_added}


def build_tax_lots(user_id: int, plaid_item_id: int | None = None):
    """Build/rebuild TaxLot rows from InvestmentTransaction buy records using FIFO."""
    q = InvestmentTransaction.query.filter_by(user_id=user_id)
    if plaid_item_id:
        q = q.filter_by(plaid_item_id=plaid_item_id)
    txns = q.order_by(InvestmentTransaction.date.asc()).all()

    processed_tickers = set()
    for txn in txns:
        if txn.ticker:
            processed_tickers.add(txn.ticker)

    for ticker in processed_tickers:
        holding = Holding.query.filter_by(
            user_id=user_id, ticker=ticker, source="plaid"
        ).first()
        holding_id = holding.id if holding else None

        TaxLot.query.filter_by(
            user_id=user_id, holding_id=holding_id
        ).delete()

        ticker_txns = [t for t in txns if t.ticker == ticker]
        lots = []

        for txn in ticker_txns:
            if txn.type == "buy" and txn.quantity and txn.quantity > 0:
                lot = TaxLot(
                    user_id=user_id,
                    holding_id=holding_id,
                    date_acquired=txn.date,
                    quantity=abs(txn.quantity),
                    cost_per_share=abs(txn.price) if txn.price else 0,
                    investment_transaction_id=txn.id,
                    sold_quantity=0,
                )
                db.session.add(lot)
                lots.append(lot)
            elif txn.type == "sell" and txn.quantity:
                remaining = abs(txn.quantity)
                for lot in lots:
                    if remaining <= 0:
                        break
                    available = lot.quantity - lot.sold_quantity
                    if available <= 0:
                        continue
                    sell_qty = min(remaining, available)
                    lot.sold_quantity += sell_qty
                    remaining -= sell_qty

    db.session.commit()


def sync_balances_to_blended(user_id: int, plaid_item: PlaidItem):
    """Sync depository account balances from PlaidAccount into BlendedAccount."""
    from sqlalchemy.orm.attributes import flag_modified

    plaid_accounts = PlaidAccount.query.filter_by(
        plaid_item_id=plaid_item.id
    ).all()

    for pa in plaid_accounts:
        if pa.type not in ("depository", "credit"):
            continue
        if pa.balance_current is None:
            continue

        source_tag = f"plaid:{plaid_item.id}:{pa.account_id}"
        display_name = pa.official_name or pa.name or "Plaid Account"
        if plaid_item.institution_name:
            display_name = f"{plaid_item.institution_name} - {display_name}"
        if pa.mask:
            display_name += f" (****{pa.mask})"

        ba = BlendedAccount.query.filter_by(
            user_id=user_id, source=source_tag
        ).first()

        if not ba:
            ba = BlendedAccount(
                user_id=user_id,
                name=display_name,
                source=source_tag,
            )
            db.session.add(ba)

        ba.value = pa.balance_current
        ba.name = display_name

        bucket = "Cash"
        if pa.subtype in ("checking", "savings", "money market", "cd"):
            bucket = "Cash"
        elif pa.type == "credit":
            bucket = "Cash"

        alloc = dict(ba.allocations or {})
        alloc["asset_class"] = bucket
        ba.allocations = alloc
        flag_modified(ba, "allocations")

    db.session.commit()


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
    """Full sync: investments + transactions + investment txns + balances.

    Each phase runs independently so a failure in one
    doesn't prevent the others from completing.
    """
    inv_result: dict = {}
    txn_result: dict = {}
    inv_txn_result: dict = {}
    bal_result: dict = {}

    try:
        inv_result = sync_investments(user_id, plaid_item)
    except Exception as e:
        log.error("Investment sync failed for item %s: %s", plaid_item.item_id, e)
        inv_result = {"error": str(e)}

    try:
        txn_result = sync_transactions(user_id, plaid_item)
    except Exception as e:
        log.error("Transaction sync failed for item %s: %s", plaid_item.item_id, e)
        txn_result = {"error": str(e)}

    try:
        inv_txn_result = sync_investment_transactions(user_id, plaid_item)
    except Exception as e:
        log.error("Inv txn sync failed for item %s: %s", plaid_item.item_id, e)
        inv_txn_result = {"error": str(e)}

    if "error" not in inv_txn_result:
        try:
            build_tax_lots(user_id, plaid_item.id)
        except Exception as e:
            log.error("Tax lot build failed for item %s: %s", plaid_item.item_id, e)

    try:
        sync_balances_to_blended(user_id, plaid_item)
        bal_result = {"synced": True}
    except Exception as e:
        log.error("Balance sync failed for item %s: %s", plaid_item.item_id, e)
        bal_result = {"error": str(e)}

    return {
        "investments": inv_result,
        "transactions": txn_result,
        "investment_transactions": inv_txn_result,
        "balances": bal_result,
    }


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
            try:
                db.session.rollback()
            except Exception:
                pass
