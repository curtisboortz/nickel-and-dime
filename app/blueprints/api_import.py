"""Import API routes: brokerage CSV upload, preview, and commit.

Import is a Pro-only feature. Supports Fidelity, Schwab, Vanguard,
E-Trade, Robinhood, WeBull, IBKR, Coinbase, thinkorswim, M1, and generic CSV.
"""

from flask import Blueprint, jsonify, request as flask_request
from flask_login import login_required, current_user

from ..extensions import db
from ..utils.auth import requires_pro
from ..models.portfolio import Holding, CryptoHolding
from ..services.import_service import detect_and_parse, get_supported_brokerages, detect_bucket

api_import_bp = Blueprint("api_import", __name__)


@api_import_bp.route("/import/brokerages")
@login_required
@requires_pro
def supported_brokerages():
    """Return list of supported brokerages with export instructions."""
    return jsonify({"brokerages": get_supported_brokerages()})


@api_import_bp.route("/import/preview", methods=["POST"])
@login_required
@requires_pro

def preview_import():
    """Upload a CSV and return a preview of detected holdings without saving.

    This lets the user review, adjust account names, and deselect rows
    before committing the import.
    """
    file = flask_request.files.get("file")
    if not file:
        return jsonify({"error": "No file provided"}), 400

    if not file.filename.lower().endswith((".csv", ".tsv", ".txt")):
        return jsonify({"error": "Please upload a CSV file"}), 400

    file_bytes = file.read()
    if len(file_bytes) > 5 * 1024 * 1024:  # 5 MB limit
        return jsonify({"error": "File too large (max 5 MB)"}), 400

    result = detect_and_parse(file_bytes, file.filename)

    # Enrich with existing holding info (so frontend can show duplicates)
    existing_tickers = set()
    for h in Holding.query.filter_by(user_id=current_user.id).all():
        existing_tickers.add(h.ticker.upper())
    for c in CryptoHolding.query.filter_by(user_id=current_user.id).all():
        existing_tickers.add(c.symbol.upper())

    for h in result["holdings"]:
        h["is_duplicate"] = h["ticker"].upper() in existing_tickers
        h["bucket"] = detect_bucket(h["ticker"], h.get("description", ""), h.get("asset_type", ""))

    return jsonify(result)


@api_import_bp.route("/import/commit", methods=["POST"])
@login_required
@requires_pro

def commit_import():
    """Save selected holdings from a previewed import.

    Expects JSON body:
    {
        "holdings": [
            {"ticker": "AAPL", "shares": 10, "account": "Fidelity", "asset_type": "stock",
             "cost_basis": 150.0, "description": "Apple Inc"},
            ...
        ],
        "mode": "merge" | "replace"
    }

    mode="merge" (default): add new holdings, update shares if ticker already exists
    mode="replace": delete all existing holdings for the account, then insert
    """
    data = flask_request.get_json(silent=True) or {}
    items = data.get("holdings", [])
    mode = data.get("mode", "merge")

    if not items:
        return jsonify({"error": "No holdings to import"}), 400

    imported = 0
    updated = 0
    skipped = 0

    for item in items:
        ticker = (item.get("ticker") or "").strip().upper()
        shares = item.get("shares")
        account = item.get("account", "Imported")
        asset_type = item.get("asset_type", "stock")
        cost_basis = item.get("cost_basis")
        description = item.get("description", "")
        bucket = item.get("bucket") or detect_bucket(ticker, description, asset_type)

        if not ticker:
            skipped += 1
            continue

        if asset_type == "crypto":
            _import_crypto(ticker, shares, account, cost_basis, description,
                           mode, imported_counter=None)
            imported += 1
            continue

        # Match by ticker+account+cost_basis to preserve separate lots
        # (e.g., same ETF bought at different prices in Margin vs Cash)
        candidates = Holding.query.filter_by(
            user_id=current_user.id, ticker=ticker, account=account
        ).all()

        existing = None
        if cost_basis is not None:
            for c in candidates:
                if c.cost_basis is not None and abs(c.cost_basis - cost_basis) < 0.01:
                    existing = c
                    break
        if existing is None and candidates:
            for c in candidates:
                if c.cost_basis is None:
                    existing = c
                    break

        if existing:
            if mode == "replace":
                existing.shares = shares
                existing.notes = description
                existing.bucket = bucket
                if cost_basis is not None:
                    existing.cost_basis = cost_basis
                updated += 1
            elif mode == "merge":
                existing.shares = shares
                if description and not existing.notes:
                    existing.notes = description
                if cost_basis is not None and not existing.cost_basis:
                    existing.cost_basis = cost_basis
                if not existing.bucket or existing.bucket == "Equities":
                    existing.bucket = bucket
                updated += 1
            else:
                skipped += 1
        else:
            h = Holding(
                user_id=current_user.id,
                ticker=ticker,
                shares=shares,
                cost_basis=cost_basis,
                account=account,
                bucket=bucket,
                notes=description,
            )
            db.session.add(h)
            imported += 1

    db.session.commit()

    return jsonify({
        "success": True,
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
    })


def _import_crypto(ticker, shares, account, cost_basis, description, mode, imported_counter):
    """Handle crypto import -- route to CryptoHolding model."""
    # Normalize: "BTC-USD" -> "BTC"
    base = ticker.split("-")[0] if "-" in ticker else ticker

    existing = CryptoHolding.query.filter_by(
        user_id=current_user.id, symbol=base
    ).first()

    if existing:
        existing.quantity = shares
    else:
        c = CryptoHolding(
            user_id=current_user.id,
            symbol=base,
            quantity=shares,
            coingecko_id="",
        )
        db.session.add(c)
