"""Bucket name normalization and standard bucket list."""

STANDARD_BUCKETS = [
    "Art", "Cash", "Crypto", "Equities", "Fixed Income", "Gold",
    "International", "Managed Blend", "Real Assets", "Real Estate",
    "Retirement Blend", "Silver",
]

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
