"""WSGI entry point for production deployment (gunicorn)."""

import os
import sys
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

try:
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env")
except ImportError:
    pass

DEMO_MODE = os.environ.get("DEMO_MODE", "").lower() in ("1", "true", "yes")
CONFIG_PATH = BASE / "config.json"

if DEMO_MODE:
    import shutil
    for src, dst in [
        ("sample_config.json", "config.json"),
        ("sample_price_cache.json", "price_cache.json"),
        ("sample_price_history.json", "price_history.json"),
    ]:
        src_path = BASE / src
        if src_path.exists():
            shutil.copy(src_path, BASE / dst)

from flask import Flask
from finance_manager import (
    load_config, run_update, get_effective_api_keys,
    get_dashboard_data, get_dashboard_data_cached,
)
from csv_import import import_csv, parse_statement_csv, parse_statement, import_statement, detect_recurring_transactions
from dashboard import render_dashboard
from routes import bp, init_routes
from server import append_history_log

AUTH_PIN = os.environ.get("WEALTH_OS_PIN", "")

def save_config(path, cfg):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def run_price_update(config, fetch_metals=True):
    tickers = list(
        {h["ticker"] for h in config.get("holdings", []) if h.get("ticker") and h["ticker"] != "SPAXX"}
    )
    for cp in config.get("custom_pulse_cards", []):
        t = cp.get("ticker", "").upper()
        if t and t not in tickers:
            tickers.append(t)
    crypto_symbols = [c["symbol"] for c in config.get("crypto_holdings", [])]
    gold_key = get_effective_api_keys(config).get("goldapi_io", "")
    run_update(BASE, config, tickers, crypto_symbols, gold_key, fetch_metals=fetch_metals, verbose=False)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "wealth-os-prod-key-change-me")

init_routes({
    "CONFIG_PATH": CONFIG_PATH,
    "BASE": BASE,
    "AUTH_PIN": AUTH_PIN,
    "DEMO_MODE": DEMO_MODE,
    "load_config": load_config,
    "run_update": run_update,
    "get_effective_api_keys": get_effective_api_keys,
    "get_dashboard_data": get_dashboard_data,
    "get_dashboard_data_cached": get_dashboard_data_cached,
    "import_csv": import_csv,
    "parse_statement_csv": parse_statement_csv,
    "parse_statement": parse_statement,
    "import_statement": import_statement,
    "detect_recurring_transactions": detect_recurring_transactions,
    "render_dashboard": render_dashboard,
    "append_history_log": append_history_log,
    "save_config": save_config,
    "run_price_update": run_price_update,
    "scheduler": None,
})
app.register_blueprint(bp)
