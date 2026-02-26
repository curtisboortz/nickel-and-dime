"""
CSV import for Fidelity, Stash, Acorns, Fundrise, and bank/credit card statements.
Updates config.json with positions/values from exported CSVs.
"""

import csv
import json
import re
from pathlib import Path
from typing import List, Optional


def _normalize_header(s: str) -> str:
    return s.strip().lower().replace(" ", "_").replace("-", "_")


def _find_column(row: list, *candidates: str) -> Optional[int]:
    """Return index of first column whose normalized name matches any candidate (exact preferred)."""
    exact_matches = []
    for i, cell in enumerate(row):
        n = _normalize_header(str(cell))
        for c in candidates:
            if n == c:
                return i  # exact match wins
            if c in n or n in c:
                exact_matches.append(i)
                break
    return exact_matches[0] if exact_matches else None


def _safe_float(s: str) -> float:
    if s is None or (isinstance(s, str) and not s.strip()):
        return 0.0
    s = str(s).strip().replace(",", "").replace("$", "").replace("(", "-").replace(")", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _normalize_symbol(s: str) -> str:
    """Strip Fidelity suffixes like ** from symbol for matching."""
    s = (s or "").strip().rstrip("*")
    return s.upper() if s else ""


def _asset_class_for_ticker(ticker: str) -> str:
    """Map ticker to asset class (Cash, Gold, Silver, Equities)."""
    t = (ticker or "").upper().rstrip("*")
    if t in ("SPAXX",):
        return "Cash"
    if t in ("GLD", "GLDM", "IAU"):
        return "Gold"
    if t in ("SLV", "PSLV"):
        return "Silver"
    return "Equities"


def parse_fidelity_csv(path: Path, account_name_filter: Optional[str] = "Individual") -> List[dict]:
    """
    Parse Fidelity Positions CSV.
    Returns one row per position/lot (no aggregation). Preserves Margin vs Cash lots as separate rows.
    If account_name_filter is set (default "Individual"), only includes rows where Account Name matches.
    Use account_name_filter=None to import all accounts.
    """
    rows = []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return []
        idx_symbol = _find_column(header, "symbol", "ticker")
        idx_qty = _find_column(header, "quantity", "qty", "shares")
        idx_price = _find_column(header, "last_price", "price", "close")
        idx_value = _find_column(header, "current_value", "value", "market_value")
        idx_desc = _find_column(header, "description", "security")
        idx_type = _find_column(header, "type")  # Fidelity: Cash, Margin
        idx_account_name = _find_column(header, "account_name", "account")
        if idx_symbol is None and idx_value is None:
            return []
        for row in reader:
            indices = [i for i in [idx_symbol, idx_qty, idx_price, idx_value, idx_desc] if i is not None]
            if not indices or len(row) <= max(indices):
                continue
            # Filter by Account Name (e.g. only "Individual" - skip Stash/Portfolio linked accounts)
            if account_name_filter and idx_account_name is not None and idx_account_name < len(row):
                acct = (row[idx_account_name] or "").strip()
                if _normalize_header(acct) != _normalize_header(account_name_filter):
                    continue
            symbol = (row[idx_symbol].strip() if idx_symbol is not None and idx_symbol < len(row) else "") or None
            if not symbol or symbol.upper() in ("CASH", "MARGIN", "TOTAL", "ACCOUNT"):
                continue
            if _normalize_symbol(symbol) == "" or symbol == "**":
                continue
            # Skip non-ticker rows (Fidelity includes these in exports)
            sym_lower = symbol.lower().strip()
            if sym_lower in ("pending activity", "pending", "total", "account total"):
                continue
            qty = _safe_float(row[idx_qty]) if idx_qty is not None else None
            price = _safe_float(row[idx_price]) if idx_price is not None else None
            value = _safe_float(row[idx_value]) if idx_value is not None else (float(qty) * float(price) if qty and price else 0)
            desc = row[idx_desc].strip() if idx_desc is not None and idx_desc < len(row) else ""
            lot_type = row[idx_type].strip() if idx_type is not None and idx_type < len(row) and row[idx_type].strip() else ""
            if lot_type:
                desc = f"{desc} | {lot_type}" if desc else lot_type
            base_sym = symbol.strip().rstrip("*") or symbol
            rows.append({
                "symbol": base_sym,
                "qty": qty if qty else None,
                "price": price,
                "value": value,
                "description": desc,
            })
    return rows


def parse_blended_csv(path: Path, source: str) -> List[dict]:
    """
    Parse Stash / Acorns / Fundrise-style CSV (holdings or single total).
    Accepts: Symbol, Quantity, Value (or Balance, Current Value); or one row with Total/Value.
    Returns list of {"symbol": str, "qty": float, "value": float} or [{"value": total}].
    """
    rows = []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return rows
        idx_symbol = _find_column(header, "symbol", "ticker", "security", "name")
        idx_qty = _find_column(header, "quantity", "qty", "shares")
        idx_value = _find_column(header, "value", "balance", "current_value", "market_value", "amount")
        for row in reader:
            if not row:
                continue
            value = _safe_float(row[idx_value]) if idx_value is not None else 0
            if idx_value is None and len(row) >= 1:
                value = _safe_float(row[-1])
            symbol = (row[idx_symbol].strip() if idx_symbol is not None and idx_symbol < len(row) else "") or source
            qty = _safe_float(row[idx_qty]) if idx_qty is not None else None
            rows.append({"symbol": symbol, "qty": qty, "value": value})
    return rows


def apply_fidelity_import(config: dict, rows: list[dict]) -> int:
    """
    Replace Fidelity holdings with CSV rows. Each lot (Margin/Cash) stays a separate row.
    Keeps non-Fidelity holdings (if any) unchanged.
    """
    existing = config.get("holdings", [])
    non_fidelity = [h for h in existing if (h.get("account") or "").strip() != "Fidelity"]
    new_holdings = []
    for r in rows:
        if not r.get("symbol") and not r.get("value"):
            continue
        new_holdings.append({
            "account": "Fidelity",
            "ticker": r["symbol"],
            "asset_class": _asset_class_for_ticker(r["symbol"]),
            "qty": r.get("qty"),
            "value_override": round(r["value"], 2) if r.get("value") else None,
            "notes": r.get("description", ""),
        })
    config["holdings"] = non_fidelity + new_holdings
    return len(new_holdings)


def apply_blended_import(config: dict, rows: list[dict], source: str) -> int:
    """
    Update config['blended_accounts'] with total from CSV.
    source: 'stash' | 'acorns' | 'fundrise'
    """
    total = sum(r.get("value", 0) for r in rows)
    if total <= 0:
        return 0
    name_map = {
        "stash": ["Stash Total"],
        "acorns": ["Acorns Invest"],  # one CSV = Invest total; use acorns_later for Later
        "acorns_invest": ["Acorns Invest"],
        "acorns_later": ["Acorns Later"],
        "fundrise": ["Fundrise"],
    }
    names = name_map.get(source)
    if not names:
        return 0
    updated = 0
    for b in config.get("blended_accounts", []):
        if b.get("name") in names:
            b["value"] = round(total, 2)
            updated += 1
            break
    if updated == 0 and names:
        config.setdefault("blended_accounts", []).append({
            "name": names[0],
            "value": round(total, 2),
            "asset_class": "ManagedBlend" if source in ("stash", "acorns", "acorns_invest", "acorns_later") else "RealEstate",
        })
        updated = 1
    return updated


def import_csv(config_path: Path, csv_path: Path, source: str) -> tuple[int, str]:
    """
    Load config, parse CSV by source, update config, save.
    source: 'fidelity' | 'stash' | 'acorns' | 'fundrise'
    Returns (rows_updated, message).
    """
    source = source.lower().strip()
    if source not in ("fidelity", "stash", "acorns", "acorns_invest", "acorns_later", "fundrise"):
        return 0, f"Unknown source: {source}. Use fidelity, stash, acorns, acorns_invest, acorns_later, or fundrise."

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Preserve crypto_holdings — CSV import only updates holdings/blended_accounts
    crypto_holdings = config.get("crypto_holdings", [])

    if source == "fidelity":
        rows = parse_fidelity_csv(csv_path)
        if not rows:
            return 0, "No Fidelity positions found in CSV. Check column headers (Symbol, Quantity, Current Value)."
        updated = apply_fidelity_import(config, rows)
    else:
        rows = parse_blended_csv(csv_path, source)
        if not rows:
            return 0, f"No rows with values found. Expected columns: Symbol/Name, Value (or Balance)."
        updated = apply_blended_import(config, rows, source)

    config["crypto_holdings"] = crypto_holdings
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    return updated, f"Updated {updated} position(s) from {source} CSV. Run the dashboard update to refresh."


# ── Bank/Credit Card Statement Import ──

# Default keyword-to-category mapping for auto-categorization.
# IMPORTANT: Categories here should match the user's budget categories.
# The function also supports a fallback mapping for categories that
# don't exist in the budget (see categorize_transaction).
DEFAULT_CATEGORY_RULES = {
    "Housing": [
        "rent", "mortgage", "hoa", "homeowner", "property tax", "landlord",
        "apartment", "lease", "housing", "regents la jolla",
    ],
    "Utilities": [
        "electric", "gas bill", "water bill", "sewer", "internet", "wifi",
        "comcast", "xfinity", "verizon", "t-mobile", "tmobile", "at&t",
        "att", "spectrum", "cox", "utility", "phone bill", "cellphone",
        "sprint", "cricket", "mint mobile",
        # Subscriptions & SaaS (mapped to Utilities since no Subscriptions budget category)
        "openai", "chatgpt", "cursor,", "cursor ", "cursor usage",
        "microsoft", "apple.com/bill", "apple.com/one",
        "linkedin", "cloudflare", "adobe", "dropbox", "notion", "figma",
        "canva", "grammarly", "1password", "nordvpn", "expressvpn",
        "google one", "google storage", "icloud",
        # Streaming (also utility-like subscriptions)
        "netflix", "hulu", "disney+", "disney plus", "hbo", "spotify",
        "apple music", "youtube premium", "amazon prime", "paramount",
        "peacock", "crunchyroll", "audible",
    ],
    "Food": [
        "grocery", "groceries", "walmart", "target", "costco", "kroger",
        "aldi", "trader joe", "whole foods", "safeway", "publix", "heb",
        "food lion", "wegmans", "shoprite", "meijer", "sam's club",
        "restaurant", "mcdonald", "starbucks", "chipotle", "chick-fil-a",
        "subway", "wendy", "taco bell", "pizza", "doordash", "uber eats",
        "ubereats", "grubhub", "postmates", "instacart", "seamless",
        "dining", "cafe", "coffee", "diner", "burger", "sushi",
        "panera", "domino", "papa john", "five guys", "popeyes",
        "chili", "applebee", "olive garden", "ihop", "waffle house",
        "dunkin", "panda express", "wingstop", "cookout",
        "nazomi", "bento", "ruth's chris", "mongolian bbq", "pita house",
        "queenstown", "rubicon deli", "snooze", "akhis", "rum jungle",
        "ike's", "micheline", "bakery", "deli", "smoothie", "juice",
    ],
    "Transportation": [
        "gas station", "shell oil", "exxon", "chevron", "bp ", "marathon",
        "sunoco", "circle k", "wawa", "speedway", "racetrac", "quiktrip",
        "fuel", "gasoline", "uber trip", "lyft", "taxi", "parking",
        "toll", "ezpass", "transit", "metro", "bus fare", "train",
        "car wash", "autozone", "jiffy lube", "oil change", "tire",
        "car payment", "auto loan",
    ],
    "Entertainment": [
        "movie", "cinema", "theater", "amc ", "regal", "concert",
        "ticket", "ticketmaster", "stubhub", "gaming", "steam",
        "playstation", "xbox", "nintendo", "bar ", "nightclub",
        "bowling", "golf", "gym", "fitness", "planet fitness", "equinox",
        "excel fitness", "feverup", "kindle",
        # Shopping (mapped here — clothes, personal items, online orders)
        "amazon", "amzn", "tjmaxx", "tj maxx", "marshalls", "ross",
        "nordstrom", "macys", "zara", "h&m", "old navy", "gap ",
        "nike", "adidas", "flaunt", "savage", "fenty", "clearstem",
        "skincar", "sephora", "ulta", "bath & body", "victoria",
        "etsy", "ebay", "wish.com", "shein",
    ],
    "Health": [
        "pharmacy", "cvs", "walgreens", "rite aid", "doctor", "medical",
        "hospital", "clinic", "dental", "dentist", "vision", "optometrist",
        "health insurance", "copay", "prescription", "lab", "urgent care",
        "therapy", "mental health", "dermatolog",
        # Insurance premiums (health-adjacent)
        "healthnet", "eqt*healthnet", "msi insurance", "insurance",
        "geico", "progressive", "state farm", "allstate",
    ],
    # Debt & loan payments don't have a budget category → they'll go to "Other"
    # but are defined here so we can potentially add a Debt budget category later
    "Other": [
        "student loan", "dept education", "student ln",
        "mission federal", "capital one",
    ],
    "Savings/Investments": [
        "transfer to savings", "investment", "fidelity", "vanguard",
        "schwab", "robinhood", "coinbase inc", "acorns", "stash capital",
        "fundrise", "wealthfront", "betterment", "401k", "ira ", "brokerage",
    ],
}


def categorize_transaction(description: str, custom_rules: dict = None, budget_categories: list = None) -> str:
    """Auto-categorize a transaction description into a budget category.
    
    If budget_categories is provided, ensures the returned category exists
    in the user's budget. Unknown categories are mapped to 'Other'.
    """
    rules = custom_rules or DEFAULT_CATEGORY_RULES
    desc_lower = (description or "").lower()
    for category, keywords in rules.items():
        for kw in keywords:
            if kw in desc_lower:
                # If we have budget categories, verify this category exists
                if budget_categories and category not in budget_categories:
                    # Try to find closest match
                    return "Other"
                return category
    return "Other"


def parse_statement_csv(path: Path) -> List[dict]:
    """
    Parse a bank or credit card statement CSV. Auto-detects column layout.
    Supports common formats from Chase, Bank of America, Wells Fargo, Capital One,
    Citi, Discover, USAA, and generic bank exports.

    Returns list of {"date": str, "description": str, "amount": float, "category": str}
    Positive amounts = expenses (debits). Negative amounts are ignored (credits/payments).
    """
    transactions = []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        # Skip BOM and blank lines at top
        content = f.read().lstrip("\ufeff").strip()
        if not content:
            return []

    # Try to find header row (some banks put metadata lines before the header)
    lines = content.split("\n")
    header_idx = 0
    for i, line in enumerate(lines[:10]):
        lower = line.lower()
        if "date" in lower and ("description" in lower or "memo" in lower or "payee" in lower or "merchant" in lower or "amount" in lower):
            header_idx = i
            break

    csv_text = "\n".join(lines[header_idx:])
    reader = csv.reader(csv_text.strip().split("\n"))
    header = next(reader, None)
    if not header:
        return []

    # Detect columns
    idx_date = _find_column(header, "date", "transaction_date", "posting_date", "trans_date")
    idx_desc = _find_column(header, "description", "memo", "payee", "merchant", "name", "merchant_name", "original_description")
    idx_amount = _find_column(header, "amount", "transaction_amount")
    idx_debit = _find_column(header, "debit", "withdrawals", "charges")
    idx_credit = _find_column(header, "credit", "deposits", "payments")
    idx_category = _find_column(header, "category", "type")

    if idx_date is None:
        return []
    if idx_desc is None:
        # Try using the column next to date
        idx_desc = min(idx_date + 1, len(header) - 1)

    for row in reader:
        if not row or len(row) <= idx_date:
            continue

        date_str = (row[idx_date] or "").strip()
        if not date_str or not any(c.isdigit() for c in date_str):
            continue

        # Normalize date format
        date_str = _normalize_date(date_str)
        if not date_str:
            continue

        desc = (row[idx_desc] if idx_desc is not None and idx_desc < len(row) else "").strip()
        if not desc:
            continue

        # Determine amount and whether it's a debit or credit
        amount = 0.0
        is_credit = False
        if idx_amount is not None and idx_amount < len(row):
            amount = _safe_float(row[idx_amount])
            if amount < 0:
                is_credit = True
                amount = abs(amount)
        elif idx_debit is not None and idx_debit < len(row):
            amount = _safe_float(row[idx_debit])

        # Check credit column for deposits/income
        if amount == 0 and idx_credit is not None and idx_credit < len(row):
            credit = _safe_float(row[idx_credit])
            if credit > 0:
                amount = credit
                is_credit = True

        if amount == 0:
            continue

        # Skip non-transaction entries
        desc_lower = desc.lower()
        skip_keywords = ["payment thank you", "autopay", "online payment",
                         "cashback", "rewards redemption", "balance transfer"]
        if any(kw in desc_lower for kw in skip_keywords):
            continue

        # Determine transaction type
        income_keywords = [
            "direct deposit", "payroll", "salary", "wages",
            "deposit", "refund", "credit adjustment", "merchant credit",
            "interest earned", "dividend", "tax refund", "reimbursement",
        ]
        if is_credit or any(kw in desc_lower for kw in income_keywords):
            txn_type = "income"
            txn_amount = -round(amount, 2)
            category = "Income"
        else:
            txn_type = "expense"
            txn_amount = round(amount, 2)
            category = categorize_transaction(desc)

        # Use bank-provided category if available (for expenses only)
        bank_cat = ""
        if idx_category is not None and idx_category < len(row):
            bank_cat = (row[idx_category] or "").strip()

        transactions.append({
            "date": date_str,
            "description": desc,
            "amount": txn_amount,
            "category": category,
            "type": txn_type,
            "bank_category": bank_cat,
        })

    return transactions


def _extract_pdf_text(path: Path) -> str:
    """Extract text from PDF. Tries pdfplumber first, falls back to PyPDF2/pypdf."""
    # Try pdfplumber
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        if text_parts:
            return "\n".join(text_parts)
    except ImportError:
        pass
    except Exception:
        pass

    # Try pypdf / PyPDF2
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        text_parts = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
        if text_parts:
            return "\n".join(text_parts)
    except ImportError:
        pass
    except Exception:
        pass

    return ""


def _normalize_date_text(date_str: str, default_year: int = None) -> str:
    """Normalize date strings from statement text. Handles:
    - MM/DD/YYYY, MM/DD/YY
    - Jan 15, 2026 / Jan 15 2026
    - 01/15/2026
    """
    import calendar
    s = date_str.strip().rstrip(",")

    # Already normalized
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s

    # MM/DD/YYYY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"

    # MM/DD/YY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2})$", s)
    if m:
        year = int(m.group(3))
        year = year + 2000 if year < 50 else year + 1900
        return f"{year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"

    # "Jan 15, 2026" or "Jan 15 2026" or "January 15, 2026"
    month_names = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
    month_abbrs = {name.lower(): i for i, name in enumerate(calendar.month_abbr) if name}
    all_months = {**month_names, **month_abbrs}
    m = re.match(r"^([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})?$", s)
    if m:
        month_str = m.group(1).lower()
        day = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else default_year or 2026
        month_num = all_months.get(month_str)
        if month_num:
            return f"{year}-{month_num:02d}-{day:02d}"

    return _normalize_date(s)


def parse_statement_pdf(path: Path) -> List[dict]:
    """
    Parse a bank or credit card statement PDF using text extraction.
    Supports: Apple Card, Golden 1 Credit Union, Coinbase Card, and generic formats.
    Returns list of {"date": str, "description": str, "amount": float, "category": str}
    """
    text = _extract_pdf_text(path)
    if not text:
        return []

    # Detect statement type and delegate
    text_lower = text.lower()
    if "apple card" in text_lower or "daily cash" in text_lower:
        return _parse_apple_card_pdf(text)
    elif "coinbase" in text_lower and ("coinbase one card" in text_lower or "cardless" in text_lower):
        return _parse_coinbase_card_pdf(text)
    elif "golden 1" in text_lower or "golden1" in text_lower:
        return _parse_golden1_pdf(text)
    else:
        return _parse_generic_pdf(text)


def _parse_apple_card_pdf(text: str) -> List[dict]:
    """Parse Apple Card statement PDF text.
    Format: MM/DD/YYYY DESCRIPTION LOCATION 1% $X.XX $XX.XX
    The last dollar amount on the line is the transaction amount.
    """
    transactions = []
    skip_keywords = ["ach deposit", "payment", "autopay", "refund", "credit adjustment"]

    # Apple Card transaction pattern: date, description, daily cash %, daily cash $, amount $
    # e.g. "01/01/2026 OPENAI *CHATGPT SUBSCR1455 3rd Street SAN FRANCISCO94158 CA USA 1% $0.20 $20.00"
    pattern = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+\d+%\s+\$[\d,.]+\s+\$([\d,.]+)$")

    for line in text.split("\n"):
        line = line.strip()
        m = pattern.match(line)
        if not m:
            continue

        date_str = _normalize_date_text(m.group(1))
        if not date_str:
            continue

        desc = m.group(2).strip()
        amount = _safe_float(m.group(3))
        if amount <= 0:
            continue

        # Clean up description: remove address/location cruft
        # Truncate at common location patterns
        desc_clean = re.sub(r'\s+\d{4,5}\s+[A-Z]{2}\s+USA$', '', desc)
        desc_clean = re.sub(r'\s+\d+\s+\w+.*$', '', desc_clean) if len(desc_clean) > 60 else desc_clean
        # Keep first ~60 chars for readability
        if len(desc_clean) > 60:
            desc_clean = desc_clean[:60].strip()

        desc_lower = desc.lower()
        if any(kw in desc_lower for kw in skip_keywords):
            continue

        transactions.append({
            "date": date_str,
            "description": desc_clean,
            "amount": round(amount, 2),
            "category": categorize_transaction(desc),
            "bank_category": "",
        })

    return transactions


def _parse_coinbase_card_pdf(text: str) -> List[dict]:
    """Parse Coinbase One Card statement PDF text.
    pdfplumber format: "Dec 22, 2025 MERCHANT NAME $XX.XX" on one line,
    with possible description continuation on next line.
    """
    transactions = []
    skip_keywords = ["ach payment", "autopay", "refund", "credit adjustment"]

    lines = text.split("\n")
    # Find the "Transactions" section
    in_transactions = False

    # Pattern: "Dec 22, 2025  DESCRIPTION  $XX.XX" or "-$XX.XX"
    date_pattern = re.compile(
        r"^((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s*\d{4})\s+(.+?)\s+(-?\$[\d,]+\.\d{2})$"
    )
    # Also try: date + description (no amount — amount may be on prev desc or next line)
    date_only_pattern = re.compile(
        r"^((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s*\d{4})\s+(.+)$"
    )

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Detect section boundaries
        if "Transactions" in line and "Date" not in line:
            in_transactions = True
            i += 1
            continue
        if line.startswith("Total") and ("period" in line.lower() or "charges" in line.lower()):
            in_transactions = False
            i += 1
            continue
        if "Payments and credits" in line:
            in_transactions = False
            i += 1
            continue
        if line.startswith("Fees") or line.startswith("Interest"):
            in_transactions = False
            i += 1
            continue

        if not in_transactions:
            i += 1
            continue

        # Skip headers and footers
        if any(s in line.lower() for s in ["page ", "coinbase one card", "curtis", "crb1898", "date description"]):
            i += 1
            continue

        # Try full pattern: date + description + amount on one line
        m = date_pattern.match(line)
        if m:
            date_str = _normalize_date_text(m.group(1))
            desc = m.group(2).strip()
            amount_str = m.group(3).replace("$", "").replace(",", "")
            amount = abs(float(amount_str))

            # Check for description continuation on next line
            j = i + 1
            while j < len(lines) and j < i + 3:
                next_line = lines[j].strip()
                if not next_line or date_only_pattern.match(next_line) or date_pattern.match(next_line):
                    break
                if any(s in next_line.lower() for s in ["page ", "coinbase", "curtis", "crb1898", "total"]):
                    j += 1
                    continue
                # It's continuation text
                desc += " " + next_line
                j += 1

            if date_str and amount > 0:
                desc_clean = re.sub(r'\s+\d{5}\s+\d{3}\s+\d{3}$', '', desc)
                desc_clean = re.sub(r'\s{2,}', ' ', desc_clean).strip()
                if len(desc_clean) > 60:
                    desc_clean = desc_clean[:60].strip()

                desc_lower = desc.lower()
                if not any(kw in desc_lower for kw in skip_keywords):
                    transactions.append({
                        "date": date_str,
                        "description": desc_clean,
                        "amount": round(amount, 2),
                        "category": categorize_transaction(desc),
                        "bank_category": "",
                    })
            i = j
            continue

        i += 1

    return transactions


def _parse_golden1_pdf(text: str) -> List[dict]:
    """Parse Golden 1 Credit Union bank statement PDF text.
    Format: tab-separated lines with Post Date, Description, Withdrawals ($), Deposits ($), Balance ($)
    Multi-line descriptions: date on first line, continuation on next lines, amount on a line.
    
    Captures BOTH withdrawals (expenses) and deposits (income/credits) for accurate cash flow.
    Deposits are returned with negative amounts so the budget can show net cash flow.
    """
    transactions = []
    # Skip non-transaction lines and credit card payments (those appear on the CC statement).
    skip_keywords = [
        # Not actual transactions
        "beginning balance", "ending balance", "account summary",
        # Credit card payments — actual spending is on the CC statement
        "applecard", "apple card", "gsbank", "coinbase card",
        "crcardpmt", "credit card",
    ]
    # Keywords that indicate incoming money (deposits) — these get negative amounts
    income_keywords = [
        "direct deposit", "payroll", "salary", "wages",
        "checking deposit", "mobile deposit", "atm deposit", "cash deposit",
        "ach deposit", "ach credit", "ach p2p credit",
        "zelle dep", "zelle credit", "zelle from", "zelle money received",
        "venmo cashout", "venmo credit",
        "interest earned", "interest paid", "dividend",
        "refund", "credit adjustment", "merchant credit",
        "from ach", "nowrtp", "moneyline", "ach p2p",
        "tax refund", "reimbursement",
    ]

    lines = text.split("\n")
    date_pattern = re.compile(r"^(\d{2}/\d{2}/\d{4})")

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        dm = date_pattern.match(line)
        if not dm:
            i += 1
            continue

        date_str = _normalize_date_text(dm.group(1))
        if not date_str:
            i += 1
            continue

        # Rest of line after date(s)
        rest = line[dm.end():].strip()
        # Sometimes there's a second date (effective date)
        dm2 = re.match(r"^(\d{2}/\d{2}/\d{4})\s*", rest)
        if dm2:
            rest = rest[dm2.end():].strip()

        # Collect description parts and find the withdrawal amount
        desc_parts = [rest] if rest else []
        amount = 0.0
        j = i + 1

        # Look for amount pattern: -X,XXX.XX (withdrawal) or just the amount on continuation lines
        # Check current line for amounts first
        amounts_on_line = re.findall(r"-?([\d,]+\.\d{2})", rest)
        
        # Scan continuation lines
        while j < len(lines):
            next_line = lines[j].strip()
            # New date = new transaction
            if date_pattern.match(next_line):
                break
            # Skip section headers
            if any(skip in next_line.lower() for skip in ["account activity", "account number", "account summary", "page "]):
                j += 1
                continue
            # Check for amount
            amt_matches = re.findall(r"-?([\d,]+\.\d{2})", next_line)
            if amt_matches:
                amounts_on_line.extend(amt_matches)
                # Don't add pure-number lines to description
                text_part = re.sub(r'-?[\d,]+\.\d{2}', '', next_line).strip()
                if text_part and len(text_part) > 3:
                    desc_parts.append(text_part)
            elif next_line and not next_line.startswith("Total"):
                desc_parts.append(next_line)
            j += 1
            if j - i > 6:
                break

        desc = " ".join(desc_parts).strip()
        desc = re.sub(r'\s{2,}', ' ', desc)

        # The withdrawal amount is typically the first negative-looking amount
        # or the first amount in the withdrawals column
        if amounts_on_line:
            # For bank statements, take the first amount as the transaction amount
            amount = _safe_float(amounts_on_line[0])

        if not desc or amount == 0:
            i = j
            continue

        # Clean up description
        desc_clean = re.sub(r'\s*\([^)]*\)\s*$', '', desc)  # Remove trailing (codes)
        if len(desc_clean) > 60:
            desc_clean = desc_clean[:60].strip()

        desc_lower = desc.lower()
        if any(kw in desc_lower for kw in skip_keywords):
            i = j
            continue

        # Detect if this is income/deposit based on keywords
        is_income = any(kw in desc_lower for kw in income_keywords)
        txn_type = "income" if is_income else "expense"
        txn_amount = -round(amount, 2) if is_income else round(amount, 2)
        txn_category = "Income" if is_income else categorize_transaction(desc)

        transactions.append({
            "date": date_str,
            "description": desc_clean,
            "amount": txn_amount,
            "category": txn_category,
            "type": txn_type,
            "bank_category": "",
        })
        i = j

    return transactions


def _parse_generic_pdf(text: str) -> List[dict]:
    """Fallback generic PDF statement parser. Line-by-line extraction."""
    transactions = []
    date_pattern = re.compile(r"^(\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?)")

    skip_keywords = ["payment thank you", "autopay", "online payment",
                     "cashback", "rewards redemption", "balance transfer"]
    income_keywords = [
        "direct deposit", "payroll", "salary", "wages",
        "deposit", "refund", "credit adjustment", "merchant credit",
        "interest earned", "dividend", "tax refund", "reimbursement",
    ]

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        m = date_pattern.match(line)
        if not m:
            continue

        date_str = _normalize_date_text(m.group(1))
        if not date_str:
            continue

        rest = line[m.end():].strip()
        amounts = re.findall(r"-?\$?[\d,]+\.\d{2}", rest)
        if not amounts:
            continue

        amount_str = amounts[-1].replace(",", "").replace("$", "")
        amount = float(amount_str)
        if amount == 0:
            continue

        last_amt_idx = rest.rfind(amounts[-1])
        desc = rest[:last_amt_idx].strip().rstrip("-").strip()
        if not desc:
            continue

        desc_lower = desc.lower()
        if any(kw in desc_lower for kw in skip_keywords):
            continue

        raw_amount = abs(amount)
        is_income = amount < 0 or any(kw in desc_lower for kw in income_keywords)
        txn_type = "income" if is_income else "expense"
        txn_amount = -round(raw_amount, 2) if is_income else round(raw_amount, 2)
        txn_category = "Income" if is_income else categorize_transaction(desc)

        transactions.append({
            "date": date_str,
            "description": desc[:60].strip(),
            "amount": txn_amount,
            "category": txn_category,
            "type": txn_type,
            "bank_category": "",
        })

    return transactions


def parse_statement(path: Path) -> List[dict]:
    """
    Parse a bank/CC statement file. Auto-detects format (CSV or PDF) based on extension.
    Returns list of {"date": str, "description": str, "amount": float, "category": str}
    """
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_statement_pdf(path)
    else:
        return parse_statement_csv(path)


def _normalize_date(date_str: str) -> str:
    """Try to normalize date string to YYYY-MM-DD format."""
    import re
    s = date_str.strip()

    # Already YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s

    # MM/DD/YYYY or M/D/YYYY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"

    # MM/DD/YY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2})$", s)
    if m:
        year = int(m.group(3))
        year = year + 2000 if year < 50 else year + 1900
        return f"{year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"

    # MM-DD-YYYY
    m = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", s)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"

    return ""


def import_statement(config_path: Path, csv_path: Path, category_overrides: dict = None) -> tuple:
    """
    Parse a bank/CC statement (CSV or PDF) and add transactions to config.
    category_overrides: dict mapping description -> category for manual corrections.
    Returns (count, transactions, message).
    """
    transactions = parse_statement(csv_path)
    if not transactions:
        return 0, [], "No transactions found. Check that the CSV has Date and Description columns."

    # Apply any manual category overrides
    if category_overrides:
        for txn in transactions:
            key = txn["description"]
            if key in category_overrides:
                txn["category"] = category_overrides[key]

    # Load config and add transactions
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    existing_txns = config.get("transactions", [])
    spending_history = config.get("spending_history", {})

    added = 0
    for txn in transactions:
        # Dedup: skip if same date+description+amount already exists
        is_dup = any(
            t.get("date") == txn["date"] and
            t.get("note", "").lower() == txn["description"].lower() and
            abs(t.get("amount", 0) - txn["amount"]) < 0.01
            for t in existing_txns
        )
        if is_dup:
            continue

        entry = {
            "date": txn["date"],
            "category": txn["category"],
            "amount": txn["amount"],
            "note": txn["description"]
        }
        existing_txns.append(entry)
        added += 1

        # Update spending history
        month_key = txn["date"][:7]
        if month_key not in spending_history:
            spending_history[month_key] = {}
        cat = txn["category"]
        spending_history[month_key][cat] = spending_history[month_key].get(cat, 0) + txn["amount"]

    config["transactions"] = existing_txns
    config["spending_history"] = spending_history

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    return added, transactions, f"Imported {added} new transactions ({len(transactions)} total parsed, {len(transactions) - added} duplicates skipped)."


def detect_recurring_transactions(transactions: list, existing_recurring: list = None) -> list:
    """
    Scan transaction history for recurring patterns.
    Looks for merchants/descriptions that appear in 2+ different months
    with similar amounts (within 20% tolerance).
    
    Returns list of suggested recurring items:
    [{"name": str, "amount": float, "category": str, "frequency": str, "occurrences": int, "months": list}]
    """
    from collections import defaultdict

    existing_recurring = existing_recurring or []
    existing_names = {r.get("name", "").lower().strip() for r in existing_recurring}

    # Normalize descriptions: strip digits/dates, collapse whitespace
    def normalize_desc(desc):
        """Collapse a merchant description into a canonical key."""
        d = (desc or "").strip()
        # Remove trailing reference numbers, dates, transaction IDs
        d = re.sub(r'\s*#?\d{4,}$', '', d)  # trailing long numbers
        d = re.sub(r'\s*\d{1,2}/\d{1,2}.*$', '', d)  # trailing dates
        d = re.sub(r'\s+', ' ', d).strip()
        # Take first ~40 chars for grouping (avoids minor suffix variations)
        return d[:40].strip().lower() if d else ""

    # Group transactions by normalized merchant name
    merchant_txns = defaultdict(list)
    for txn in transactions:
        key = normalize_desc(txn.get("note") or txn.get("description", ""))
        if not key or len(key) < 3:
            continue
        merchant_txns[key].append(txn)

    suggestions = []
    for key, txns in merchant_txns.items():
        if len(txns) < 2:
            continue

        # Check how many distinct months this merchant appears in
        months = set()
        amounts = []
        categories = []
        original_names = []
        for t in txns:
            date = t.get("date", "")
            if len(date) >= 7:
                months.add(date[:7])
            amt = t.get("amount", 0)
            if amt > 0:
                amounts.append(amt)
            categories.append(t.get("category", "Other"))
            original_names.append(t.get("note") or t.get("description", ""))

        if len(months) < 2:
            continue  # Must appear in at least 2 different months
        if not amounts:
            continue

        # Check amount consistency (within 20% of median)
        amounts.sort()
        median_amt = amounts[len(amounts) // 2]
        consistent = sum(1 for a in amounts if abs(a - median_amt) / max(median_amt, 0.01) < 0.20)
        if consistent < len(amounts) * 0.6:
            continue  # Amounts too variable

        # Determine frequency based on month gaps
        sorted_months = sorted(months)
        if len(sorted_months) >= 2:
            # Calculate average gap in months
            month_nums = []
            for m in sorted_months:
                parts = m.split("-")
                month_nums.append(int(parts[0]) * 12 + int(parts[1]))
            gaps = [month_nums[i+1] - month_nums[i] for i in range(len(month_nums)-1)]
            avg_gap = sum(gaps) / len(gaps) if gaps else 1
            if avg_gap <= 0.3:
                frequency = "weekly"
            elif avg_gap <= 1.2:
                frequency = "monthly"
            elif avg_gap <= 3.5:
                frequency = "quarterly"
            else:
                frequency = "yearly"
        else:
            frequency = "monthly"

        # Pick the best name (most common original description)
        from collections import Counter
        name_counts = Counter(n.strip() for n in original_names if n.strip())
        best_name = name_counts.most_common(1)[0][0] if name_counts else key.title()

        # Pick most common category
        cat_counts = Counter(categories)
        best_cat = cat_counts.most_common(1)[0][0]

        # Skip if already in recurring list
        if best_name.lower().strip() in existing_names:
            continue
        # Also skip if the normalized key matches any existing name
        if any(normalize_desc(n) == key for n in existing_names):
            continue

        suggestions.append({
            "name": best_name,
            "amount": round(median_amt, 2),
            "category": best_cat,
            "frequency": frequency,
            "occurrences": len(txns),
            "months": sorted_months,
        })

    # Sort by occurrences (most frequent first), then by amount
    suggestions.sort(key=lambda s: (-s["occurrences"], -s["amount"]))
    return suggestions[:20]  # Cap at 20 suggestions


def main():
    import argparse
    p = argparse.ArgumentParser(description="Import Fidelity / Stash / Acorns / Fundrise CSV into config")
    p.add_argument("csv_path", type=Path, help="Path to the CSV file")
    p.add_argument("--source", "-s", required=True,
                    choices=["fidelity", "stash", "acorns", "acorns_invest", "acorns_later", "fundrise"],
                    help="Source of the CSV")
    p.add_argument("--config", "-c", type=Path, default=None, help="Path to config.json (default: same dir)")
    args = p.parse_args()
    base = Path(__file__).resolve().parent
    config_path = args.config or (base / "config.json")
    if not args.csv_path.exists():
        print(f"File not found: {args.csv_path}")
        return 1
    updated, msg = import_csv(config_path, args.csv_path, args.source)
    print(msg)
    return 0 if updated else 1


if __name__ == "__main__":
    exit(main())
