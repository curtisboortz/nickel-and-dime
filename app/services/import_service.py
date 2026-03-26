from __future__ import annotations

"""Multi-brokerage CSV import service.

Auto-detects and parses position/holding exports from major brokerages:
  Fidelity, Charles Schwab, Vanguard, E-Trade, Robinhood, WeBull,
  Interactive Brokers, Coinbase, thinkorswim, and generic CSVs.

Each parser normalises rows into a list of dicts:
  {"ticker": str, "shares": float, "account": str, "cost_basis": float|None,
   "description": str, "asset_type": "stock"|"crypto"|"mutual_fund"|"cash"}
"""

import csv
import io
import logging
import re

log = logging.getLogger(__name__)

# Tickers to skip (cash placeholders, pending settlements, totals rows)
_SKIP_SYMBOLS = {
    "", "CASH", "SPAXX", "SPAXX**", "FDRXX", "FDRXX**", "FCASH", "CORE",
    "CORE**", "MMDA1", "VMFXX", "VMFXX**", "VMMXX", "SWVXX", "SWVXX**",
    "Pending Activity", "Account Total", "Cash & Cash Investments",
    "MARGIN", "SHORT", "N/A", "--",
}

# Crypto symbol suffixes on some platforms
_CRYPTO_SUFFIXES = {"-USD", "-USDT", "-USDC", "-BTC", "-ETH"}

# Common crypto base symbols
_CRYPTO_BASES = {
    "BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "DOT", "AVAX", "MATIC",
    "LINK", "UNI", "AAVE", "ATOM", "LTC", "BCH", "ALGO", "NEAR", "FTM",
    "SHIB", "APE", "CRO", "MANA", "SAND", "GRT", "FIL", "ICP", "HBAR",
    "VET", "EOS", "XLM", "XTZ", "THETA", "AXS", "COMP", "MKR", "SNX",
}


def detect_and_parse(file_bytes: bytes, filename: str = "") -> dict:
    """Detect the brokerage format and parse the CSV.

    Returns:
        {
            "brokerage": str,          # detected brokerage name
            "holdings": [...],         # normalised holding dicts
            "skipped": [...],          # rows that were skipped (cash, totals, etc.)
            "errors": [...],           # rows that failed to parse
            "raw_columns": [str],      # original column headers found
        }
    """
    text = file_bytes.decode("utf-8-sig").strip()

    # Some brokerages add non-CSV header lines before the actual data
    text = _strip_preamble(text)

    if not text:
        return {"brokerage": "unknown", "holdings": [], "skipped": [], "errors": ["File is empty"], "raw_columns": []}

    # Sniff the CSV dialect
    try:
        sample = text[:4096]
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        return {"brokerage": "unknown", "holdings": [], "skipped": [], "errors": ["No headers found"], "raw_columns": []}

    headers = [h.strip() for h in reader.fieldnames]
    headers_lower = {h.lower() for h in headers}

    brokerage, parser = _identify_brokerage(headers, headers_lower)

    holdings = []
    skipped = []
    errors = []

    for row_num, row in enumerate(reader, start=2):
        clean = {k.strip(): (v.strip() if v else "") for k, v in row.items() if k}
        try:
            result = parser(clean)
            if result is None:
                skipped.append(f"Row {row_num}: skipped (cash/total/empty)")
                continue
            if result["ticker"] and result["ticker"].upper() not in _SKIP_SYMBOLS:
                holdings.append(result)
            else:
                skipped.append(f"Row {row_num}: skipped '{result.get('ticker', '')}'")
        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")

    log.info("Import: detected=%s holdings=%d skipped=%d errors=%d",
             brokerage, len(holdings), len(skipped), len(errors))

    return {
        "brokerage": brokerage,
        "holdings": holdings,
        "skipped": skipped,
        "errors": errors[:20],
        "raw_columns": headers,
    }


def _strip_preamble(text: str) -> str:
    """Strip non-CSV preamble lines that some brokerages prepend."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        # Fidelity prepends lines like "Brokerage" then blank, then headers
        # Schwab prepends "Positions for account ..." then blank
        # Look for the first line with enough commas to be a CSV header
        if line.count(",") >= 2:
            return "\n".join(lines[i:])
    return text


def _identify_brokerage(headers: list, headers_lower: set) -> tuple:
    """Identify the brokerage from column headers and return (name, parser_fn)."""

    # Fidelity: "Account Name/Number", "Symbol", "Description", "Quantity",
    #           "Last Price", "Current Value", "Cost Basis Per Share"
    if "account name/number" in headers_lower or (
        "current value" in headers_lower and "cost basis per share" in headers_lower
    ):
        return "Fidelity", _parse_fidelity

    # Schwab: "Symbol", "Name", "Quantity", "Price", "Market Value",
    #         "% Of Account" or "Cost Basis"
    if "% of account" in headers_lower or (
        "name" in headers_lower and "market value" in headers_lower and "cost basis" in headers_lower
    ):
        return "Charles Schwab", _parse_schwab

    # Vanguard: "Account Number", "Investment Name", "Symbol", "Shares", "Share Price"
    if "investment name" in headers_lower or (
        "share price" in headers_lower and "shares" in headers_lower
    ):
        return "Vanguard", _parse_vanguard

    # E-Trade: "Symbol", "Price Paid $" or "Qty #"
    if "price paid $" in headers_lower or "qty #" in headers_lower:
        return "E-Trade", _parse_etrade

    # thinkorswim: "Instrument", "Qty", "Trade Price", "Mark"
    if "instrument" in headers_lower and "mark" in headers_lower:
        return "thinkorswim", _parse_thinkorswim

    # Interactive Brokers: "Financial Instrument", "Position", "Cost Basis", "Currency"
    if "financial instrument" in headers_lower or (
        "position" in headers_lower and "cost basis" in headers_lower and "currency" in headers_lower
    ):
        return "Interactive Brokers", _parse_ibkr

    # Robinhood (third-party export): "Average Cost", "Equity", "Total Return"
    if "average cost" in headers_lower and "equity" in headers_lower:
        return "Robinhood", _parse_robinhood

    # WeBull: "Ticker", "Shares", "Avg Cost"
    if "avg cost" in headers_lower and "ticker" in headers_lower:
        return "WeBull", _parse_webull

    # Coinbase: "Asset", "Quantity", "Spot Price" or "Balance"
    if "asset" in headers_lower and ("spot price" in headers_lower or "balance" in headers_lower):
        return "Coinbase", _parse_coinbase

    # M1 Finance: "Account", "Symbol", "Shares", "Average Price"
    if "average price" in headers_lower and "symbol" in headers_lower:
        return "M1 Finance", _parse_m1

    # Generic fallback: look for any symbol/ticker + quantity/shares columns
    return "Generic CSV", _parse_generic


# ── Brokerage-specific parsers ──────────────────────────────────────────────

def _parse_fidelity(row: dict) -> dict | None:
    symbol = _get(row, "Symbol")
    if not symbol or _is_skip(symbol):
        return None
    return {
        "ticker": _clean_ticker(symbol),
        "shares": _to_float(_get(row, "Quantity")),
        "account": _get(row, "Account Name/Number", "Fidelity"),
        "cost_basis": _to_float(_get(row, "Cost Basis Per Share")),
        "description": _get(row, "Description"),
        "asset_type": _detect_asset_type(symbol, _get(row, "Description")),
    }


def _parse_schwab(row: dict) -> dict | None:
    symbol = _get(row, "Symbol")
    if not symbol or _is_skip(symbol):
        return None
    return {
        "ticker": _clean_ticker(symbol),
        "shares": _to_float(_get(row, "Quantity")),
        "account": "Schwab",
        "cost_basis": _to_float(_get(row, "Cost Basis")),
        "description": _get(row, "Name"),
        "asset_type": _detect_asset_type(symbol, _get(row, "Name")),
    }


def _parse_vanguard(row: dict) -> dict | None:
    symbol = _get(row, "Symbol")
    if not symbol or _is_skip(symbol):
        return None
    return {
        "ticker": _clean_ticker(symbol),
        "shares": _to_float(_get(row, "Shares")),
        "account": _get(row, "Account Number", "Vanguard"),
        "cost_basis": _to_float(_get(row, "Share Price")),
        "description": _get(row, "Investment Name"),
        "asset_type": _detect_asset_type(symbol, _get(row, "Investment Name")),
    }


def _parse_etrade(row: dict) -> dict | None:
    symbol = _get(row, "Symbol")
    if not symbol or _is_skip(symbol):
        return None
    return {
        "ticker": _clean_ticker(symbol),
        "shares": _to_float(_get(row, "Qty #", _get(row, "Quantity"))),
        "account": "E-Trade",
        "cost_basis": _to_float(_get(row, "Price Paid $")),
        "description": _get(row, "Description"),
        "asset_type": _detect_asset_type(symbol, _get(row, "Description")),
    }


def _parse_thinkorswim(row: dict) -> dict | None:
    instrument = _get(row, "Instrument")
    if not instrument or _is_skip(instrument):
        return None
    # thinkorswim "Instrument" can be "AAPL 100 16 JUN 23 150 CALL" for options
    # We only want stock positions (single-word instruments)
    parts = instrument.strip().split()
    if len(parts) > 1:
        return None  # skip options/futures
    return {
        "ticker": _clean_ticker(parts[0]),
        "shares": _to_float(_get(row, "Qty")),
        "account": "thinkorswim",
        "cost_basis": _to_float(_get(row, "Trade Price")),
        "description": "",
        "asset_type": _detect_asset_type(parts[0], ""),
    }


def _parse_ibkr(row: dict) -> dict | None:
    symbol = _get(row, "Financial Instrument", _get(row, "Symbol"))
    if not symbol or _is_skip(symbol):
        return None
    return {
        "ticker": _clean_ticker(symbol),
        "shares": _to_float(_get(row, "Position", _get(row, "Quantity"))),
        "account": "IBKR",
        "cost_basis": _to_float(_get(row, "Cost Basis")),
        "description": _get(row, "Description"),
        "asset_type": _detect_asset_type(symbol, _get(row, "Description")),
    }


def _parse_robinhood(row: dict) -> dict | None:
    symbol = _get(row, "Symbol", _get(row, "Ticker"))
    if not symbol or _is_skip(symbol):
        return None
    return {
        "ticker": _clean_ticker(symbol),
        "shares": _to_float(_get(row, "Quantity", _get(row, "Shares"))),
        "account": "Robinhood",
        "cost_basis": _to_float(_get(row, "Average Cost")),
        "description": _get(row, "Name"),
        "asset_type": _detect_asset_type(symbol, _get(row, "Name")),
    }


def _parse_webull(row: dict) -> dict | None:
    symbol = _get(row, "Ticker", _get(row, "Symbol"))
    if not symbol or _is_skip(symbol):
        return None
    return {
        "ticker": _clean_ticker(symbol),
        "shares": _to_float(_get(row, "Shares", _get(row, "Quantity"))),
        "account": "WeBull",
        "cost_basis": _to_float(_get(row, "Avg Cost")),
        "description": _get(row, "Name"),
        "asset_type": _detect_asset_type(symbol, _get(row, "Name")),
    }


def _parse_coinbase(row: dict) -> dict | None:
    asset = _get(row, "Asset", _get(row, "Symbol"))
    if not asset or _is_skip(asset):
        return None
    qty = _to_float(_get(row, "Quantity", _get(row, "Balance")))
    if qty is None or qty == 0:
        return None
    ticker = asset.upper().strip()
    if "-" not in ticker:
        ticker = f"{ticker}-USD"
    return {
        "ticker": ticker,
        "shares": qty,
        "account": "Coinbase",
        "cost_basis": _to_float(_get(row, "Spot Price", _get(row, "Cost Basis"))),
        "description": _get(row, "Name", asset),
        "asset_type": "crypto",
    }


def _parse_m1(row: dict) -> dict | None:
    symbol = _get(row, "Symbol")
    if not symbol or _is_skip(symbol):
        return None
    return {
        "ticker": _clean_ticker(symbol),
        "shares": _to_float(_get(row, "Shares", _get(row, "Quantity"))),
        "account": _get(row, "Account", "M1 Finance"),
        "cost_basis": _to_float(_get(row, "Average Price")),
        "description": _get(row, "Name"),
        "asset_type": _detect_asset_type(symbol, _get(row, "Name")),
    }


def _parse_generic(row: dict) -> dict | None:
    """Flexible parser that hunts for ticker/shares in any column name."""
    ticker = None
    shares = None
    account = ""
    cost_basis = None
    description = ""

    for key, val in row.items():
        kl = key.lower().strip()
        if kl in ("symbol", "ticker", "sym"):
            ticker = val
        elif kl in ("shares", "quantity", "qty", "qty #", "position", "units", "amount"):
            shares = _to_float(val)
        elif kl in ("account", "account name", "account number", "account name/number"):
            account = val
        elif kl in ("cost basis", "cost basis per share", "avg cost", "average cost",
                     "price paid", "price paid $", "average price", "purchase price"):
            cost_basis = _to_float(val)
        elif kl in ("description", "name", "investment name", "security name"):
            description = val

    if not ticker or _is_skip(ticker):
        return None

    return {
        "ticker": _clean_ticker(ticker),
        "shares": shares,
        "account": account or "Imported",
        "cost_basis": cost_basis,
        "description": description,
        "asset_type": _detect_asset_type(ticker, description),
    }


# ── Utility helpers ─────────────────────────────────────────────────────────

def _get(row: dict, *keys, default="") -> str:
    """Case-insensitive dict lookup across multiple possible keys."""
    row_lower = {k.lower().strip(): v for k, v in row.items() if k}
    for key in keys:
        val = row_lower.get(key.lower().strip())
        if val is not None and val.strip():
            return val.strip()
    return default


def _to_float(val: str | None) -> float | None:
    if not val:
        return None
    cleaned = re.sub(r"[,$%\s]", "", str(val))
    cleaned = cleaned.replace("(", "-").replace(")", "")
    if cleaned in ("", "--", "N/A", "n/a"):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _clean_ticker(symbol: str) -> str:
    """Normalize a ticker symbol."""
    s = symbol.strip().upper()
    # Remove trailing ** (Fidelity core position marker)
    s = re.sub(r"\*+$", "", s)
    # Remove leading/trailing whitespace
    s = s.strip()
    return s


def _is_skip(symbol: str) -> bool:
    """Check if a symbol should be skipped (cash, totals, etc.)."""
    s = _clean_ticker(symbol)
    if s in _SKIP_SYMBOLS:
        return True
    if any(kw in s.lower() for kw in ("total", "pending", "cash", "account")):
        return True
    return False


def _detect_asset_type(symbol: str, description: str = "") -> str:
    """Guess the asset type from ticker and description."""
    s = symbol.upper().strip()
    desc = (description or "").lower()

    if any(s.endswith(sfx) for sfx in _CRYPTO_SUFFIXES):
        return "crypto"
    base = s.split("-")[0] if "-" in s else s
    if base in _CRYPTO_BASES:
        return "crypto"
    if "crypto" in desc or "bitcoin" in desc or "ethereum" in desc:
        return "crypto"

    # Mutual funds: 5-letter symbols ending in X
    if len(s) == 5 and s.endswith("X") and s.isalpha():
        return "mutual_fund"
    if "mutual fund" in desc or "money market" in desc:
        return "mutual_fund"

    return "stock"


def get_supported_brokerages() -> list[dict]:
    """Return list of supported brokerages with instructions."""
    return [
        {
            "id": "fidelity",
            "name": "Fidelity",
            "instructions": "Log in → Accounts & Trade → Positions → click Download (CSV icon)",
        },
        {
            "id": "schwab",
            "name": "Charles Schwab",
            "instructions": "Log in → Accounts → Positions → click Export",
        },
        {
            "id": "vanguard",
            "name": "Vanguard",
            "instructions": "Log in → My Accounts → Holdings → Download (CSV)",
        },
        {
            "id": "etrade",
            "name": "E-Trade",
            "instructions": "Log in → Portfolios → Positions → Export to File",
        },
        {
            "id": "thinkorswim",
            "name": "thinkorswim (Schwab)",
            "instructions": "Monitor tab → Activity and Positions → Export to file",
        },
        {
            "id": "robinhood",
            "name": "Robinhood",
            "instructions": "Use the Robinhood Portfolio Exporter Chrome extension, or Account → Statements → Download",
        },
        {
            "id": "webull",
            "name": "WeBull",
            "instructions": "Desktop app → Portfolio → Export Positions",
        },
        {
            "id": "ibkr",
            "name": "Interactive Brokers",
            "instructions": "Account Management → Reports → Activity Statements → CSV",
        },
        {
            "id": "coinbase",
            "name": "Coinbase",
            "instructions": "Settings → Privacy & Security → Download your data",
        },
        {
            "id": "m1",
            "name": "M1 Finance",
            "instructions": "Research tab → Holdings → Export to CSV",
        },
        {
            "id": "generic",
            "name": "Other / Custom CSV",
            "instructions": "CSV with columns: Symbol, Shares (or Quantity), and optionally Account, Cost Basis",
        },
    ]
