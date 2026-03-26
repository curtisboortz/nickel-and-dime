"""Portfolio API routes: holdings, balances, metals, quick-update.

Holdings, metals, and portfolio history are Pro features.
Balances (manual account values) remain available to all tiers.
"""

from flask import Blueprint, jsonify, request as flask_request
from flask_login import login_required, current_user

from ..extensions import db, csrf
from ..utils.auth import requires_pro, is_pro
from ..models.portfolio import Holding, CryptoHolding, PhysicalMetal, Account, BlendedAccount
from ..models.settings import UserSettings
from ..models.snapshot import PortfolioSnapshot

api_portfolio_bp = Blueprint("api_portfolio", __name__)


@api_portfolio_bp.route("/holdings")
@login_required
@requires_pro
def get_holdings():
    """Return all holdings for the current user. Pro only."""
    holdings = Holding.query.filter_by(user_id=current_user.id).all()
    crypto = CryptoHolding.query.filter_by(user_id=current_user.id).all()
    metals = PhysicalMetal.query.filter_by(user_id=current_user.id).all()
    return jsonify({
        "holdings": [{"id": h.id, "ticker": h.ticker, "shares": h.shares,
                       "bucket": h.bucket, "account": h.account,
                       "value_override": h.value_override, "notes": h.notes}
                      for h in holdings],
        "crypto": [{"id": c.id, "symbol": c.symbol, "quantity": c.quantity,
                     "coingecko_id": c.coingecko_id} for c in crypto],
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
    """Add or update a holding. Pro only."""
    data = flask_request.get_json(silent=True) or {}

    holding_id = data.get("id")
    if holding_id:
        h = Holding.query.filter_by(id=holding_id, user_id=current_user.id).first()
        if not h:
            return jsonify({"error": "Not found"}), 404
    else:
        h = Holding(user_id=current_user.id)
        db.session.add(h)

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

    db.session.commit()
    return jsonify({"success": True, "id": h.id})


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
    """Return blended account balances."""
    blended = BlendedAccount.query.filter_by(user_id=current_user.id).all()
    return jsonify({
        "accounts": [{"id": a.id, "name": a.name, "value": a.value,
                       "allocations": a.allocations} for a in blended],
    })


@api_portfolio_bp.route("/balances", methods=["POST"])
@login_required
@csrf.exempt
def save_balances():
    """Update blended account balances."""
    data = flask_request.get_json(silent=True) or {}
    updates = data.get("accounts", [])
    for item in updates:
        acct = BlendedAccount.query.filter_by(id=item.get("id"), user_id=current_user.id).first()
        if acct and "value" in item:
            acct.value = float(item["value"])
    db.session.commit()
    return jsonify({"success": True})


@api_portfolio_bp.route("/portfolio-history")
@login_required
@requires_pro
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
