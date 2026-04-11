"""Builds the system prompt and portfolio context for the AI advisor.

Assembles data from portfolio, insights, snapshots, targets, and
holdings into a structured context string for the OpenAI system message.
"""

from datetime import date, timedelta
from pathlib import Path

from ..extensions import db
from ..models.portfolio import Holding, CryptoHolding, PhysicalMetal, BlendedAccount, Account
from ..models.market import PriceCache, SentimentCache
from ..models.settings import UserSettings
from ..models.snapshot import PortfolioSnapshot
from ..services.insights_service import generate_insights
from ..utils.buckets import rollup_breakdown

_KB_PATH = Path(__file__).resolve().parent.parent / "data" / "investment_frameworks.md"
_INVESTMENT_KB = _KB_PATH.read_text(encoding="utf-8")

SYSTEM_PROMPT = """\
You are a portfolio research assistant embedded in Nickel&Dime, a personal finance \
dashboard. You have access to the user's portfolio data, market data, and economic \
indicators via tools. You provide educational analysis and opinions informed by \
well-known investment frameworks. You are NOT a licensed financial advisor.

## Important Disclaimer (follow strictly)
- You provide **educational information and personal opinions only**, not professional \
financial advice. Always frame suggestions as ideas to consider, not directives.
- You are not a registered investment advisor, broker-dealer, or financial planner.
- Remind the user at the end of substantive analyses: \
"*This is educational commentary, not financial advice. Consider consulting a \
qualified financial advisor before making investment decisions.*"
- Never say "you should" as a command. Use language like "you might consider," \
"one approach would be," "historically this has worked because," or "in my opinion."

## Analytical Frameworks

You have a detailed investment knowledge base (provided in a separate system \
message) covering the following cornerstone investors and their works. Apply \
their principles contextually when relevant to the user's portfolio:

- **Benjamin Graham** — margin of safety, Mr. Market, defensive investor criteria
- **Warren Buffett** — economic moats, circle of competence, owner earnings
- **Charlie Munger** — inversion, second-order thinking, quality over cheapness
- **Ray Dalio** — risk parity, All Weather, four economic quadrants, Holy Grail
- **Howard Marks** — second-level thinking, the pendulum, risk as permanent loss
- **Bill Ackman** — concentrated value, simple businesses, catalyst-driven investing
- **Peter Lynch** — invest in what you know, PEG ratio, six stock categories
- **John Bogle** — cost drag, indexing, reversion to the mean, stay the course

When citing a framework, reference the specific principle by name (e.g., \
"Graham's Mr. Market concept," "Dalio's four-quadrant model," "Lynch's PEG \
ratio") rather than generic attribution.

**Portfolio Construction Principles:**
- Rebalancing systematically captures the buy-low-sell-high discipline
- Tax-loss harvesting is a valuable tool when done correctly (watch wash sale rules)
- Cash is a legitimate position: it represents optionality during drawdowns
- International diversification reduces single-country political and currency risk
- Bonds historically serve three roles: income, deflation hedge, and rebalancing fuel

**Rebalancing Execution — Scale In / Scale Out:**
- Large rebalancing moves should be spread over multiple transactions, not executed \
all at once. Recommend phased approaches (e.g. "over 2-4 weeks" or "in 3-4 tranches").
- For positions larger than 5% of the portfolio, always suggest scaling in or out \
gradually to manage timing risk and reduce market impact.
- Never recommend liquidating an entire position in one trade unless it is very small \
(<1% of portfolio) or the thesis is clearly broken.
- When recommending sells, **always verify the suggested dollar amount and share count \
against the actual holding size shown in the portfolio data**. Never suggest selling \
more than the user actually owns.
- Frame rebalancing as a process, not a single event: "consider trimming X by $Y over \
the next few weeks" rather than "sell $Z of X today."

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
and percentages, framed as ideas to explore, not instructions.
- When discussing rebalancing, watchlists, or positioning, go beyond bucket names: \
suggest specific tickers (ETFs, individual stocks) as ideas to explore. Reference the \
user's existing holdings and well-known options in each asset class. For example, \
instead of "add to Equities," say "you might consider adding to VOO or VTI in your \
Equities bucket." Frame all ticker suggestions as opinions, not recommendations.
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

    Includes the base system prompt, the investment knowledge base,
    and a portfolio context snapshot.
    """
    context = _build_portfolio_context(user_id)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Investment knowledge base:\n\n{_INVESTMENT_KB}"},
        {"role": "system", "content": f"Current portfolio snapshot:\n\n{context}"},
    ]


def _build_portfolio_context(user_id):
    """Assemble a compact text representation of the user's portfolio."""
    from ..services.portfolio_service import compute_portfolio_value
    from ..utils.buckets import normalize_bucket

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

    pv = compute_portfolio_value(user_id)
    raw_breakdown = pv.get("breakdown", {})
    rolled, children = rollup_breakdown(raw_breakdown, overrides)

    lines.append("Allocation weights (rolled-up parent buckets):")
    for bucket, w in sorted(weights.items(), key=lambda x: -x[1]):
        lines.append(f"  {bucket}: {w * 100:.1f}%")

    has_children = any(children.values())
    if has_children and total > 0:
        lines.append("")
        lines.append("Detailed allocation (child buckets before rollup):")
        for bucket, val in sorted(raw_breakdown.items(),
                                  key=lambda x: -x[1]):
            normed = normalize_bucket(bucket)
            pct = val / total * 100
            lines.append(f"  {normed}: {pct:.1f}% (${val:,.0f})")

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
                f"  {h.ticker}: {h.shares or 0:.2f} shares, "
                f"${val:,.0f} ({h.bucket}){cost}"
            )

    crypto = CryptoHolding.query.filter_by(user_id=user_id).all()
    if crypto:
        lines.append("")
        lines.append("Crypto holdings (bucket: Crypto):")
        for c in crypto:
            cg_key = f"CG:{c.coingecko_id}" if c.coingecko_id else f"CG:{c.symbol.lower()}"
            pc = PriceCache.query.filter_by(symbol=cg_key).first()
            price = pc.price if pc and pc.price else 0
            val = c.quantity * price
            cost_str = f", cost ${c.cost_basis:,.2f}" if c.cost_basis else ""
            lines.append(f"  {c.symbol}: {c.quantity:.4f}, ${val:,.0f}{cost_str} (source: {c.source})")

    metals = PhysicalMetal.query.filter_by(user_id=user_id).all()
    if metals:
        lines.append("")
        lines.append("Physical metals:")
        gold_oz, silver_oz = 0, 0
        for m in metals:
            if m.metal.lower() == "gold":
                gold_oz += m.oz
            else:
                silver_oz += m.oz
        gold_pc = PriceCache.query.get("GC=F")
        silver_pc = PriceCache.query.get("SI=F")
        if gold_oz > 0:
            gold_price = gold_pc.price if gold_pc and gold_pc.price else 0
            lines.append(f"  Gold: {gold_oz:.2f} oz, ${gold_oz * gold_price:,.0f} (bucket: Gold)")
        if silver_oz > 0:
            silver_price = silver_pc.price if silver_pc and silver_pc.price else 0
            lines.append(f"  Silver: {silver_oz:.2f} oz, ${silver_oz * silver_price:,.0f} (bucket: Silver)")

    blended = BlendedAccount.query.filter_by(user_id=user_id).all()
    if blended:
        lines.append("")
        lines.append("Blended / alternative accounts:")
        for b in blended:
            alloc = b.allocations or {}
            asset_class = alloc.get("asset_class", "")
            if asset_class:
                lines.append(f"  {b.name}: ${b.value:,.0f} (bucket: {asset_class})")
            elif alloc:
                splits = ", ".join(f"{k} {v}%" for k, v in alloc.items())
                lines.append(f"  {b.name}: ${b.value:,.0f} (split: {splits})")
            else:
                lines.append(f"  {b.name}: ${b.value:,.0f}")

    accounts = Account.query.filter_by(user_id=user_id).all()
    cash_accounts = [a for a in accounts if a.account_type in ("checking", "savings")]
    if cash_accounts:
        lines.append("")
        lines.append("Cash accounts (bucket: Cash):")
        for a in cash_accounts:
            lines.append(f"  {a.name}: ${a.balance:,.0f}")

    if settings and settings.targets:
        active = settings.targets.get("tactical", settings.targets.get("catchup", {}))
        if active:
            lines.append("")
            lines.append("User's allocation targets:")
            for bucket, v in sorted(active.items()):
                pct = v.get("target", v) if isinstance(v, dict) else v
                lines.append(f"  {bucket}: {pct}%")
    if settings and settings.rebalance_months:
        lines.append(f"Rebalance timeline: {settings.rebalance_months} months")

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
