"""Bucket name normalization and standard bucket list."""

STANDARD_BUCKETS = [
    "Alternatives", "Art", "Cash", "Crypto", "Equities", "Fixed Income",
    "Gold", "International", "Managed Blend", "Real Assets", "Real Estate",
    "Retirement Blend", "Silver",
]

BUCKET_PARENTS = {
    "Managed Blend": "Equities",
    "Retirement Blend": "Equities",
    "International": "Equities",
    "Real Estate": "Real Assets",
    "Art": "Real Assets",
    "Gold": "Real Assets",
    "Silver": "Real Assets",
    "Crypto": "Alternatives",
}

_BUCKET_ALIASES = {
    "realassets": "Real Assets",
    "real assets": "Real Assets",
    "fixedincome": "Fixed Income",
    "fixed income": "Fixed Income",
    "managedblend": "Managed Blend",
    "managed blend": "Managed Blend",
    "retirementblend": "Retirement Blend",
    "retirement blend": "Retirement Blend",
    "realestate": "Real Estate",
    "real estate": "Real Estate",
    "alternatives": "Alternatives",
    "commodities": "Real Assets",
}


def normalize_bucket(name):
    """Normalize a bucket name to its canonical form."""
    if not name:
        return name
    key = name.lower().strip()
    if key in _BUCKET_ALIASES:
        return _BUCKET_ALIASES[key]
    for sb in STANDARD_BUCKETS:
        if key == sb.lower():
            return sb
    return name


def rollup_breakdown(breakdown, overrides=None):
    """Roll sub-categories into parent categories.

    *overrides* is an optional dict of ``{child: parent_or_None}`` that takes
    precedence over the default ``BUCKET_PARENTS``.  A value of ``None``
    means "standalone" (remove the default parent mapping).

    Returns (rolled_up_dict, children_dict) where children_dict maps
    parent -> {child: value, ...} for categories that were merged.
    """
    effective = dict(BUCKET_PARENTS)
    if overrides:
        for child, parent in overrides.items():
            normed_child = normalize_bucket(child)
            if parent is None:
                effective.pop(normed_child, None)
            else:
                effective[normed_child] = parent

    rolled = {}
    children = {}
    for bucket, value in breakdown.items():
        normed = normalize_bucket(bucket)
        parent = effective.get(normed)
        if parent:
            rolled[parent] = rolled.get(parent, 0) + value
            children.setdefault(parent, {})[normed] = \
                children.get(parent, {}).get(normed, 0) + value
        else:
            rolled[normed] = rolled.get(normed, 0) + value
    return rolled, children
