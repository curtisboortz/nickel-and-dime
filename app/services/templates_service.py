"""Pre-built allocation templates for portfolio comparison.

Each template is a dict with id, name, description, source attribution,
and an allocations dict mapping bucket names to target percentages.
"""

TEMPLATES = [
    {
        "id": "all-weather",
        "name": "All Weather",
        "author": "Ray Dalio / Bridgewater",
        "description": (
            "Designed to perform well across all economic environments "
            "(growth, recession, inflation, deflation). "
            "Classic allocation from Dalio's 2014 Tony Robbins interview; "
            "his current views may differ."
        ),
        "allocations": {
            "Equities": 30,
            "Fixed Income": 55,
            "Gold": 7.5,
            "Real Assets": 7.5,
        },
    },
    {
        "id": "60-40",
        "name": "Classic 60/40",
        "author": "Traditional",
        "description": (
            "The foundational balanced portfolio: 60% stocks for "
            "growth, 40% bonds for stability."
        ),
        "allocations": {
            "Equities": 60,
            "Fixed Income": 40,
        },
    },
    {
        "id": "permanent",
        "name": "Permanent Portfolio",
        "author": "Harry Browne",
        "description": (
            "Equal allocation across four pillars that each thrive "
            "in different economic conditions."
        ),
        "allocations": {
            "Equities": 25,
            "Fixed Income": 25,
            "Gold": 25,
            "Cash": 25,
        },
    },
    {
        "id": "golden-butterfly",
        "name": "Golden Butterfly",
        "author": "Tyler (Portfolio Charts)",
        "description": (
            "A Permanent Portfolio variant that tilts toward "
            "small-cap value and overweights gold."
        ),
        "allocations": {
            "Equities": 40,
            "Fixed Income": 20,
            "Gold": 20,
            "Cash": 20,
        },
    },
    {
        "id": "boglehead-3",
        "name": "Boglehead Three-Fund",
        "author": "Jack Bogle / Vanguard",
        "description": (
            "Simple, low-cost diversification: US stocks, "
            "international stocks, and US bonds."
        ),
        "allocations": {
            "Equities": 50,
            "International": 30,
            "Fixed Income": 20,
        },
    },
    {
        "id": "macro-investor",
        "name": "Macro Investor",
        "author": "Nickel&Dime",
        "description": (
            "For macro-minded investors who want meaningful "
            "commodity and alternatives exposure."
        ),
        "allocations": {
            "Equities": 35,
            "Fixed Income": 20,
            "Real Assets": 15,
            "Gold": 10,
            "Crypto": 10,
            "Cash": 10,
        },
    },
    {
        "id": "income-focus",
        "name": "Income Focus",
        "author": "Traditional",
        "description": (
            "Prioritises yield through bonds, REITs, and "
            "dividend stocks for steady cash flow."
        ),
        "allocations": {
            "Equities": 30,
            "Fixed Income": 40,
            "Real Estate": 15,
            "Cash": 15,
        },
    },
]

TEMPLATE_MAP = {t["id"]: t for t in TEMPLATES}


def list_templates():
    """Return all available templates (sans allocations for the list)."""
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "author": t["author"],
            "description": t["description"],
        }
        for t in TEMPLATES
    ]


def get_template(template_id):
    """Return a single template by id, or None."""
    return TEMPLATE_MAP.get(template_id)


def compare_portfolio(template_id, breakdown, total, children=None):
    """Compare user's rolled-up allocation against a template.

    *children* is the child-detail dict from ``rollup_breakdown``
    (parent -> {child: dollar_value}).  When a template references a
    child category (e.g. Gold, International) we pull the child value
    out and subtract it from the parent so nothing is double-counted.

    Returns per-bucket rows with user_pct, template_pct, and delta,
    plus an overall similarity score (0-100).
    """
    from ..utils.buckets import BUCKET_PARENTS

    tpl = TEMPLATE_MAP.get(template_id)
    if not tpl:
        return None

    children = children or {}
    allocs = tpl["allocations"]

    effective = dict(breakdown)
    for bucket in allocs:
        parent = BUCKET_PARENTS.get(bucket)
        if not parent:
            continue
        child_val = children.get(parent, {}).get(bucket, 0)
        if child_val:
            effective[bucket] = effective.get(bucket, 0) + child_val
            effective[parent] = effective.get(parent, 0) - child_val

    all_buckets = sorted(
        set(list(effective.keys()) + list(allocs.keys()))
    )

    rows = []
    sum_abs_delta = 0.0
    for bucket in all_buckets:
        user_val = effective.get(bucket, 0)
        user_pct = round(user_val / total * 100, 1) if total > 0 else 0
        tpl_pct = allocs.get(bucket, 0)
        if user_pct == 0 and tpl_pct == 0:
            continue
        delta = round(user_pct - tpl_pct, 1)
        sum_abs_delta += abs(delta)
        rows.append({
            "bucket": bucket,
            "user_pct": user_pct,
            "template_pct": tpl_pct,
            "delta": delta,
        })

    similarity = max(0, round(100 - sum_abs_delta / 2, 1))

    return {
        "template": {
            "id": tpl["id"],
            "name": tpl["name"],
            "author": tpl["author"],
            "description": tpl["description"],
        },
        "rows": rows,
        "similarity": similarity,
    }
