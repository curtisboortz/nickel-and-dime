"""Portfolio API routes: holdings, balances, metals, quick-update.

Holdings (real-time tracking), metals, and import are Pro features.
Balances (manual), portfolio history, and budget remain free for all.
"""

from datetime import datetime, timezone

from flask import (
    Blueprint, current_app, jsonify, request as flask_request,
    Response,
)
from flask_login import login_required, current_user

from ..extensions import db, cache
from ..utils.auth import requires_pro, is_pro
from ..models.portfolio import (
    Holding, CryptoHolding, PhysicalMetal, Account, BlendedAccount,
    InvestmentTransaction, TaxLot,
)
from ..models.market import PriceCache
from ..models.settings import UserSettings
from ..models.snapshot import PortfolioSnapshot, IntradaySnapshot

api_portfolio_bp = Blueprint("api_portfolio", __name__)


def _get_price_entry(symbol):
    """Return the PriceCache row for a symbol, fetching on demand if needed."""
    entry = PriceCache.query.get(symbol)
    if entry and entry.price:
        return entry
    entry = PriceCache.query.get(f"CG:{symbol.lower()}")
    if entry and entry.price:
        return entry
    return _fetch_and_cache(symbol)


def _get_price(symbol):
    """Shorthand: return just the price float."""
    entry = _get_price_entry(symbol)
    return entry.price if entry else None


def _yf_symbol(symbol):
    """Convert Plaid-style ticker to yfinance format (e.g. BRK.B -> BRK-B)."""
    if not symbol or symbol.startswith("PRIV:") or symbol.startswith("CASH:"):
        return None
    return symbol.replace(".", "-")


def _fetch_and_cache(symbol):
    """One-off yfinance fetch for a ticker not yet in the price cache."""
    yf_sym = _yf_symbol(symbol)
    if not yf_sym:
        return None
    try:
        import yfinance as yf
        from datetime import datetime, timezone
        tk = yf.Ticker(yf_sym)
        info = tk.fast_info
        price = getattr(info, "last_price", None)
        prev = getattr(info, "previous_close", None)
        if price and price > 0:
            row = PriceCache.query.get(symbol)
            if not row:
                row = PriceCache(symbol=symbol)
                db.session.add(row)
            row.price = price
            row.prev_close = prev
            if prev and prev > 0:
                row.change_pct = (price - prev) / prev * 100
            row.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            return row
    except Exception:
        pass
    return None


@api_portfolio_bp.route("/holdings")
@login_required
@requires_pro
def get_holdings():
    """Return holdings grouped by account with institution metadata."""
    from ..models.plaid import PlaidItem, PlaidAccount

    holdings = Holding.query.filter_by(
        user_id=current_user.id
    ).all()
    crypto = CryptoHolding.query.filter_by(
        user_id=current_user.id
    ).all()
    metals = PhysicalMetal.query.filter_by(
        user_id=current_user.id
    ).all()

    stock_symbols = list(
        {h.ticker for h in holdings if h.ticker}
    )
    cg_keys = list(
        {f"CG:{c.coingecko_id}" for c in crypto if c.coingecko_id}
    )
    all_symbols = stock_symbols + cg_keys
    price_cache = {}
    if all_symbols:
        rows = PriceCache.query.filter(
            PriceCache.symbol.in_(all_symbols)
        ).all()
        price_cache = {r.symbol: r for r in rows}

    plaid_ids = {
        h.plaid_item_id for h in holdings if h.plaid_item_id
    }
    plaid_map = {}
    if plaid_ids:
        try:
            items = PlaidItem.query.filter(
                PlaidItem.id.in_(plaid_ids)
            ).all()
            plaid_map = {p.id: p for p in items}
        except Exception:
            db.session.rollback()
            plaid_map = {}

    pa_ids = {
        h.plaid_account_id for h in holdings
        if hasattr(h, "plaid_account_id") and h.plaid_account_id
    }
    pa_map = {}
    if pa_ids:
        try:
            pa_rows = PlaidAccount.query.filter(
                PlaidAccount.id.in_(pa_ids)
            ).all()
            pa_map = {pa.id: pa for pa in pa_rows}
        except Exception:
            db.session.rollback()

    groups = {}
    holdings_flat = []
    grand_total = 0.0

    for h in holdings:
        entry = (
            price_cache.get(h.ticker)
            or _fetch_and_cache(h.ticker)
        )
        price = entry.price if entry else None
        prev_close = entry.prev_close if entry else None
        qty = h.shares or 0
        vo = h.value_override
        inst_val = getattr(h, "institution_value", None)
        if vo:
            total = vo
        elif price and qty:
            total = price * qty
            if total == 0 and inst_val:
                total = inst_val
        else:
            total = inst_val or 0
        grand_total += total

        h_dict = {
            "id": h.id, "ticker": h.ticker,
            "shares": h.shares,
            "bucket": _normalize_bucket(h.bucket),
            "account": h.account,
            "value_override": h.value_override,
            "institution_value": inst_val,
            "notes": h.notes,
            "cost_basis": h.cost_basis,
            "source": h.source or "manual",
            "price": price, "prev_close": prev_close,
            "total": total,
            "security_name": getattr(h, "security_name", None),
            "security_type": getattr(h, "security_type", None),
            "isin": getattr(h, "isin", None),
            "cusip": getattr(h, "cusip", None),
        }
        holdings_flat.append(h_dict)

        pa_id = getattr(h, "plaid_account_id", None)
        gkey = (h.account or "", h.plaid_item_id, pa_id)
        if gkey not in groups:
            pi = plaid_map.get(h.plaid_item_id)
            pa = pa_map.get(pa_id) if pa_id else None
            groups[gkey] = {
                "account_name": h.account or "Unassigned",
                "institution_name": (
                    pi.institution_name if pi else None
                ),
                "institution_id": (
                    pi.institution_id if pi else None
                ),
                "logo_base64": (
                    pi.logo_base64
                    if pi and hasattr(pi, "logo_base64")
                    else None
                ),
                "primary_color": (
                    pi.primary_color
                    if pi and hasattr(pi, "primary_color")
                    else None
                ),
                "source": h.source or "manual",
                "plaid_item_id": h.plaid_item_id,
                "plaid_account_id": pa_id,
                "account_type": pa.type if pa else None,
                "account_subtype": pa.subtype if pa else None,
                "account_mask": pa.mask if pa else None,
                "official_name": pa.official_name if pa else None,
                "balance_current": pa.balance_current if pa else None,
                "balance_available": pa.balance_available if pa else None,
                "holdings": [],
                "subtotal": 0.0,
            }
        groups[gkey]["holdings"].append(h_dict)
        groups[gkey]["subtotal"] += total

    accounts_out = sorted(
        groups.values(),
        key=lambda g: (
            0 if g["source"] == "plaid" else 1,
            (g["institution_name"] or "").lower(),
            (g["account_name"] or "").lower(),
        ),
    )

    crypto_out = []
    for c in crypto:
        cg_key = (
            f"CG:{c.coingecko_id}" if c.coingecko_id
            else None
        )
        entry = price_cache.get(cg_key) if cg_key else None
        price = (
            entry.price if entry and entry.price else None
        )
        qty = c.quantity or 0
        value = price * qty if price else 0
        crypto_out.append({
            "id": c.id, "symbol": c.symbol,
            "quantity": c.quantity,
            "coingecko_id": c.coingecko_id,
            "source": c.source or "manual",
            "price": price, "value": value,
        })

    return jsonify({
        "accounts": accounts_out,
        "holdings": holdings_flat,
        "crypto": crypto_out,
        "metals": [
            {
                "id": m.id, "metal": m.metal,
                "oz": m.oz,
                "purchase_price": m.purchase_price,
                "description": m.description,
            }
            for m in metals
        ],
        "grand_total": grand_total,
        "limit": None,
        "total_count": len(holdings) + len(crypto),
    })


@api_portfolio_bp.route("/holdings", methods=["POST"])
@login_required
@requires_pro

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
        if h.source == "plaid":
            return jsonify({"error": "Plaid holdings are read-only"}), 400
    else:
        h = Holding(user_id=current_user.id)
        db.session.add(h)

    _apply_holding_fields(h, data)
    db.session.commit()
    return jsonify({"success": True, "id": h.id})


from ..utils.buckets import STANDARD_BUCKETS, normalize_bucket as _normalize_bucket


def _apply_holding_fields(h, data):
    if "ticker" in data:
        h.ticker = data["ticker"]
    if "shares" in data:
        h.shares = float(data["shares"]) if data["shares"] else None
    if "bucket" in data:
        h.bucket = _normalize_bucket(data["bucket"])
    if "account" in data:
        h.account = data["account"]
    if "value_override" in data:
        h.value_override = float(data["value_override"]) if data["value_override"] else None
    if "cost_basis" in data:
        h.cost_basis = float(data["cost_basis"]) if data["cost_basis"] else None
    if "notes" in data:
        h.notes = data["notes"]


def _save_holdings_bulk(rows):
    """Replace all manual holdings with the provided list.

    Plaid-sourced holdings are never modified or deleted here — they
    are managed exclusively by the Plaid sync process.
    """
    all_existing = Holding.query.filter_by(user_id=current_user.id).all()
    editable = {h.id: h for h in all_existing if h.source != "plaid"}
    plaid_holdings = {h.id: h for h in all_existing if h.source == "plaid"}
    seen_ids = set()

    for row in rows:
        ticker = (row.get("ticker") or "").strip()
        if not ticker:
            continue
        hid = row.get("id")
        if hid and hid in plaid_holdings:
            ph = plaid_holdings[hid]
            if "bucket" in row:
                ph.bucket = _normalize_bucket(row["bucket"])
            continue
        if hid and hid in editable:
            h = editable[hid]
            seen_ids.add(hid)
        else:
            h = Holding(user_id=current_user.id)
            db.session.add(h)
        _apply_holding_fields(h, row)

    if not seen_ids and editable:
        db.session.commit()
        return jsonify({"success": True, "warning": "No matching rows submitted; existing holdings preserved"})

    for hid, h in editable.items():
        if hid not in seen_ids:
            db.session.delete(h)

    db.session.commit()
    return jsonify({"success": True})


@api_portfolio_bp.route("/holdings/<int:holding_id>", methods=["DELETE"])
@login_required
@requires_pro

def delete_holding(holding_id):
    """Delete a holding. Plaid-sourced holdings cannot be deleted here."""
    h = Holding.query.filter_by(id=holding_id, user_id=current_user.id).first()
    if not h:
        return jsonify({"success": True})
    if h.source == "plaid":
        return jsonify({"error": "Plaid holdings are managed by sync. Disconnect the account in Settings to remove."}), 400
    db.session.delete(h)
    db.session.commit()
    return jsonify({"success": True})


@api_portfolio_bp.route("/investment-transactions")
@login_required
@requires_pro
def get_investment_transactions():
    """Return paginated investment transactions, optionally filtered by account."""
    from ..models.plaid import PlaidAccount

    account_id = flask_request.args.get("account_id", type=int)
    page = flask_request.args.get("page", 1, type=int)
    per_page = flask_request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)

    q = InvestmentTransaction.query.filter_by(user_id=current_user.id)
    if account_id:
        q = q.filter_by(plaid_account_id=account_id)

    q = q.order_by(InvestmentTransaction.date.desc())
    total = q.count()
    txns = q.offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        "transactions": [
            {
                "id": t.id,
                "date": t.date.isoformat() if t.date else None,
                "type": t.type,
                "subtype": t.subtype,
                "ticker": t.ticker,
                "security_name": t.security_name,
                "quantity": t.quantity,
                "amount": t.amount,
                "price": t.price,
                "fees": t.fees,
                "description": t.description,
                "plaid_account_id": t.plaid_account_id,
            }
            for t in txns
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    })


@api_portfolio_bp.route("/tax-lots")
@login_required
@requires_pro
def get_tax_lots():
    """Return tax lots for a holding or all holdings."""
    holding_id = flask_request.args.get("holding_id", type=int)
    q = TaxLot.query.filter_by(user_id=current_user.id)
    if holding_id:
        q = q.filter_by(holding_id=holding_id)
    lots = q.order_by(TaxLot.date_acquired.asc()).all()

    return jsonify({
        "lots": [
            {
                "id": lot.id,
                "holding_id": lot.holding_id,
                "date_acquired": lot.date_acquired.isoformat() if lot.date_acquired else None,
                "quantity": lot.quantity,
                "cost_per_share": lot.cost_per_share,
                "sold_quantity": lot.sold_quantity,
                "remaining": round(lot.quantity - (lot.sold_quantity or 0), 6),
            }
            for lot in lots
        ],
    })


@api_portfolio_bp.route("/crypto", methods=["POST"])
@login_required
@requires_pro
def create_crypto():
    """Add a new manual crypto holding."""
    from ..services.coinbase_service import COINGECKO_MAP
    data = flask_request.get_json(silent=True) or {}
    symbol = (data.get("symbol") or "").strip().upper()
    if not symbol:
        return jsonify({"error": "Symbol is required"}), 400
    try:
        qty = float(data.get("quantity", 0))
    except (TypeError, ValueError):
        qty = 0
    cost_basis = None
    if data.get("cost_basis") is not None:
        try:
            cost_basis = float(data["cost_basis"])
        except (TypeError, ValueError):
            pass
    cg_id = data.get("coingecko_id") or COINGECKO_MAP.get(symbol, symbol.lower())
    c = CryptoHolding(
        user_id=current_user.id,
        symbol=symbol,
        quantity=qty,
        coingecko_id=cg_id,
        cost_basis=cost_basis,
        source="manual",
    )
    db.session.add(c)
    db.session.commit()
    return jsonify({"success": True, "id": c.id})


@api_portfolio_bp.route("/crypto/<int:crypto_id>", methods=["PUT"])
@login_required
@requires_pro
def update_crypto(crypto_id):
    """Update an existing crypto holding."""
    c = CryptoHolding.query.filter_by(id=crypto_id, user_id=current_user.id).first()
    if not c:
        return jsonify({"error": "Not found"}), 404
    data = flask_request.get_json(silent=True) or {}
    if "quantity" in data:
        try:
            c.quantity = float(data["quantity"])
        except (TypeError, ValueError):
            pass
    if "cost_basis" in data:
        try:
            c.cost_basis = float(data["cost_basis"]) if data["cost_basis"] is not None else None
        except (TypeError, ValueError):
            pass
    if "coingecko_id" in data:
        c.coingecko_id = data["coingecko_id"]
    db.session.commit()
    return jsonify({"success": True})


@api_portfolio_bp.route("/crypto/<int:crypto_id>", methods=["DELETE"])
@login_required
@requires_pro
def delete_crypto(crypto_id):
    """Delete a crypto holding."""
    c = CryptoHolding.query.filter_by(id=crypto_id, user_id=current_user.id).first()
    if c:
        db.session.delete(c)
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
    out = []
    for a in blended:
        alloc = dict(a.allocations or {})
        if "asset_class" in alloc:
            alloc["asset_class"] = _normalize_bucket(alloc["asset_class"])
        out.append({
            "id": a.id, "name": a.name, "value": a.value,
            "allocations": alloc,
            "source": getattr(a, "source", "manual") or "manual",
        })
    return jsonify({"accounts": out})


@api_portfolio_bp.route("/balances", methods=["POST"])
@login_required

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
        if not acct:
            continue
        if getattr(acct, "source", "manual") not in ("manual", "", None):
            continue
        if "value" in item:
            acct.value = float(item["value"])
        if "asset_class" in item:
            alloc = dict(acct.allocations or {})
            alloc["asset_class"] = _normalize_bucket(item["asset_class"])
            acct.allocations = alloc
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(acct, "allocations")
    db.session.commit()
    return jsonify({"success": True})


@api_portfolio_bp.route("/balances/rename", methods=["POST"])
@login_required

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

def delete_balance(acct_id):
    """Delete a blended account. Plaid-synced accounts cannot be deleted here."""
    acct = BlendedAccount.query.filter_by(id=acct_id, user_id=current_user.id).first()
    if acct:
        if getattr(acct, "source", "manual") not in ("manual", "", None):
            return jsonify({"error": "Plaid-synced accounts are managed by sync."}), 400
        db.session.delete(acct)
        db.session.commit()
    return jsonify({"success": True})


@api_portfolio_bp.route("/portfolio-history")
@login_required
def portfolio_history():
    """Return portfolio OHLC snapshots for the history chart."""
    import math
    def _safe(v):
        if v is None:
            return None
        try:
            if math.isnan(v) or math.isinf(v):
                return None
        except (TypeError, ValueError):
            pass
        return v

    from datetime import date as _date, datetime as _dt, timedelta
    from ..services.portfolio_service import compute_portfolio_value

    tz_name = flask_request.args.get("tz", "UTC")
    try:
        from zoneinfo import ZoneInfo
        today = _dt.now(ZoneInfo(tz_name)).date()
    except Exception:
        today = _date.today()

    range_param = flask_request.args.get("range", "all").lower()
    range_days = {
        "1d": 1, "1w": 7, "1m": 30, "3m": 90,
        "1y": 365, "3y": 1095, "5y": 1825,
    }
    use_intraday = range_param in ("1d", "1w")

    try:
        pv = compute_portfolio_value(current_user.id)
        live_total = pv.get("total", 0) if pv else 0
    except Exception:
        live_total = 0

    if use_intraday:
        try:
            cutoff_dt = _dt.now(timezone.utc) - timedelta(days=range_days[range_param])
            intraday_rows = (
                IntradaySnapshot.query
                .filter(
                    IntradaySnapshot.user_id == current_user.id,
                    IntradaySnapshot.timestamp >= cutoff_dt,
                )
                .order_by(IntradaySnapshot.timestamp)
                .all()
            )
        except Exception:
            intraday_rows = []
        if intraday_rows:
            all_entries = []
            for row in intraday_rows:
                t = _safe(row.total)
                if not t:
                    continue
                all_entries.append({
                    "date": row.timestamp.isoformat(),
                    "total": t, "close": t,
                })
            if live_total and live_total > 0:
                all_entries.append({
                    "date": _dt.now(timezone.utc).isoformat(),
                    "total": live_total, "close": live_total,
                })
            return jsonify({"history": all_entries, "range": range_param, "intraday": True})

    query = (PortfolioSnapshot.query
             .filter_by(user_id=current_user.id))
    if range_param in range_days:
        cutoff = today - timedelta(days=range_days[range_param])
        query = query.filter(PortfolioSnapshot.date >= cutoff)
    query = query.order_by(PortfolioSnapshot.date)
    snapshots = query.all()

    all_entries = []
    last_snap_date = None
    for s in snapshots:
        total = _safe(s.total)
        close = _safe(s.close)
        val = close or total
        if not val:
            continue
        all_entries.append({
            "date": s.date.isoformat(),
            "total": total, "open": _safe(s.open_val),
            "high": _safe(s.high), "low": _safe(s.low),
            "close": close, "val": val,
            "gold": _safe(s.gold_price), "silver": _safe(s.silver_price),
        })
        last_snap_date = s.date
    if live_total and live_total > 0:
        if last_snap_date == today and all_entries:
            all_entries[-1]["close"] = live_total
            all_entries[-1]["total"] = live_total
            all_entries[-1]["high"] = max(all_entries[-1].get("high") or live_total, live_total)
            all_entries[-1]["low"] = min(all_entries[-1].get("low") or live_total, live_total)
            all_entries[-1]["val"] = live_total
        else:
            all_entries.append({
                "date": today.isoformat(),
                "total": live_total, "open": live_total,
                "high": live_total, "low": live_total,
                "close": live_total, "val": live_total,
                "gold": None, "silver": None,
            })

    if range_param == "all" and len(all_entries) >= 3:
        latest_val = all_entries[-1]["val"]
        threshold = latest_val * 0.4
        start_idx = 0
        for i, e in enumerate(all_entries):
            if e["val"] >= threshold:
                start_idx = i
                break
        all_entries = all_entries[start_idx:]

    for e in all_entries:
        e.pop("val", None)
    return jsonify({"history": all_entries, "range": range_param})


@api_portfolio_bp.route("/physical-metals", methods=["GET", "POST", "DELETE"])
@login_required
@requires_pro

def physical_metals():
    """CRUD for physical metal holdings."""
    if flask_request.method == "GET":
        metals = PhysicalMetal.query.filter_by(user_id=current_user.id).all()
        gold_row = PriceCache.query.get("GC=F")
        silver_row = PriceCache.query.get("SI=F")
        spot = {
            "gold": {"price": gold_row.price if gold_row else None, "change_pct": gold_row.change_pct if gold_row else None},
            "silver": {"price": silver_row.price if silver_row else None, "change_pct": silver_row.change_pct if silver_row else None},
        }
        return jsonify({
            "metals": [
                {"id": m.id, "metal": m.metal, "oz": m.oz,
                 "purchase_price": m.purchase_price, "description": m.description,
                 "form": m.form, "date": m.date, "note": m.note}
                for m in metals
            ],
            "spot": spot,
        })

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


@api_portfolio_bp.route("/tax-report")
@login_required
@requires_pro
def tax_report():
    """Generate a tax-ready CSV with cost basis, market value, unrealized gains, and TLH flags."""
    import io
    import csv
    from flask import Response
    from datetime import date as _date

    holdings = Holding.query.filter_by(user_id=current_user.id).all()
    crypto = CryptoHolding.query.filter_by(user_id=current_user.id).all()
    metals = PhysicalMetal.query.filter_by(user_id=current_user.id).all()

    tickers = list({h.ticker for h in holdings if h.ticker})
    cg_keys = list({f"CG:{c.coingecko_id}" for c in crypto if c.coingecko_id})
    all_syms = tickers + cg_keys + ["GC=F", "SI=F"]
    price_map = {}
    if all_syms:
        price_map = {r.symbol: r for r in PriceCache.query.filter(PriceCache.symbol.in_(all_syms)).all()}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Asset Type", "Ticker/Symbol", "Account", "Category", "Shares/Qty",
        "Cost Basis/Share", "Total Cost Basis", "Current Price", "Market Value",
        "Unrealized Gain/Loss", "Unrealized %", "TLH Candidate", "Substitute ETF",
    ])

    for h in holdings:
        qty = h.shares or 0
        cost_per = h.cost_basis or 0
        pr = price_map.get(h.ticker)
        price = pr.price if pr else 0
        mv = h.value_override or (qty * price)
        total_cost = qty * cost_per
        gl = mv - total_cost if cost_per else 0
        gl_pct = (gl / total_cost * 100) if total_cost else 0
        is_tlh = "Yes" if gl < -50 else ""
        sub = SUBSTITUTE_ETFS.get(h.ticker, "") if gl < -50 else ""
        writer.writerow([
            "Stock/ETF", h.ticker, h.account or "", h.bucket or "",
            round(qty, 4), round(cost_per, 2), round(total_cost, 2),
            round(price, 2), round(mv, 2), round(gl, 2),
            f"{gl_pct:.1f}%", is_tlh, sub,
        ])

    for c in crypto:
        cg_key = f"CG:{c.coingecko_id}" if c.coingecko_id else None
        pr = price_map.get(cg_key) if cg_key else None
        price = pr.price if pr else 0
        mv = c.quantity * price
        total_cost = c.quantity * (c.cost_basis or 0)
        gl = mv - total_cost if c.cost_basis else 0
        gl_pct = (gl / total_cost * 100) if total_cost else 0
        writer.writerow([
            "Crypto", c.symbol, "", "Crypto",
            round(c.quantity, 8), round(c.cost_basis or 0, 2), round(total_cost, 2),
            round(price, 2), round(mv, 2), round(gl, 2),
            f"{gl_pct:.1f}%", "", "",
        ])

    for m in metals:
        sym = "GC=F" if m.metal.lower() == "gold" else "SI=F"
        pr = price_map.get(sym)
        spot = pr.price if pr else 0
        mv = m.oz * spot
        total_cost = m.oz * (m.purchase_price or 0)
        gl = mv - total_cost
        gl_pct = (gl / total_cost * 100) if total_cost else 0
        writer.writerow([
            "Physical Metal", m.metal, "", m.metal,
            round(m.oz, 4), round(m.purchase_price or 0, 2), round(total_cost, 2),
            round(spot, 2), round(mv, 2), round(gl, 2),
            f"{gl_pct:.1f}%", "", "",
        ])

    today = _date.today().isoformat()
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=nickeldime_tax_report_{today}.csv"},
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


SUBSTITUTE_ETFS = {
    "SPY": "IVV", "IVV": "VOO", "VOO": "SPY",
    "QQQ": "QQQM", "QQQM": "QQQ",
    "VTI": "ITOT", "ITOT": "VTI",
    "VXUS": "IXUS", "IXUS": "VXUS",
    "VEA": "IEFA", "IEFA": "VEA",
    "VWO": "IEMG", "IEMG": "VWO",
    "BND": "AGG", "AGG": "BND",
    "TLT": "VGLT", "VGLT": "TLT",
    "GLD": "IAU", "IAU": "GLD",
    "SLV": "SIVR", "SIVR": "SLV",
    "XLE": "VDE", "VDE": "XLE",
    "XLF": "VFH", "VFH": "XLF",
    "XLK": "VGT", "VGT": "XLK",
    "ARKK": "QQQM", "SCHD": "VYM", "VYM": "SCHD",
    "IWM": "VTWO", "VTWO": "IWM",
    "EFA": "VEA", "EEM": "VWO",
}


@api_portfolio_bp.route("/tax-loss-harvesting")
@login_required
def tax_loss_harvesting():
    """Return TLH opportunities with wash-sale warnings and substitute ETFs."""
    from datetime import timedelta
    holdings = Holding.query.filter_by(user_id=current_user.id).all()
    tickers = list({h.ticker for h in holdings if h.ticker})
    price_map = {}
    if tickers:
        price_map = {r.symbol: r for r in PriceCache.query.filter(PriceCache.symbol.in_(tickers)).all()}

    now = datetime.now(timezone.utc)
    wash_window = now - timedelta(days=30)
    recent_tickers = set()
    for h in holdings:
        added = h.added_at
        if added and added.tzinfo is None:
            added = added.replace(tzinfo=timezone.utc)
        if added and added >= wash_window:
            recent_tickers.add(h.ticker)

    rows = []
    for h in holdings:
        qty = h.shares or 0
        cost_per = h.cost_basis or 0
        if not qty or not cost_per:
            continue
        price_row = price_map.get(h.ticker)
        live_price = price_row.price if price_row and price_row.price else 0
        if not live_price:
            continue
        unrealized = (live_price - cost_per) * qty
        if unrealized < -50:
            wash_risk = h.ticker in recent_tickers
            substitute = SUBSTITUTE_ETFS.get(h.ticker)
            rows.append({
                "ticker": h.ticker,
                "qty": round(qty, 3),
                "cost_basis": round(cost_per, 2),
                "current": round(live_price, 2),
                "unrealized": round(unrealized, 0),
                "wash_sale_risk": wash_risk,
                "substitute": substitute,
            })
    rows.sort(key=lambda r: r["unrealized"])
    return jsonify({"rows": rows})


@api_portfolio_bp.route("/perf-attribution")
@login_required
def perf_attribution():
    """Return performance attribution with per-bucket returns from snapshot history."""
    from ..services.portfolio_service import compute_portfolio_value
    from ..utils.buckets import rollup_breakdown

    pv = compute_portfolio_value(current_user.id)
    total = pv["total"]
    raw_buckets = pv.get("breakdown", {})

    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    overrides = (settings.bucket_rollup if settings and hasattr(settings, "bucket_rollup") else None)
    rolled, _ = rollup_breakdown(raw_buckets, overrides=overrides)

    snaps = (PortfolioSnapshot.query
             .filter_by(user_id=current_user.id)
             .order_by(PortfolioSnapshot.date.asc())
             .all())

    overall_return = 0
    if len(snaps) >= 2:
        first_total = snaps[0].close or snaps[0].open or 0
        if first_total > 0:
            overall_return = ((total - first_total) / first_total) * 100

    bucket_returns = {}
    first_bd = None
    for s in snaps:
        if s.breakdown and isinstance(s.breakdown, dict):
            first_bd = s.breakdown
            break

    if first_bd:
        current_rolled, _ = rollup_breakdown(raw_buckets, overrides=overrides)
        first_rolled, _ = rollup_breakdown(first_bd, overrides=overrides)
        for bucket in current_rolled:
            curr_val = current_rolled.get(bucket, 0)
            first_val = first_rolled.get(bucket, 0)
            if first_val > 0:
                bucket_returns[bucket] = round(((curr_val - first_val) / first_val) * 100, 2)
            elif curr_val > 0:
                bucket_returns[bucket] = None
            else:
                bucket_returns[bucket] = 0

    import math
    def _clean(v):
        if v is None:
            return None
        try:
            if math.isnan(v) or math.isinf(v):
                return None
        except (TypeError, ValueError):
            pass
        return v

    history = []
    for s in snaps:
        t = _clean(s.close) or _clean(s.total) or 0
        entry = {"date": s.date.isoformat(), "total": t}
        if s.breakdown and isinstance(s.breakdown, dict):
            bd_rolled, _ = rollup_breakdown(s.breakdown, overrides=overrides)
            entry["breakdown"] = {b: round(v, 2) for b, v in bd_rolled.items() if _clean(v) is not None}
        history.append(entry)

    return jsonify({
        "buckets": {b: round(v, 2) for b, v in rolled.items()},
        "total": round(total, 2),
        "overall_return": round(_clean(overall_return) or 0, 2),
        "bucket_returns": bucket_returns,
        "history": history,
    })


@api_portfolio_bp.route("/ta-tickers", methods=["POST"])
@login_required

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


@api_portfolio_bp.route("/buckets")
@login_required
def list_buckets():
    """Return standard bucket names + any custom ones the user has created."""
    user_buckets = (
        db.session.query(Holding.bucket)
        .filter(Holding.user_id == current_user.id, Holding.bucket.isnot(None))
        .distinct()
        .all()
    )
    custom = set()
    for (b,) in user_buckets:
        normalized = _normalize_bucket(b)
        if normalized and normalized not in STANDARD_BUCKETS:
            custom.add(normalized)
    return jsonify({"standard": STANDARD_BUCKETS, "custom": sorted(custom)})


@api_portfolio_bp.route("/normalize-buckets", methods=["POST"])
@login_required

def normalize_buckets():
    """One-shot: normalize all bucket names for the current user's holdings."""
    holdings = Holding.query.filter_by(user_id=current_user.id).all()
    fixed = 0
    for h in holdings:
        if h.bucket:
            normed = _normalize_bucket(h.bucket)
            if normed != h.bucket:
                h.bucket = normed
                fixed += 1
    db.session.commit()
    return jsonify({"success": True, "fixed": fixed})


ASSET_CLASS_PARAMS = {
    "Equities":        {"return": 0.10,  "vol": 0.16},
    "International":   {"return": 0.08,  "vol": 0.18},
    "Managed Blend":   {"return": 0.09,  "vol": 0.14},
    "Retirement Blend":{"return": 0.08,  "vol": 0.13},
    "Fixed Income":    {"return": 0.04,  "vol": 0.05},
    "Cash":            {"return": 0.04,  "vol": 0.01},
    "Gold":            {"return": 0.06,  "vol": 0.15},
    "Silver":          {"return": 0.05,  "vol": 0.22},
    "Crypto":          {"return": 0.15,  "vol": 0.60},
    "Alternatives":    {"return": 0.08,  "vol": 0.20},
    "Real Assets":     {"return": 0.07,  "vol": 0.14},
    "Real Estate":     {"return": 0.07,  "vol": 0.13},
    "Art":             {"return": 0.06,  "vol": 0.18},
}


@api_portfolio_bp.route("/mc-params")
@login_required
def mc_params():
    """Return portfolio-weighted Monte Carlo parameters."""
    from ..services.portfolio_service import compute_portfolio_value
    from ..utils.buckets import rollup_breakdown

    pv = compute_portfolio_value(current_user.id)
    total = pv["total"]
    raw = pv.get("breakdown", {})

    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    overrides = (settings.bucket_rollup if settings and hasattr(settings, "bucket_rollup") else None)
    rolled, _ = rollup_breakdown(raw, overrides=overrides)

    if total <= 0:
        return jsonify({"annual_return": 0.07, "annual_vol": 0.15, "total": 0, "weights": {}})

    weighted_return = 0
    weighted_var = 0
    weights = {}
    for bucket, value in rolled.items():
        w = value / total
        params = ASSET_CLASS_PARAMS.get(bucket, {"return": 0.07, "vol": 0.15})
        weighted_return += w * params["return"]
        weighted_var += (w ** 2) * (params["vol"] ** 2)
        weights[bucket] = {"weight": round(w * 100, 1), "return": params["return"], "vol": params["vol"]}

    return jsonify({
        "annual_return": round(weighted_return, 4),
        "annual_vol": round(weighted_var ** 0.5, 4),
        "total": round(total, 2),
        "weights": weights,
    })


# ── Allocation Templates ──────────────────────────────────────


@api_portfolio_bp.route("/templates", methods=["GET"])
@login_required
def list_templates():
    """List all available allocation templates."""
    from ..services.templates_service import (
        list_templates as _list,
    )
    return jsonify({"templates": _list()})


@api_portfolio_bp.route(
    "/templates/<template_id>", methods=["GET"]
)
@login_required
def get_template(template_id):
    """Return a single template with full allocations."""
    from ..services.templates_service import (
        get_template as _get,
    )
    tpl = _get(template_id)
    if not tpl:
        return jsonify({"error": "Template not found"}), 404
    return jsonify(tpl)


@api_portfolio_bp.route(
    "/templates/<template_id>/compare", methods=["GET"]
)
@login_required
def compare_template(template_id):
    """Compare user portfolio against a template."""
    from ..services.templates_service import compare_portfolio
    from ..services.portfolio_service import (
        compute_portfolio_value,
    )
    from ..utils.buckets import rollup_breakdown

    pv = compute_portfolio_value(current_user.id)
    settings = (
        db.session.query(UserSettings)
        .filter_by(user_id=current_user.id)
        .first()
    )
    overrides = (
        settings.bucket_rollup
        if settings and hasattr(settings, "bucket_rollup")
        else None
    )
    breakdown, children = rollup_breakdown(
        pv.get("breakdown", {}), overrides=overrides
    )
    result = compare_portfolio(
        template_id, breakdown, pv["total"], children=children
    )
    if not result:
        return jsonify({"error": "Template not found"}), 404
    return jsonify(result)


# ── AI Portfolio Insights ──────────────────────────────────────


@api_portfolio_bp.route("/insights", methods=["GET"])
@login_required
def portfolio_insights():
    """Return AI-generated portfolio insights."""
    from ..services.insights_service import generate_insights

    ck = f"insights:{current_user.id}"
    cached = cache.get(ck)
    if cached is not None:
        return jsonify(cached)

    settings = (
        db.session.query(UserSettings)
        .filter_by(user_id=current_user.id)
        .first()
    )
    overrides = (
        settings.bucket_rollup
        if settings and hasattr(settings, "bucket_rollup")
        else None
    )
    result = generate_insights(current_user.id, overrides=overrides)
    cache.set(ck, result, timeout=120)
    return jsonify(result)


# ── AI Portfolio Advisor ────────────────────────────────────────


@api_portfolio_bp.route("/insights/ai-advice", methods=["POST"])
@login_required
@requires_pro
def ai_portfolio_advice():
    """Return AI-generated portfolio advice (Pro only)."""
    from ..services.ai_advice_service import get_ai_advice

    api_key = current_app.config.get("OPENAI_API_KEY", "")
    if not api_key:
        return jsonify({"error": "AI not configured"}), 503

    settings = (
        db.session.query(UserSettings)
        .filter_by(user_id=current_user.id)
        .first()
    )
    overrides = (
        settings.bucket_rollup
        if settings and hasattr(settings, "bucket_rollup")
        else None
    )

    try:
        result = get_ai_advice(
            current_user.id, overrides=overrides
        )
    except Exception:
        return jsonify(
            {"error": "AI service unavailable"}
        ), 503

    if "error" in result:
        return jsonify(result), 503
    return jsonify(result)


# ── PDF Report ─────────────────────────────────────────────────


@api_portfolio_bp.route("/report/pdf", methods=["GET"])
@login_required
@requires_pro
def download_pdf_report():
    """Generate and return a branded PDF portfolio report."""
    from ..services.pdf_service import generate_pdf

    settings = (
        db.session.query(UserSettings)
        .filter_by(user_id=current_user.id)
        .first()
    )
    overrides = (
        settings.bucket_rollup
        if settings and hasattr(settings, "bucket_rollup")
        else None
    )
    pdf_bytes = generate_pdf(
        current_user.id, overrides=overrides
    )
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    fname = f"NickelAndDime_Report_{ts}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={fname}"
        },
    )
