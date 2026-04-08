"""AI Portfolio Insights — risk scoring, concentration analysis,
correlation estimation, and plain-English summaries.

No external AI API needed: all analytics are computed from the
user's holdings, price history, and allocation data.
"""

import math
from collections import defaultdict

from ..models.portfolio import Holding, CryptoHolding, Account
from ..models.market import PriceCache
from ..models.snapshot import PortfolioSnapshot
from ..services.portfolio_service import compute_portfolio_value
from ..utils.buckets import rollup_breakdown, normalize_bucket


ASSET_CLASS_CORRELATIONS = {
    ("Equities", "Fixed Income"): -0.20,
    ("Equities", "Gold"): 0.05,
    ("Equities", "Real Assets"): 0.25,
    ("Equities", "Real Estate"): 0.60,
    ("Equities", "Crypto"): 0.45,
    ("Equities", "Cash"): 0.00,
    ("Equities", "Alternatives"): 0.35,
    ("Equities", "International"): 0.85,
    ("Fixed Income", "Gold"): 0.15,
    ("Fixed Income", "Real Assets"): 0.10,
    ("Fixed Income", "Real Estate"): 0.20,
    ("Fixed Income", "Crypto"): -0.10,
    ("Fixed Income", "Cash"): 0.30,
    ("Fixed Income", "Alternatives"): 0.05,
    ("Fixed Income", "International"): -0.15,
    ("Gold", "Real Assets"): 0.85,
    ("Gold", "Real Estate"): 0.10,
    ("Gold", "Crypto"): 0.15,
    ("Gold", "Cash"): 0.05,
    ("Gold", "Alternatives"): 0.20,
    ("Gold", "International"): 0.10,
    ("Real Assets", "Real Estate"): 0.20,
    ("Real Assets", "Crypto"): 0.15,
    ("Real Assets", "Cash"): 0.05,
    ("Real Assets", "Alternatives"): 0.25,
    ("Real Assets", "International"): 0.15,
    ("Real Estate", "Crypto"): 0.10,
    ("Real Estate", "Cash"): 0.05,
    ("Real Estate", "Alternatives"): 0.20,
    ("Real Estate", "International"): 0.50,
    ("Crypto", "Cash"): -0.05,
    ("Crypto", "Alternatives"): 0.55,
    ("Crypto", "International"): 0.40,
    ("Cash", "Alternatives"): 0.00,
    ("Cash", "International"): 0.00,
    ("Alternatives", "International"): 0.30,
    ("Equities", "Commodities"): 0.30,
    ("Fixed Income", "Commodities"): -0.10,
    ("Gold", "Commodities"): 0.35,
    ("Real Assets", "Commodities"): 0.40,
    ("Real Estate", "Commodities"): 0.15,
    ("Crypto", "Commodities"): 0.20,
    ("Cash", "Commodities"): -0.05,
    ("Alternatives", "Commodities"): 0.25,
    ("International", "Commodities"): 0.25,
    ("Commodities", "Silver"): 0.40,
    ("Commodities", "Art"): 0.10,
    ("Commodities", "Private Equity"): 0.20,
    ("Commodities", "Venture Capital"): 0.15,
    ("Equities", "Private Equity"): 0.65,
    ("Equities", "Venture Capital"): 0.55,
    ("Fixed Income", "Private Equity"): -0.05,
    ("Fixed Income", "Venture Capital"): -0.10,
    ("Gold", "Private Equity"): 0.05,
    ("Gold", "Venture Capital"): 0.00,
    ("Real Assets", "Private Equity"): 0.15,
    ("Real Assets", "Venture Capital"): 0.10,
    ("Real Estate", "Private Equity"): 0.35,
    ("Real Estate", "Venture Capital"): 0.25,
    ("Crypto", "Private Equity"): 0.30,
    ("Crypto", "Venture Capital"): 0.40,
    ("Cash", "Private Equity"): 0.00,
    ("Cash", "Venture Capital"): 0.00,
    ("Alternatives", "Private Equity"): 0.50,
    ("Alternatives", "Venture Capital"): 0.45,
    ("International", "Private Equity"): 0.55,
    ("International", "Venture Capital"): 0.45,
    ("Private Equity", "Venture Capital"): 0.70,
}


def _get_corr(a, b):
    """Symmetric lookup in the correlation table."""
    if a == b:
        return 1.0
    return (ASSET_CLASS_CORRELATIONS.get((a, b))
            or ASSET_CLASS_CORRELATIONS.get((b, a))
            or 0.0)


BUCKET_VOL = {
    "Equities": 0.16,
    "Fixed Income": 0.05,
    "Gold": 0.15,
    "Real Assets": 0.14,
    "Real Estate": 0.12,
    "Crypto": 0.65,
    "Cash": 0.01,
    "Alternatives": 0.25,
    "International": 0.18,
    "Silver": 0.22,
    "Art": 0.10,
    "Managed Blend": 0.14,
    "Retirement Blend": 0.14,
    "Commodities": 0.22,
    "Private Equity": 0.20,
    "Venture Capital": 0.30,
}


def generate_insights(user_id, overrides=None):
    """Return a full insights payload for the user."""
    pv = compute_portfolio_value(user_id)
    total = pv["total"]
    raw_breakdown = pv.get("breakdown", {})
    breakdown, _ = rollup_breakdown(raw_breakdown, overrides)

    weights = {}
    if total > 0:
        for bucket, val in breakdown.items():
            weights[bucket] = round(val / total, 4)

    risk = _risk_score(weights)
    concentration = _concentration_analysis(
        user_id, weights, total
    )
    corr_matrix = _correlation_matrix(weights)
    diversification = _diversification_ratio(weights)
    summaries = _plain_english(
        weights, risk, concentration, diversification, total
    )

    return {
        "total": round(total, 2),
        "weights": weights,
        "risk_score": risk,
        "concentration": concentration,
        "correlation_matrix": corr_matrix,
        "diversification_ratio": diversification,
        "summaries": summaries,
    }


def _risk_score(weights):
    """Compute a 0-100 risk score from portfolio volatility.

    0 = all cash, 100 = all crypto. The score is the annualised
    portfolio volatility scaled relative to 100% equity baseline.
    """
    if not weights:
        return {"score": 0, "label": "No Data", "vol": 0}

    port_var = 0.0
    buckets = list(weights.keys())
    for i, a in enumerate(buckets):
        for j, b in enumerate(buckets):
            wa = weights[a]
            wb = weights[b]
            vol_a = BUCKET_VOL.get(a, 0.15)
            vol_b = BUCKET_VOL.get(b, 0.15)
            corr = _get_corr(a, b)
            port_var += wa * wb * vol_a * vol_b * corr

    port_vol = math.sqrt(max(port_var, 0))
    score = min(100, round(port_vol / 0.16 * 50))

    if score <= 20:
        label = "Conservative"
    elif score <= 40:
        label = "Moderate"
    elif score <= 60:
        label = "Balanced"
    elif score <= 80:
        label = "Growth"
    else:
        label = "Aggressive"

    return {
        "score": score,
        "label": label,
        "vol": round(port_vol * 100, 1),
    }


def _concentration_analysis(user_id, weights, total):
    """Analyse concentration at both bucket and individual
    holding level."""
    warnings = []

    for bucket, w in weights.items():
        pct = w * 100
        if pct >= 50:
            warnings.append({
                "type": "bucket",
                "name": bucket,
                "pct": round(pct, 1),
                "severity": "high",
                "msg": (
                    f"{bucket} makes up {pct:.0f}% of your "
                    f"portfolio — consider diversifying."
                ),
            })
        elif pct >= 35:
            warnings.append({
                "type": "bucket",
                "name": bucket,
                "pct": round(pct, 1),
                "severity": "medium",
                "msg": (
                    f"{bucket} is {pct:.0f}% — a meaningful "
                    f"concentration."
                ),
            })

    if total > 0:
        holdings = Holding.query.filter_by(
            user_id=user_id).all()
        for h in holdings:
            if not h.ticker:
                continue
            val = 0
            if h.value_override:
                val = h.value_override
            elif h.shares:
                pc = PriceCache.query.filter_by(
                    symbol=h.ticker).first()
                val = h.shares * (pc.price if pc else 0)
            pct = val / total * 100
            if pct >= 20:
                warnings.append({
                    "type": "holding",
                    "name": h.ticker,
                    "pct": round(pct, 1),
                    "severity": "high",
                    "msg": (
                        f"{h.ticker} alone is {pct:.0f}% of "
                        f"your portfolio."
                    ),
                })
            elif pct >= 10:
                warnings.append({
                    "type": "holding",
                    "name": h.ticker,
                    "pct": round(pct, 1),
                    "severity": "medium",
                    "msg": (
                        f"{h.ticker} is {pct:.0f}% — "
                        f"top-heavy position."
                    ),
                })

    hhi = sum(
        (w * 100) ** 2 for w in weights.values()
    )
    return {
        "warnings": sorted(
            warnings, key=lambda x: -x["pct"]
        ),
        "hhi": round(hhi, 0),
        "bucket_count": len(weights),
    }


_PARENT_CATEGORIES = [
    "Equities", "Fixed Income", "Real Assets",
    "Alternatives", "Commodities", "Cash",
]


def _correlation_matrix(weights):
    """Build a correlation matrix including all parent categories."""
    held = set(weights.keys())
    all_cats = list(held)
    for c in _PARENT_CATEGORIES:
        if c not in held:
            all_cats.append(c)
    buckets = sorted(all_cats)
    matrix = {}
    for a in buckets:
        row = {}
        for b in buckets:
            row[b] = _get_corr(a, b)
        matrix[a] = row
    return {"buckets": buckets, "values": matrix}


def _diversification_ratio(weights):
    """Diversification ratio = weighted avg vol / portfolio vol.

    > 1.0 means diversification benefit; higher is better.
    """
    if not weights:
        return {"ratio": 1.0, "label": "N/A"}

    weighted_vol = sum(
        w * BUCKET_VOL.get(b, 0.15)
        for b, w in weights.items()
    )

    port_var = 0.0
    buckets = list(weights.keys())
    for i, a in enumerate(buckets):
        for j, b in enumerate(buckets):
            wa = weights[a]
            wb = weights[b]
            vol_a = BUCKET_VOL.get(a, 0.15)
            vol_b = BUCKET_VOL.get(b, 0.15)
            corr = _get_corr(a, b)
            port_var += wa * wb * vol_a * vol_b * corr

    port_vol = math.sqrt(max(port_var, 0))
    if port_vol == 0:
        return {"ratio": 1.0, "label": "N/A"}

    ratio = round(weighted_vol / port_vol, 2)
    if ratio >= 1.5:
        label = "Excellent"
    elif ratio >= 1.2:
        label = "Good"
    elif ratio >= 1.05:
        label = "Moderate"
    else:
        label = "Low"

    return {"ratio": ratio, "label": label}


def _plain_english(
    weights, risk, concentration, diversification, total
):
    """Generate a list of plain-English insight strings."""
    insights = []

    if total == 0:
        return ["Add holdings to see portfolio insights."]

    score = risk["score"]
    vol = risk["vol"]
    insights.append(
        f"Your portfolio risk score is {score}/100 "
        f"({risk['label']}), with an estimated annual "
        f"volatility of {vol}%."
    )

    dr = diversification["ratio"]
    if dr >= 1.3:
        insights.append(
            f"Diversification ratio of {dr}x — your asset "
            f"mix is reducing risk meaningfully."
        )
    elif dr >= 1.1:
        insights.append(
            f"Diversification ratio of {dr}x — moderate "
            f"benefit from diversification."
        )
    else:
        insights.append(
            f"Diversification ratio of {dr}x — your "
            f"holdings move together. Consider adding "
            f"uncorrelated assets."
        )

    n_buckets = concentration["bucket_count"]
    if n_buckets <= 2:
        insights.append(
            f"You're in only {n_buckets} asset "
            f"class{'es' if n_buckets > 1 else ''}. "
            f"Broader diversification typically reduces "
            f"drawdowns."
        )
    elif n_buckets >= 5:
        insights.append(
            f"Spread across {n_buckets} asset classes — "
            f"good breadth."
        )

    top_warnings = concentration["warnings"][:2]
    for w in top_warnings:
        insights.append(w["msg"])

    eq_pct = weights.get("Equities", 0) * 100
    fi_pct = weights.get("Fixed Income", 0) * 100
    if eq_pct > 0 and fi_pct > 0:
        corr = _get_corr("Equities", "Fixed Income")
        corr_word = (
            "negatively" if corr < 0 else "weakly"
        )
        insights.append(
            f"Your stocks ({eq_pct:.0f}%) and bonds "
            f"({fi_pct:.0f}%) are {corr_word} correlated "
            f"({corr:+.2f}), which helps cushion drawdowns."
        )

    crypto_pct = weights.get("Crypto", 0) * 100
    if crypto_pct >= 10:
        insights.append(
            f"Crypto is {crypto_pct:.0f}% of your "
            f"portfolio — high volatility (~65% annual) "
            f"can swing total returns significantly."
        )

    gold_pct = (weights.get("Gold", 0)
                + weights.get("Real Assets", 0)) * 100
    if gold_pct >= 10:
        insights.append(
            f"Real assets/gold at {gold_pct:.0f}% gives "
            f"inflation hedging and low equity correlation."
        )

    return insights
