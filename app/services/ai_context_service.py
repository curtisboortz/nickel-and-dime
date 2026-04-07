"""Builds the system prompt and portfolio context for the AI advisor.

Assembles data from portfolio, insights, snapshots, targets, and
holdings into a structured context string for the OpenAI system message.
"""

from datetime import date, timedelta

from ..extensions import db
from ..models.portfolio import Holding, CryptoHolding
from ..models.market import PriceCache, SentimentCache
from ..models.settings import UserSettings
from ..models.snapshot import PortfolioSnapshot
from ..services.insights_service import generate_insights
from ..services.portfolio_service import compute_portfolio_value
from ..utils.buckets import rollup_breakdown

SYSTEM_PROMPT = """\
You are a senior portfolio analyst embedded in Nickel&Dime, a personal finance dashboard. \
You have access to the user's full portfolio data, market data, and economic indicators via tools.

Your capabilities:
- Analyze portfolio risk, concentration, and diversification
- Look up live ticker prices and market sentiment
- Query economic indicators (FRED data)
- Compare portfolios against classic allocation templates
- Suggest specific allocation changes and rebalancing trades

Rules:
- Be direct and opinionated. You're an analyst, not a compliance officer.
- Reference the user's actual numbers when giving advice.
- Use **bold** for key terms and numbers.
- When suggesting trades, be specific: name tickers/asset classes, dollar amounts, and percentages.
- If asked to build a portfolio, provide a concrete allocation with percentages and explain why.
- Keep responses focused and concise — under 400 words unless the user asks for detail.
- Use tools to look up data rather than guessing. If you need a price, sentiment score, or FRED series, call the tool.
- Never fabricate data. If a tool returns no result, say so.
- Format lists and tables with markdown when helpful."""


def build_system_messages(user_id):
    """Return the system message list for a new conversation.

    Includes the base system prompt plus a portfolio context snapshot.
    """
    context = _build_portfolio_context(user_id)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Current portfolio snapshot:\n\n{context}"},
    ]


def _build_portfolio_context(user_id):
    """Assemble a compact text representation of the user's portfolio."""
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

    insights = generate_insights(user_id, overrides=overrides)
    pv = compute_portfolio_value(user_id)

    lines = []

    total = insights.get("total", 0)
    risk = insights.get("risk_score", {})
    div_r = insights.get("diversification_ratio", {})
    conc = insights.get("concentration", {})
    weights = insights.get("weights", {})

    lines.append(f"Portfolio total: ${total:,.2f}")
    lines.append(f"Risk score: {risk.get('score', 0)}/100 ({risk.get('label', 'N/A')})")
    lines.append(f"Est. annual volatility: {risk.get('vol', 0)}%")
    lines.append(f"Diversification ratio: {div_r.get('ratio', 1.0)}x ({div_r.get('label', 'N/A')})")
    lines.append(f"Asset classes: {conc.get('bucket_count', 0)}")
    lines.append("")

    lines.append("Allocation weights:")
    for bucket, w in sorted(weights.items(), key=lambda x: -x[1]):
        lines.append(f"  {bucket}: {w * 100:.1f}%")

    holdings = (
        Holding.query.filter_by(user_id=user_id)
        .order_by(Holding.bucket)
        .all()
    )
    if holdings:
        lines.append("")
        lines.append("Top holdings:")
        valued = []
        for h in holdings:
            if h.value_override:
                val = h.value_override
            elif h.shares:
                pc = PriceCache.query.filter_by(symbol=h.ticker).first()
                val = h.shares * (pc.price if pc and pc.price else 0)
            else:
                val = 0
            valued.append((h, val))
        valued.sort(key=lambda x: -x[1])
        for h, val in valued[:15]:
            cost = f", cost ${h.cost_basis:,.2f}/sh" if h.cost_basis else ""
            lines.append(
                f"  {h.ticker} — {h.shares or 0:.2f} shares, "
                f"${val:,.0f} ({h.bucket}){cost}"
            )

    crypto = CryptoHolding.query.filter_by(user_id=user_id).all()
    if crypto:
        lines.append("")
        lines.append("Crypto holdings:")
        for c in crypto:
            lines.append(f"  {c.symbol} — {c.quantity:.4f}")

    if settings and settings.targets:
        tactical = settings.targets.get("tactical", {})
        if tactical:
            lines.append("")
            lines.append("Allocation targets (tactical):")
            for bucket, v in sorted(tactical.items()):
                pct = v.get("target", v) if isinstance(v, dict) else v
                lines.append(f"  {bucket}: {pct}%")

    warnings = conc.get("warnings", [])
    if warnings:
        lines.append("")
        lines.append("Concentration warnings:")
        for w in warnings:
            lines.append(f"  - {w.get('msg', '')}")

    snapshots = _recent_snapshots(user_id)
    if snapshots:
        lines.append("")
        lines.append("Portfolio value trend (last 30 days):")
        for s in snapshots:
            lines.append(f"  {s.date.isoformat()}: ${s.total:,.0f}")

    return "\n".join(lines)


def _recent_snapshots(user_id, days=30):
    """Return the last N days of portfolio snapshots."""
    cutoff = date.today() - timedelta(days=days)
    return (
        PortfolioSnapshot.query
        .filter(
            PortfolioSnapshot.user_id == user_id,
            PortfolioSnapshot.date >= cutoff,
        )
        .order_by(PortfolioSnapshot.date)
        .all()
    )
