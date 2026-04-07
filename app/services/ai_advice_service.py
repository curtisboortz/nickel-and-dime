"""AI Portfolio Advisor — sends portfolio context to OpenAI and
returns personalised investment advice.

Requires OPENAI_API_KEY to be set in the environment / app config.
"""

from flask import current_app
from openai import OpenAI

from .insights_service import generate_insights

SYSTEM_PROMPT = """You are a portfolio research assistant in Nickel&Dime, a personal \
finance dashboard. You provide educational analysis and opinions, NOT professional \
financial advice. The user will give you a snapshot of their portfolio analytics.

Rules:
- Write 4-6 short paragraphs. Use **bold** for key terms.
- Reference the user's actual numbers (weights, risk score, volatility, diversification ratio).
- Identify the biggest risk and the biggest opportunity in their current allocation.
- Frame suggestions as ideas to consider, not directives (e.g., "You might consider \
shifting 5-10% from Equities into Fixed Income to reduce volatility").
- When relevant, connect your analysis to well-known frameworks (Dalio's risk parity, \
Bogle's indexing philosophy, Graham's margin of safety, Marks' cycle awareness).
- If concentration warnings exist, address them directly.
- End with a one-sentence overall assessment and a brief reminder that this is \
educational commentary, not professional financial advice.
- Keep the total response under 300 words."""


def get_ai_advice(user_id, overrides=None):
    """Generate AI portfolio advice via OpenAI.

    Returns a dict with 'advice' (str) on success,
    or 'error' (str) on failure.
    """
    api_key = current_app.config.get("OPENAI_API_KEY", "")
    if not api_key:
        return {"error": "no_key"}

    insights = generate_insights(user_id, overrides=overrides)
    if insights.get("total", 0) == 0:
        return {"advice": "Add holdings to your portfolio before requesting AI advice."}

    portfolio_context = _build_context(insights)

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": portfolio_context},
        ],
        temperature=0.6,
        max_tokens=800,
    )

    advice_text = response.choices[0].message.content.strip()
    return {"advice": advice_text}


def _build_context(insights):
    """Build a compact text summary of the portfolio for the prompt."""
    w = insights.get("weights", {})
    risk = insights.get("risk_score", {})
    conc = insights.get("concentration", {})
    div_r = insights.get("diversification_ratio", {})

    lines = [
        f"Portfolio total: ${insights.get('total', 0):,.2f}",
        f"Risk score: {risk.get('score', 0)}/100 ({risk.get('label', 'N/A')})",
        f"Estimated annual volatility: {risk.get('vol', 0)}%",
        f"Diversification ratio: {div_r.get('ratio', 1.0)}x ({div_r.get('label', 'N/A')})",
        f"Asset classes: {conc.get('bucket_count', 0)}",
        "",
        "Allocation weights:",
    ]
    for bucket, weight in sorted(w.items(), key=lambda x: -x[1]):
        lines.append(f"  {bucket}: {weight * 100:.1f}%")

    warnings = conc.get("warnings", [])
    if warnings:
        lines.append("")
        lines.append("Concentration warnings:")
        for warn in warnings:
            lines.append(f"  - {warn.get('msg', '')}")

    summaries = insights.get("summaries", [])
    if summaries:
        lines.append("")
        lines.append("Current analysis notes:")
        for s in summaries:
            lines.append(f"  - {s}")

    return "\n".join(lines)
