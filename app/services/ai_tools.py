"""OpenAI function-calling tool definitions and handlers for the AI advisor.

Each tool reuses existing service code so the AI can pull live data
on demand during a conversation.
"""

import json

from ..extensions import db
from ..models.market import PriceCache, SentimentCache, FredCache
from ..models.portfolio import Holding
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
]


def execute_tool(name, arguments, user_id):
    """Dispatch a tool call to the appropriate handler."""
    args = json.loads(arguments) if isinstance(arguments, str) else arguments
    handlers = {
        "get_ticker_price": _handle_ticker_price,
        "get_market_sentiment": _handle_market_sentiment,
        "get_economic_indicator": _handle_economic_indicator,
        "get_allocation_templates": _handle_allocation_templates,
        "compare_to_template": _handle_compare_to_template,
        "suggest_rebalance": _handle_suggest_rebalance,
    }
    handler = handlers.get(name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {name}"})

    try:
        if name in ("compare_to_template", "suggest_rebalance"):
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


def _handle_suggest_rebalance(args, user_id):
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
    breakdown, _ = rollup_breakdown(pv.get("breakdown", {}), overrides=overrides)
    total = pv["total"]

    if total == 0:
        return {"error": "Portfolio is empty — add holdings first"}

    trades = []
    for bucket, target_pct in sorted(target_weights.items()):
        current_val = breakdown.get(bucket, 0)
        current_pct = current_val / total * 100 if total > 0 else 0
        target_val = total * target_pct / 100
        delta_val = target_val - current_val
        action = "buy" if delta_val > 0 else "sell" if delta_val < 0 else "hold"
        trades.append({
            "bucket": bucket,
            "current_pct": round(current_pct, 1),
            "target_pct": target_pct,
            "current_value": round(current_val, 2),
            "target_value": round(target_val, 2),
            "trade_amount": round(abs(delta_val), 2),
            "action": action,
        })

    return {
        "portfolio_total": round(total, 2),
        "trades": trades,
    }
