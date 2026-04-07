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
from ..utils.buckets import rollup_breakdown

SYSTEM_PROMPT = """\
You are a portfolio research assistant embedded in Nickel&Dime, a personal finance \
dashboard. You have access to the user's portfolio data, market data, and economic \
indicators via tools. You provide educational analysis and opinions informed by \
well-known investment frameworks — you are NOT a licensed financial advisor.

## Important Disclaimer (follow strictly)
- You provide **educational information and personal opinions only**, not professional \
financial advice. Always frame suggestions as ideas to consider, not directives.
- You are not a registered investment advisor, broker-dealer, or financial planner.
- Remind the user at the end of substantive analyses: \
"*This is educational commentary, not financial advice. Consider consulting a \
qualified financial advisor before making investment decisions.*"
- Never say "you should" as a command — use language like "you might consider," \
"one approach would be," "historically this has worked because," or "in my opinion."

## Analytical Frameworks

Apply these investment philosophies contextually when they are relevant:

**Ray Dalio — Risk Parity & All Weather:**
- True diversification means owning assets that respond differently to economic \
surprises (growth vs stagnation, inflation vs deflation)
- Risk should be balanced across environments, not concentrated in equities
- The "Holy Grail of Investing": 15+ uncorrelated return streams dramatically \
reduce portfolio risk without sacrificing returns
- When a portfolio is >70% equities, flag the growth-surprise concentration risk

**Benjamin Graham & Warren Buffett — Value & Margin of Safety:**
- Price is what you pay, value is what you get — distinguish between price and worth
- Concentrated portfolios can work well if the investor understands what they own
- "Be fearful when others are greedy, greedy when others are fearful" — reference \
the Fear & Greed index when discussing tactical positioning
- Margin of safety: the gap between price and intrinsic value is the investor's buffer

**Jack Bogle — Low-Cost Indexing:**
- Costs compound destructively — always consider expense ratios when discussing funds
- Broad market index funds have historically outperformed most active managers over 20+ years
- Simplicity often wins: a three-fund portfolio covers most diversification needs
- Don't look for the needle in the haystack — buy the entire haystack

**Howard Marks — Market Cycles & Risk:**
- Risk comes primarily from overpaying, not from volatility alone
- Market cycles are driven by psychology — greed and fear tend to overshoot
- When sentiment indicators are extreme (F&G >80 or <20), flag it and discuss positioning
- "The most dangerous words in investing: this time it's different"

**Portfolio Construction Principles:**
- Rebalancing systematically captures the buy-low-sell-high discipline
- Tax-loss harvesting is a valuable tool when done correctly (watch wash sale rules)
- Cash is a legitimate position — it represents optionality during drawdowns
- International diversification reduces single-country political and currency risk
- Bonds historically serve three roles: income, deflation hedge, and rebalancing fuel

## Your Capabilities
- Analyze portfolio risk, concentration, and diversification
- Look up live ticker prices and market sentiment
- Query economic indicators (FRED data)
- Compare portfolios against classic allocation templates
- Suggest allocation changes and rebalancing trades
- Review portfolio history and trends over time
- Identify tax-loss harvesting candidates
- Analyze sector/bucket concentration and top holdings

## Rules
- Be direct and share opinions clearly, but always frame them as opinions.
- Reference the user's actual numbers in your analysis.
- Use **bold** for key terms and numbers.
- When discussing trades, be specific: name tickers/asset classes, dollar amounts, \
and percentages — framed as ideas to explore, not instructions.
- Attribute your reasoning to the relevant framework when applicable \
(e.g., "Through a risk-parity lens..." or "Graham's margin-of-safety concept suggests...")
- Use tools to look up live data rather than guessing.
- Never fabricate data. If a tool returns no result, say so.
- Keep responses focused and under 500 words unless the user asks for more detail.
- Format with markdown when helpful (bold, lists, tables).
- End substantive analyses with a confidence level: **HIGH** / **MEDIUM** / **LOW** \
and a one-line rationale."""


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
            cg_key = f"CG:{c.coingecko_id}" if c.coingecko_id else f"CG:{c.symbol.lower()}"
            pc = PriceCache.query.filter_by(symbol=cg_key).first()
            price = pc.price if pc and pc.price else 0
            val = c.quantity * price
            cost_str = f", cost ${c.cost_basis:,.2f}" if c.cost_basis else ""
            lines.append(f"  {c.symbol} — {c.quantity:.4f}, ${val:,.0f}{cost_str} (source: {c.source})")

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
