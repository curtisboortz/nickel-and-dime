"""Portfolio API routes: holdings, balances, metals, quick-update.

Holdings (real-time tracking), metals, and import are Pro features.
Balances (manual), portfolio history, and budget remain free for all.
"""

from flask import Blueprint, jsonify, request as flask_request
from flask_login import login_required, current_user

from ..extensions import db, csrf
from ..utils.auth import requires_pro, is_pro
from ..models.portfolio import Holding, CryptoHolding, PhysicalMetal, Account, BlendedAccount
from ..models.market import PriceCache
from ..models.settings import UserSettings
from ..models.snapshot import PortfolioSnapshot

api_portfolio_bp = Blueprint("api_portfolio", __name__)


def _get_price(symbol):
    """Look up a cached price by yfinance symbol or CoinGecko key."""
    entry = PriceCache.query.get(symbol)
    if entry and entry.price:
        return entry.price
    entry = PriceCache.query.get(f"CG:{symbol.lower()}")
    if entry and entry.price:
        return entry.price
    return None


@api_portfolio_bp.route("/holdings")
@login_required
@requires_pro
def get_holdings():
    """Return all holdings with live prices for the current user. Pro only."""
    holdings = Holding.query.filter_by(user_id=current_user.id).all()
    crypto = CryptoHolding.query.filter_by(user_id=current_user.id).all()
    metals = PhysicalMetal.query.filter_by(user_id=current_user.id).all()

    holdings_out = []
    for h in holdings:
        price = _get_price(h.ticker)
        qty = h.shares or 0
        vo = h.value_override
        if vo:
            total = vo
        elif price and qty:
            total = price * qty
        else:
            total = 0
        holdings_out.append({
            "id": h.id, "ticker": h.ticker, "shares": h.shares,
            "bucket": h.bucket, "account": h.account,
            "value_override": h.value_override, "notes": h.notes,
            "price": price, "total": total,
        })

    crypto_out = []
    for c in crypto:
        cg_key = f"CG:{c.coingecko_id}" if c.coingecko_id else None
        entry = PriceCache.query.get(cg_key) if cg_key else None
        price = entry.price if entry and entry.price else None
        qty = c.quantity or 0
        value = price * qty if price else 0
        crypto_out.append({
            "id": c.id, "symbol": c.symbol, "quantity": c.quantity,
            "coingecko_id": c.coingecko_id,
            "source": c.source or "manual",
            "price": price, "value": value,
        })

    return jsonify({
        "holdings": holdings_out,
        "crypto": crypto_out,
        "metals": [{"id": m.id, "metal": m.metal, "oz": m.oz,
                     "purchase_price": m.purchase_price, "description": m.description}
                    for m in metals],
        "limit": None,
        "total_count": len(holdings) + len(crypto),
    })


@api_portfolio_bp.route("/holdings", methods=["POST"])
@login_required
@requires_pro
@csrf.exempt
def save_holdings():
    """Add or update holdings. Supports single or bulk save.

    Single: {"ticker": "AAPL", "shares": 10, ...}
    Bulk:   {"holdings": [{"id": 1, "ticker": "AAPL", ...}, ...]}
    """
    data = flask_request.get_json(silent=True) or {}

    bulk = data.get("holdings")
    if bulk is not None:
        return _save_holdings_bulk(bulk)

    holding_id = data.get("id")
    if holding_id:
        h = Holding.query.filter_by(id=holding_id, user_id=current_user.id).first()
        if not h:
            return jsonify({"error": "Not found"}), 404
    else:
        h = Holding(user_id=current_user.id)
        db.session.add(h)

    _apply_holding_fields(h, data)
    db.session.commit()
    return jsonify({"success": True, "id": h.id})


def _apply_holding_fields(h, data):
    if "ticker" in data:
        h.ticker = data["ticker"]
    if "shares" in data:
        h.shares = float(data["shares"]) if data["shares"] else None
    if "bucket" in data:
        h.bucket = data["bucket"]
    if "account" in data:
        h.account = data["account"]
    if "value_override" in data:
        h.value_override = float(data["value_override"]) if data["value_override"] else None
    if "notes" in data:
        h.notes = data["notes"]


def _save_holdings_bulk(rows):
    """Replace all holdings with the provided list (mirrors the original form save)."""
    existing = {h.id: h for h in Holding.query.filter_by(user_id=current_user.id).all()}
    seen_ids = set()

    for row in rows:
        ticker = (row.get("ticker") or "").strip()
        if not ticker:
            continue
        hid = row.get("id")
        if hid and hid in existing:
            h = existing[hid]
            seen_ids.add(hid)
        else:
            h = Holding(user_id=current_user.id)
            db.session.add(h)
        _apply_holding_fields(h, row)

    for hid, h in existing.items():
        if hid not in seen_ids:
            db.session.delete(h)

    db.session.commit()
    return jsonify({"success": True})


@api_portfolio_bp.route("/holdings/<int:holding_id>", methods=["DELETE"])
@login_required
@requires_pro
@csrf.exempt
def delete_holding(holding_id):
    """Delete a holding."""
    h = Holding.query.filter_by(id=holding_id, user_id=current_user.id).first()
    if h:
        db.session.delete(h)
        db.session.commit()
    return jsonify({"success": True})


@api_portfolio_bp.route("/balances")
@login_required
def get_balances():
    """Return blended account balances, respecting saved order."""
    from ..models.settings import UserSettings
    blended = BlendedAccount.query.filter_by(user_id=current_user.id).all()
    us = UserSettings.query.filter_by(user_id=current_user.id).first()
    wo = (us.widget_order if us and isinstance(us.widget_order, dict) else {}) or {}
    saved_order = wo.get("balance_order", [])
    if saved_order:
        order_map = {aid: i for i, aid in enumerate(saved_order)}
        blended.sort(key=lambda a: order_map.get(a.id, 9999))
    return jsonify({
        "accounts": [{"id": a.id, "name": a.name, "value": a.value,
                       "allocations": a.allocations} for a in blended],
    })


@api_portfolio_bp.route("/balances", methods=["POST"])
@login_required
@csrf.exempt
def save_balances():
    """Create or update blended account balances."""
    data = flask_request.get_json(silent=True) or {}

    new_account = data.get("new_account")
    if new_account:
        acct = BlendedAccount(
            user_id=current_user.id,
            name=new_account.get("name", "Account"),
            value=float(new_account.get("value", 0)),
            allocations=new_account.get("allocations", {}),
        )
        db.session.add(acct)
        db.session.commit()
        return jsonify({"success": True, "id": acct.id})

    updates = data.get("accounts", [])
    for item in updates:
        acct = BlendedAccount.query.filter_by(id=item.get("id"), user_id=current_user.id).first()
        if acct and "value" in item:
            acct.value = float(item["value"])
    db.session.commit()
    return jsonify({"success": True})


@api_portfolio_bp.route("/balances/rename", methods=["POST"])
@login_required
@csrf.exempt
def rename_balance():
    """Rename a blended account."""
    data = flask_request.get_json(silent=True) or {}
    acct = BlendedAccount.query.filter_by(id=data.get("id"), user_id=current_user.id).first()
    if acct and data.get("name"):
        acct.name = data["name"].strip()
        db.session.commit()
    return jsonify({"success": True})


@api_portfolio_bp.route("/balances/reorder", methods=["POST"])
@login_required
@csrf.exempt
def reorder_balances():
    """Persist the user's preferred balance row order."""
    from ..models.settings import UserSettings
    data = flask_request.get_json(silent=True) or {}
    order = data.get("order", [])
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)
    wo = dict(settings.widget_order or {}) if isinstance(settings.widget_order, dict) else {}
    wo["balance_order"] = order
    settings.widget_order = wo
    db.session.commit()
    return jsonify({"success": True})


@api_portfolio_bp.route("/balances/<int:acct_id>", methods=["DELETE"])
@login_required
@csrf.exempt
def delete_balance(acct_id):
    """Delete a blended account."""
    acct = BlendedAccount.query.filter_by(id=acct_id, user_id=current_user.id).first()
    if acct:
        db.session.delete(acct)
        db.session.commit()
    return jsonify({"success": True})


@api_portfolio_bp.route("/portfolio-history")
@login_required
def portfolio_history():
    """Return portfolio OHLC snapshots for the history chart."""
    snapshots = (PortfolioSnapshot.query
                 .filter_by(user_id=current_user.id)
                 .order_by(PortfolioSnapshot.date)
                 .all())
    return jsonify({
        "history": [{"date": s.date.isoformat(), "total": s.total,
                      "open": s.open_val, "high": s.high, "low": s.low, "close": s.close,
                      "gold": s.gold_price, "silver": s.silver_price}
                     for s in snapshots],
    })


@api_portfolio_bp.route("/physical-metals", methods=["GET", "POST", "DELETE"])
@login_required
@requires_pro
@csrf.exempt
def physical_metals():
    """CRUD for physical metal holdings."""
    if flask_request.method == "GET":
        metals = PhysicalMetal.query.filter_by(user_id=current_user.id).all()
        return jsonify({"metals": [
            {"id": m.id, "metal": m.metal, "oz": m.oz,
             "purchase_price": m.purchase_price, "description": m.description,
             "form": m.form, "date": m.date, "note": m.note}
            for m in metals
        ]})

    if flask_request.method == "POST":
        data = flask_request.get_json(silent=True) or {}
        metal = PhysicalMetal(
            user_id=current_user.id,
            metal=data.get("metal", "gold"),
            form=data.get("form", ""),
            oz=float(data.get("oz", 0)),
            purchase_price=float(data.get("purchase_price", 0)),
            description=data.get("description", ""),
            date=data.get("date", ""),
            note=data.get("note", ""),
        )
        db.session.add(metal)
        db.session.commit()
        return jsonify({"success": True, "id": metal.id})

    if flask_request.method == "DELETE":
        metal_id = flask_request.args.get("id", type=int)
        metal = PhysicalMetal.query.filter_by(id=metal_id, user_id=current_user.id).first()
        if metal:
            db.session.delete(metal)
            db.session.commit()
        return jsonify({"success": True})

    return jsonify({"error": "Invalid method"}), 405


@api_portfolio_bp.route("/quick-update", methods=["POST"])
@login_required
@requires_pro
@csrf.exempt
def quick_update():
    """Natural language quick-update for contributions/trades."""
    data = flask_request.get_json(silent=True) or {}
    text = data.get("text", "")
    # TODO: Parse natural language updates via portfolio service
    return jsonify({"success": True, "parsed": text})


@api_portfolio_bp.route("/export")
@login_required
@requires_pro
def export_data():
    """Export portfolio data as CSV."""
    import io
    import csv
    from flask import Response

    holdings = Holding.query.filter_by(user_id=current_user.id).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Account", "Ticker", "Shares", "Bucket", "Value Override", "Notes"])
    for h in holdings:
        writer.writerow([h.account, h.ticker, h.shares, h.bucket, h.value_override, h.notes])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=portfolio_export.csv"},
    )


DEFAULT_TA_TICKERS = ["SPY", "GC=F", "SI=F", "BTC-USD", "DX=F", "^TNX"]


@api_portfolio_bp.route("/ta-tickers")
@login_required
def get_ta_tickers():
    """Return the user's TA quick-access tickers, auto-seeded from holdings."""
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    wo = (settings.widget_order if settings and isinstance(settings.widget_order, dict) else {})
    saved = wo.get("ta_tickers")

    if saved is not None:
        return jsonify({"tickers": saved})

    tickers = list(DEFAULT_TA_TICKERS)
    holdings = Holding.query.filter_by(user_id=current_user.id).all()
    for h in holdings:
        t = h.ticker.upper()
        if t not in tickers:
            tickers.append(t)
    cryptos = CryptoHolding.query.filter_by(user_id=current_user.id).all()
    for c in cryptos:
        sym = c.symbol.upper() + "-USD"
        if sym not in tickers and "BTC-USD" != sym:
            tickers.append(sym)
    return jsonify({"tickers": tickers})


@api_portfolio_bp.route("/tax-loss-harvesting")
@login_required
def tax_loss_harvesting():
    """Return holdings with unrealized losses > $50 for TLH opportunities."""
    holdings = Holding.query.filter_by(user_id=current_user.id).all()
    rows = []
    for h in holdings:
        qty = h.shares or 0
        cost_per = h.cost_basis or 0
        if not qty or not cost_per:
            continue
        price_row = PriceCache.query.get(h.ticker)
        live_price = price_row.price if price_row and price_row.price else 0
        if not live_price:
            continue
        unrealized = (live_price - cost_per) * qty
        if unrealized < -50:
            rows.append({
                "ticker": h.ticker,
                "qty": round(qty, 3),
                "cost_basis": round(cost_per, 2),
                "current": round(live_price, 2),
                "unrealized": round(unrealized, 0),
            })
    rows.sort(key=lambda r: r["unrealized"])
    return jsonify({"rows": rows})


@api_portfolio_bp.route("/perf-attribution")
@login_required
def perf_attribution():
    """Return performance attribution data: bucket values and overall return."""
    from ..services.portfolio_service import compute_portfolio_value

    pv = compute_portfolio_value(current_user.id)
    total = pv["total"]
    buckets = pv.get("breakdown", {})

    snaps = (PortfolioSnapshot.query
             .filter_by(user_id=current_user.id)
             .order_by(PortfolioSnapshot.date.asc())
             .all())
    overall_return = 0
    if len(snaps) >= 2:
        first_total = snaps[0].close or snaps[0].open or 0
        if first_total > 0:
            overall_return = ((total - first_total) / first_total) * 100

    return jsonify({
        "buckets": {b: round(v, 2) for b, v in buckets.items()},
        "total": round(total, 2),
        "overall_return": round(overall_return, 2),
    })


@api_portfolio_bp.route("/ta-tickers", methods=["POST"])
@login_required
@csrf.exempt
def save_ta_tickers():
    """Save the user's TA quick-access ticker list."""
    data = flask_request.get_json(silent=True) or {}
    tickers = data.get("tickers", [])

    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id, widget_order={})
        db.session.add(settings)

    wo = settings.widget_order if isinstance(settings.widget_order, dict) else {}
    wo["ta_tickers"] = tickers
    settings.widget_order = wo
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(settings, "widget_order")
    db.session.commit()
    return jsonify({"ok": True, "tickers": tickers})
