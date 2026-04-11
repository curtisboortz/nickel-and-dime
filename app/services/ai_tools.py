"""OpenAI function-calling tool definitions and handlers for the AI advisor.

Each tool reuses existing service code so the AI can pull live data
on demand during a conversation.
"""

import json
from datetime import date, datetime, timedelta, timezone

from ..extensions import db
from ..models.market import PriceCache, SentimentCache, FredCache
from ..models.portfolio import Holding, CryptoHolding, PhysicalMetal, BlendedAccount, Account
from ..models.snapshot import PortfolioSnapshot
from ..models.settings import UserSettings
from ..services.portfolio_service import compute_portfolio_value
from ..services.templates_service import (
    list_templates as _list_templates,
    get_template as _get_template,
    compare_portfolio,
)
from ..utils.buckets import rollup_breakdown


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_ticker_price",
            "description": (
                "Look up the current price, daily change %, and previous close "
                "for a stock, ETF, crypto, or commodity ticker symbol."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Ticker symbol (e.g. SPY, BTC-USD, GC=F)",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_sentiment",
            "description": (
                "Get current market sentiment indicators: CNN Fear & Greed index, "
                "crypto Fear & Greed, VIX level."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_economic_indicator",
            "description": (
                "Get the latest value(s) for a FRED economic data series group. "
                "Available groups: debt_fiscal, cpi_pce, monetary, yield_curve, "
                "credit_spreads, real_yields, fed_balance_sheet, sahm, "
                "labor, growth_sentiment, housing, wui."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "series_group": {
                        "type": "string",
                        "description": "FRED series group name",
                    },
                },
                "required": ["series_group"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_allocation_templates",
            "description": (
                "List all available portfolio allocation templates "
                "(e.g. All Weather, Golden Butterfly, etc.) with their names and descriptions."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_to_template",
            "description": (
                "Compare the user's current portfolio allocation against a named template. "
                "Returns per-bucket deltas and a similarity score."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "template_id": {
                        "type": "string",
                        "description": "Template ID (e.g. 'all_weather', 'golden_butterfly')",
                    },
                },
                "required": ["template_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_rebalance",
            "description": (
                "Given target allocation percentages, compute the dollar trades "
                "needed to rebalance from the user's current allocation. "
                "Returns buy/sell amounts per bucket."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_weights": {
                        "type": "object",
                        "description": (
                            "Target allocation as {bucket: percentage}. "
                            "E.g. {\"Equities\": 50, \"Fixed Income\": 30, \"Real Assets\": 20}"
                        ),
                        "additionalProperties": {"type": "number"},
                    },
                },
                "required": ["target_weights"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_portfolio_history",
            "description": (
                "Get the user's portfolio value over time (daily snapshots). "
                "Returns dates and total values. Useful for analyzing trends, "
                "drawdowns, and growth rate."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days of history (default 90, 0 for all time)",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sector_exposure",
            "description": (
                "Analyze the user's portfolio concentration by asset class bucket. "
                "Returns each bucket's value, weight, and the top holdings within it."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tax_loss_harvest_candidates",
            "description": (
                "Find holdings currently at an unrealized loss that could "
                "potentially be sold for tax-loss harvesting. Includes wash "
                "sale risk flags and substitute ETF suggestions."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_targets",
            "description": (
                "Get the user's saved portfolio allocation targets, current drift "
                "from those targets, and rebalance timeline. Use this to understand "
                "what the user is aiming for before suggesting rebalance trades."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def execute_tool(name, arguments, user_id):
    """Dispatch a tool call to the appropriate handler."""
    args = json.loads(arguments) if isinstance(arguments, str) else arguments
    _user_tools = {
        "compare_to_template", "suggest_rebalance",
        "get_portfolio_history", "get_sector_exposure",
        "get_tax_loss_harvest_candidates", "get_user_targets",
    }
    handlers = {
        "get_ticker_price": _handle_ticker_price,
        "get_market_sentiment": _handle_market_sentiment,
        "get_economic_indicator": _handle_economic_indicator,
        "get_allocation_templates": _handle_allocation_templates,
        "compare_to_template": _handle_compare_to_template,
        "suggest_rebalance": _handle_suggest_rebalance,
        "get_portfolio_history": _handle_portfolio_history,
        "get_sector_exposure": _handle_sector_exposure,
        "get_tax_loss_harvest_candidates": _handle_tlh_candidates,
        "get_user_targets": _handle_user_targets,
    }
    handler = handlers.get(name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {name}"})

    try:
        if name in _user_tools:
            result = handler(args, user_id)
        else:
            result = handler(args)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _handle_ticker_price(args):
    symbol = args.get("symbol", "").upper().strip()
    if not symbol:
        return {"error": "No symbol provided"}
    pc = PriceCache.query.filter_by(symbol=symbol).first()
    if not pc or pc.price is None:
        return {"error": f"No price data found for {symbol}"}
    return {
        "symbol": symbol,
        "price": round(pc.price, 2),
        "change_pct": round(pc.change_pct or 0, 2),
        "prev_close": round(pc.prev_close, 2) if pc.prev_close else None,
        "source": pc.source,
        "updated_at": pc.updated_at.isoformat() if pc.updated_at else None,
    }


def _handle_market_sentiment(_args):
    result = {}
    vix = PriceCache.query.filter_by(symbol="^VIX").first()
    if vix and vix.price:
        result["vix"] = round(vix.price, 2)

    cnn = SentimentCache.query.filter_by(source="cnn_fg").first()
    if cnn and cnn.data:
        result["cnn_fear_greed"] = cnn.data

    crypto_fg = SentimentCache.query.filter_by(source="crypto_fg").first()
    if crypto_fg and crypto_fg.data:
        result["crypto_fear_greed"] = crypto_fg.data

    if not result:
        return {"error": "No sentiment data available"}
    return result


def _handle_economic_indicator(args):
    group = args.get("series_group", "")
    if not group:
        return {"error": "No series_group provided"}
    fc = FredCache.query.filter_by(series_group=group).first()
    if not fc or not fc.data:
        return {"error": f"No FRED data for group '{group}'"}

    summary = {}
    for series_id, values in fc.data.items():
        if isinstance(values, list) and values:
            latest = values[-1]
            summary[series_id] = {
                "date": latest[0] if len(latest) > 0 else None,
                "value": latest[1] if len(latest) > 1 else None,
            }
    return {"series_group": group, "latest_values": summary}


def _handle_allocation_templates(_args):
    templates = _list_templates()
    for t in templates:
        full = _get_template(t["id"])
        if full:
            t["allocations"] = full.get("allocations", {})
    return {"templates": templates}


def _handle_compare_to_template(args, user_id):
    template_id = args.get("template_id", "")
    if not template_id:
        return {"error": "No template_id provided"}

    settings = (
        db.session.query(UserSettings)
        .filter_by(user_id=user_id)
        .first()
    )
    overrides = (
        settings.bucket_rollup
        if settings and hasattr(settings, "bucket_rollup")
        else None
    )

    pv = compute_portfolio_value(user_id)
    breakdown, _ = rollup_breakdown(pv.get("breakdown", {}), overrides=overrides)
    total = pv["total"]

    result = compare_portfolio(template_id, breakdown, total)
    if not result:
        return {"error": f"Template '{template_id}' not found"}
    return result


def _build_bucket_holdings(user_id):
    """Build a complete {bucket: [holdings…]} dict across all asset types.

    Used by suggest_rebalance and sector_exposure so the AI sees every
    position, not just Holding rows.
    """
    from ..utils.buckets import normalize_bucket as _nb

    holdings = Holding.query.filter_by(user_id=user_id).all()
    tickers = list({h.ticker for h in holdings if h.ticker})
    price_map = {}
    if tickers:
        price_map = {
            r.symbol: r.price
            for r in PriceCache.query.filter(PriceCache.symbol.in_(tickers)).all()
            if r.price
        }

    bucket_holdings = {}
    for h in holdings:
        if h.value_override:
            val = h.value_override
        elif h.shares:
            val = h.shares * (price_map.get(h.ticker) or 0)
        else:
            val = 0
        b = h.bucket or "Other"
        bucket_holdings.setdefault(b, []).append({
            "ticker": h.ticker,
            "shares": round(h.shares or 0, 2),
            "value": round(val, 2),
            "cost_basis": round(h.cost_basis or 0, 2) if h.cost_basis else None,
        })

    crypto = CryptoHolding.query.filter_by(user_id=user_id).all()
    for c in crypto:
        cg_key = f"CG:{c.coingecko_id}" if c.coingecko_id else f"CG:{c.symbol.lower()}"
        pc = PriceCache.query.filter_by(symbol=cg_key).first()
        price = pc.price if pc and pc.price else 0
        val = c.quantity * price
        bucket_holdings.setdefault("Crypto", []).append({
            "ticker": c.symbol,
            "shares": round(c.quantity, 4),
            "value": round(val, 2),
            "cost_basis": round(c.cost_basis or 0, 2) if c.cost_basis else None,
        })

    metals = PhysicalMetal.query.filter_by(user_id=user_id).all()
    gold_oz, silver_oz = 0.0, 0.0
    for m in metals:
        if m.metal.lower() == "gold":
            gold_oz += m.oz
        else:
            silver_oz += m.oz
    if gold_oz:
        pc = PriceCache.query.get("GC=F")
        gp = pc.price if pc and pc.price else 0
        bucket_holdings.setdefault("Gold", []).append({
            "ticker": "Physical Gold",
            "shares": round(gold_oz, 2),
            "value": round(gold_oz * gp, 2),
            "cost_basis": None,
        })
    if silver_oz:
        pc = PriceCache.query.get("SI=F")
        sp = pc.price if pc and pc.price else 0
        bucket_holdings.setdefault("Silver", []).append({
            "ticker": "Physical Silver",
            "shares": round(silver_oz, 2),
            "value": round(silver_oz * sp, 2),
            "cost_basis": None,
        })

    blended = BlendedAccount.query.filter_by(user_id=user_id).all()
    for b in blended:
        alloc = b.allocations or {}
        if "asset_class" in alloc:
            bucket = _nb(alloc["asset_class"]) or "Other"
            bucket_holdings.setdefault(bucket, []).append({
                "ticker": b.name,
                "shares": None,
                "value": round(b.value, 2),
                "cost_basis": None,
            })
        elif alloc:
            for raw_bucket, pct in alloc.items():
                try:
                    pct_val = float(pct)
                except (TypeError, ValueError):
                    continue
                bucket = _nb(raw_bucket) or "Other"
                bucket_holdings.setdefault(bucket, []).append({
                    "ticker": f"{b.name} ({bucket} slice)",
                    "shares": None,
                    "value": round(b.value * pct_val / 100, 2),
                    "cost_basis": None,
                })
        else:
            bucket_holdings.setdefault("Other", []).append({
                "ticker": b.name,
                "shares": None,
                "value": round(b.value, 2),
                "cost_basis": None,
            })

    accounts = Account.query.filter_by(user_id=user_id).all()
    for a in accounts:
        if a.account_type in ("checking", "savings"):
            bucket_holdings.setdefault("Cash", []).append({
                "ticker": a.name,
                "shares": None,
                "value": round(a.balance, 2),
                "cost_basis": None,
            })

    for bh in bucket_holdings.values():
        bh.sort(key=lambda x: -x["value"])

    return bucket_holdings


def _handle_suggest_rebalance(args, user_id):
    from ..utils.buckets import normalize_bucket as _nb_reb

    target_weights = args.get("target_weights", {})
    if not target_weights:
        return {"error": "No target_weights provided"}

    total_pct = sum(target_weights.values())
    if abs(total_pct - 100) > 1:
        return {"error": f"Target weights sum to {total_pct}%, should be ~100%"}

    settings = (
        db.session.query(UserSettings)
        .filter_by(user_id=user_id)
        .first()
    )
    overrides = (
        settings.bucket_rollup
        if settings and hasattr(settings, "bucket_rollup")
        else None
    )

    pv = compute_portfolio_value(user_id)
    raw_breakdown = pv.get("breakdown", {})
    rolled_breakdown, _ = rollup_breakdown(raw_breakdown, overrides=overrides)
    total = pv["total"]

    if total == 0:
        return {"error": "Portfolio is empty. Add holdings first."}

    has_child_targets = any(
        _nb_reb(b) not in rolled_breakdown and _nb_reb(b) in raw_breakdown
        for b in target_weights
    )
    breakdown = raw_breakdown if has_child_targets else rolled_breakdown

    bucket_holdings = _build_bucket_holdings(user_id)

    trades = []
    for bucket, target_pct in sorted(target_weights.items()):
        normed = _nb_reb(bucket) or bucket
        current_val = breakdown.get(normed, 0)
        current_pct = current_val / total * 100 if total > 0 else 0
        target_val = total * target_pct / 100
        delta_val = target_val - current_val
        action = "buy" if delta_val > 0 else "sell" if delta_val < 0 else "hold"
        trades.append({
            "bucket": normed,
            "current_pct": round(current_pct, 1),
            "target_pct": target_pct,
            "current_value": round(current_val, 2),
            "target_value": round(target_val, 2),
            "trade_amount": round(abs(delta_val), 2),
            "action": action,
            "holdings": bucket_holdings.get(normed, [])[:5],
        })

    return {
        "portfolio_total": round(total, 2),
        "trades": trades,
    }


def _handle_portfolio_history(args, user_id):
    days = args.get("days", 90)
    query = (
        PortfolioSnapshot.query
        .filter(PortfolioSnapshot.user_id == user_id)
    )
    if days and days > 0:
        cutoff = date.today() - timedelta(days=days)
        query = query.filter(PortfolioSnapshot.date >= cutoff)
    snaps = query.order_by(PortfolioSnapshot.date).all()

    if not snaps:
        return {"error": "No portfolio history available yet"}

    points = []
    for s in snaps:
        points.append({
            "date": s.date.isoformat(),
            "total": round(s.total, 2),
        })

    first_val = snaps[0].total or 0
    last_val = snaps[-1].total or 0
    peak = max(s.total for s in snaps) if snaps else 0
    trough = min(s.total for s in snaps) if snaps else 0

    growth_pct = ((last_val - first_val) / first_val * 100) if first_val else 0
    max_drawdown_pct = ((trough - peak) / peak * 100) if peak else 0

    max_points = 120
    sampled = points
    if len(points) > max_points:
        step = len(points) / max_points
        sampled = [points[int(i * step)] for i in range(max_points - 1)]
        sampled.append(points[-1])

    return {
        "days": days if days and days > 0 else (snaps[-1].date - snaps[0].date).days,
        "data_points": len(points),
        "first": points[0] if points else None,
        "last": points[-1] if points else None,
        "peak": round(peak, 2),
        "trough": round(trough, 2),
        "growth_pct": round(growth_pct, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "history": sampled,
    }


def _handle_sector_exposure(args, user_id):
    settings = (
        db.session.query(UserSettings)
        .filter_by(user_id=user_id)
        .first()
    )
    overrides = (
        settings.bucket_rollup
        if settings and hasattr(settings, "bucket_rollup")
        else None
    )

    pv = compute_portfolio_value(user_id)
    raw_breakdown = pv.get("breakdown", {})
    rolled_breakdown, children = rollup_breakdown(raw_breakdown, overrides=overrides)
    total = pv["total"]

    if total == 0:
        return {"error": "Portfolio is empty"}

    bucket_holdings = _build_bucket_holdings(user_id)

    buckets = []
    for bucket in sorted(rolled_breakdown.keys(),
                         key=lambda b: -rolled_breakdown[b]):
        bval = rolled_breakdown[bucket]
        top = bucket_holdings.get(bucket, [])[:5]
        child_detail = []
        if bucket in children:
            for child_name, child_val in sorted(
                children[bucket].items(), key=lambda x: -x[1]
            ):
                child_detail.append({
                    "bucket": child_name,
                    "value": round(child_val, 2),
                    "weight_pct": round(child_val / total * 100, 1),
                    "top_holdings": bucket_holdings.get(child_name, [])[:3],
                })
        buckets.append({
            "bucket": bucket,
            "value": round(bval, 2),
            "weight_pct": round(bval / total * 100, 1),
            "top_holdings": top,
            "children": child_detail,
        })

    return {
        "portfolio_total": round(total, 2),
        "bucket_count": len(buckets),
        "buckets": buckets,
    }


_SUBSTITUTE_ETFS = {
    "SPY": "IVV", "IVV": "VOO", "VOO": "SPY",
    "QQQ": "QQQM", "QQQM": "QQQ",
    "VTI": "ITOT", "ITOT": "VTI",
    "SCHB": "VTI", "SPTM": "VTI",
    "VEA": "IEFA", "IEFA": "VEA",
    "VXUS": "IXUS", "IXUS": "VXUS",
    "VWO": "IEMG", "IEMG": "VWO",
    "BND": "AGG", "AGG": "BND",
    "VCIT": "LQD", "LQD": "VCIT",
    "TLT": "VGLT", "VGLT": "TLT",
    "GLD": "IAU", "IAU": "GLD",
    "SLV": "SIVR", "SIVR": "SLV",
    "VNQ": "IYR", "IYR": "VNQ",
    "XLE": "VDE", "VDE": "XLE",
    "XLK": "VGT", "VGT": "XLK",
    "XLF": "VFH", "VFH": "XLF",
    "XLV": "VHT", "VHT": "XLV",
    "ARKK": "QQQM",
}


def _handle_tlh_candidates(args, user_id):
    holdings = Holding.query.filter_by(user_id=user_id).all()
    tickers = list({h.ticker for h in holdings if h.ticker})
    price_map = {}
    if tickers:
        price_map = {
            r.symbol: r.price
            for r in PriceCache.query.filter(
                PriceCache.symbol.in_(tickers)
            ).all()
            if r.price
        }

    now = datetime.now(timezone.utc)
    wash_window = now - timedelta(days=30)
    recent_tickers = set()
    for h in holdings:
        added = h.added_at
        if added and added.tzinfo is None:
            added = added.replace(tzinfo=timezone.utc)
        if added and added >= wash_window:
            recent_tickers.add(h.ticker)

    candidates = []
    total_loss = 0
    for h in holdings:
        qty = h.shares or 0
        cost_per = h.cost_basis or 0
        if not qty or not cost_per:
            continue
        live_price = price_map.get(h.ticker, 0)
        if not live_price:
            continue
        unrealized = (live_price - cost_per) * qty
        if unrealized < -50:
            wash_risk = h.ticker in recent_tickers
            substitute = _SUBSTITUTE_ETFS.get(h.ticker)
            candidates.append({
                "ticker": h.ticker,
                "shares": round(qty, 3),
                "cost_basis_per_share": round(cost_per, 2),
                "current_price": round(live_price, 2),
                "unrealized_loss": round(unrealized, 2),
                "wash_sale_risk": wash_risk,
                "substitute_etf": substitute,
            })
            total_loss += unrealized

    candidates.sort(key=lambda r: r["unrealized_loss"])
    est_tax_savings = round(abs(total_loss) * 0.25, 2) if total_loss < 0 else 0

    if not candidates:
        return {"message": "No tax-loss harvesting candidates found (all positions are above cost basis or losses are under $50)."}

    return {
        "candidates": candidates,
        "total_unrealized_loss": round(total_loss, 2),
        "estimated_tax_savings_25pct": est_tax_savings,
        "note": "Estimated savings assume a 25% marginal tax rate. Wash sale risk means the same ticker was purchased within the last 30 days.",
    }


def _handle_user_targets(args, user_id):
    settings = (
        db.session.query(UserSettings)
        .filter_by(user_id=user_id)
        .first()
    )
    if not settings or not settings.targets:
        return {"error": "No allocation targets have been set yet."}

    targets = settings.targets
    active = targets.get("tactical", targets.get("catchup", {}))
    if not active:
        return {"error": "No allocation targets have been set yet."}

    overrides = (
        settings.bucket_rollup
        if hasattr(settings, "bucket_rollup")
        else None
    )

    pv = compute_portfolio_value(user_id)
    breakdown, _ = rollup_breakdown(pv.get("breakdown", {}), overrides=overrides)
    total = pv["total"]

    target_weights = {}
    drift = {}
    for bucket, v in active.items():
        pct = v.get("target", v) if isinstance(v, dict) else v
        target_weights[bucket] = pct
        current_pct = round(breakdown.get(bucket, 0) / total * 100, 1) if total > 0 else 0
        drift[bucket] = {
            "target_pct": pct,
            "current_pct": current_pct,
            "drift_pct": round(current_pct - pct, 1),
            "drift_dollars": round((current_pct - pct) / 100 * total, 2),
        }

    rebalance_months = settings.rebalance_months or 12

    return {
        "portfolio_total": round(total, 2),
        "target_weights": target_weights,
        "drift": drift,
        "rebalance_months": rebalance_months,
    }
