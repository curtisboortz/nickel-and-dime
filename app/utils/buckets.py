"""Bucket name normalization and standard bucket list."""

STANDARD_BUCKETS = [
    "Art", "Cash", "Crypto", "Equities", "Fixed Income", "Gold",
    "International", "Managed Blend", "Real Assets", "Real Estate",
    "Retirement Blend", "Silver",
]

BUCKET_PARENTS = {
    "Managed Blend": "Equities",
    "Retirement Blend": "Equities",
    "International": "Equities",
    "Real Estate": "Real Assets",
    "Art": "Real Assets",
    "Gold": "Commodities",
    "Silver": "Commodities",
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


def rollup_breakdown(breakdown):
    """Roll sub-categories into parent categories.

    Returns (rolled_up_dict, children_dict) where children_dict maps
    parent -> {child: value, ...} for categories that were merged.
    """
    rolled = {}
    children = {}
    for bucket, value in breakdown.items():
        normed = normalize_bucket(bucket)
        parent = BUCKET_PARENTS.get(normed)
        if parent:
            rolled[parent] = rolled.get(parent, 0) + value
            children.setdefault(parent, {})[normed] = \
                children.get(parent, {}).get(normed, 0) + value
        else:
            rolled[normed] = rolled.get(normed, 0) + value
    return rolled, children
