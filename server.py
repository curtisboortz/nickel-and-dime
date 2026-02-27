"""
Local server for the Nickel&Dime dashboard.
Run: python server.py
Then open http://localhost:5000 — one interface: Summary, Balances, Budget, Investments.
Saves go to config.json and are logged to Excel History sheet.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

# Run from finance-tool directory
BASE = Path(__file__).resolve().parent
PROJECT_ROOT = BASE
sys.path.insert(0, str(BASE))

# Load .env so API keys work when running server
try:
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env")
except ImportError:
    pass

DEMO_MODE = os.environ.get("DEMO_MODE", "").lower() in ("1", "true", "yes")

if DEMO_MODE:
    import shutil
    import tempfile
    DEMO_DIR = Path(tempfile.mkdtemp(prefix="nickeldime_demo_"))
    for src, dst in [
        ("sample_config.json", "config.json"),
        ("sample_price_cache.json", "price_cache.json"),
        ("sample_price_history.json", "price_history.json"),
    ]:
        src_path = BASE / src
        if src_path.exists():
            shutil.copy(src_path, DEMO_DIR / dst)
    CONFIG_PATH = DEMO_DIR / "config.json"
    BASE = DEMO_DIR
    print(f"[DEMO MODE] Sample data loaded into temp dir — your real files are untouched")
else:
    CONFIG_PATH = BASE / "config.json"

# Auth PIN: set WEALTH_OS_PIN in .env (e.g. WEALTH_OS_PIN=1234). If unset, no auth required.
AUTH_PIN = os.environ.get("WEALTH_OS_PIN", "")


def append_history_log(action: str, details: str = "") -> None:
    from finance_manager import append_history_log as _log
    _log(BASE, action, details)


def main():
    try:
        from flask import Flask, request, redirect
    except ImportError:
        print("Flask is required. Run: pip install flask")
        sys.exit(1)

    from finance_manager import (
        load_config,
        run_update,
        get_effective_api_keys,
        get_dashboard_data,
        get_dashboard_data_cached,
    )
    from csv_import import import_csv, parse_statement_csv, parse_statement, import_statement, detect_recurring_transactions
    from dashboard import render_dashboard
    from routes import bp, init_routes

    def save_config(path, cfg):
        """Write config dict to JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

    def run_price_update(config, fetch_metals=True):
        tickers = list(
            {h["ticker"] for h in config.get("holdings", []) if h.get("ticker") and h["ticker"] != "SPAXX"}
        )
        # Include custom pulse card tickers so their prices are fetched
        for cp in config.get("custom_pulse_cards", []):
            t = cp.get("ticker", "").upper()
            if t and t not in tickers:
                tickers.append(t)
        crypto_symbols = [c["symbol"] for c in config.get("crypto_holdings", [])]
        gold_key = get_effective_api_keys(config).get("goldapi_io", "")
        run_update(BASE, config, tickers, crypto_symbols, gold_key, fetch_metals=fetch_metals, verbose=False)

    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET", "wealth-os-default-key-change-me")

    # ── Scheduled auto-refresh — runs even when browser is closed ──
    # Only start scheduler in the reloader child process (or when reloader is off)
    # to avoid duplicate jobs when use_reloader=True
    is_reloader_parent = os.environ.get("WERKZEUG_RUN_MAIN") != "true"
    scheduler = None
    if not is_reloader_parent:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            scheduler = BackgroundScheduler(daemon=True)

            def scheduled_refresh():
                import datetime as dt
                now = dt.datetime.now()
                try:
                    config = load_config(CONFIG_PATH)
                    auto_cfg = config.get("auto_refresh", {})
                    if not auto_cfg.get("enabled", True):
                        return  # auto-refresh disabled by user

                    # Determine if metals should be fetched (conserve GoldAPI calls — max 4x/day)
                    fetch_metals = now.hour % 6 == 0 and now.minute < 20

                    run_price_update(config, fetch_metals=fetch_metals)
                    print(f"[Auto-refresh] Prices updated at {now.strftime('%Y-%m-%d %H:%M')}")
                except Exception as e:
                    print(f"[Auto-refresh] Error: {e}")

            # Read interval from config (default 15 min)
            initial_config = load_config(CONFIG_PATH)
            auto_cfg = initial_config.get("auto_refresh", {})
            interval_min = auto_cfg.get("interval_minutes", 15)
            if interval_min < 5:
                interval_min = 5  # minimum 5 minutes to avoid API abuse
            scheduler.add_job(scheduled_refresh, "interval", minutes=interval_min, id="auto_refresh")
            scheduler.start()
            print(f"Auto-refresh: Every {interval_min} min (24/7, including crypto & metals)")
        except ImportError:
            scheduler = None
            print("Note: Install 'apscheduler' for automatic price refresh (pip install apscheduler)")

    # Pre-seed metals cache on startup so first page load has real prices
    if not is_reloader_parent:
        import threading
        def _warm_metals_cache():
            try:
                from finance_manager import load_price_cache, save_price_cache, fetch_metals_prices
                pc = load_price_cache(BASE)
                if not pc.get("metals") or not pc["metals"].get("GOLD"):
                    cfg = load_config(CONFIG_PATH)
                    gold_key = get_effective_api_keys(cfg).get("goldapi_io", "")
                    mp = fetch_metals_prices(gold_key, verbose=False)
                    if mp:
                        save_price_cache(BASE, metals=mp)
                        print(f"[Startup] Metals cache primed: GOLD=${mp.get('GOLD',0):.0f} SILVER=${mp.get('SILVER',0):.2f}")
            except Exception as e:
                print(f"[Startup] Metals cache warm failed: {e}")
        threading.Thread(target=_warm_metals_cache, daemon=True).start()

    # Initialize routes with all dependencies
    init_routes({
        "CONFIG_PATH": CONFIG_PATH,
        "BASE": BASE,
        "PROJECT_ROOT": PROJECT_ROOT,
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
        "scheduler": scheduler,
    })
    app.register_blueprint(bp)

    # ── HTTPS Support (self-signed cert) ──
    ssl_ctx = None
    use_https = os.environ.get("WEALTH_OS_HTTPS", "").lower() in ("1", "true", "yes")
    if use_https:
        cert_path = BASE / "cert.pem"
        key_path = BASE / "key.pem"
        if not cert_path.exists() or not key_path.exists():
            try:
                import subprocess
                print("Generating self-signed SSL certificate...")
                subprocess.run([
                    "openssl", "req", "-x509", "-newkey", "rsa:2048",
                    "-keyout", str(key_path), "-out", str(cert_path),
                    "-days", "365", "-nodes",
                    "-subj", "/CN=localhost/O=NickelAndDime/C=US"
                ], check=True, capture_output=True)
                print(f"SSL cert generated: {cert_path}")
            except (FileNotFoundError, subprocess.CalledProcessError):
                # Fallback: use Python ssl module to create a self-signed cert
                try:
                    from cryptography import x509
                    from cryptography.x509.oid import NameOID
                    from cryptography.hazmat.primitives import hashes, serialization
                    from cryptography.hazmat.primitives.asymmetric import rsa
                    import datetime as dt
                    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
                    subject = issuer = x509.Name([
                        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
                        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Nickel&Dime"),
                    ])
                    cert = (x509.CertificateBuilder()
                            .subject_name(subject)
                            .issuer_name(issuer)
                            .public_key(key.public_key())
                            .serial_number(x509.random_serial_number())
                            .not_valid_before(dt.datetime.utcnow())
                            .not_valid_after(dt.datetime.utcnow() + dt.timedelta(days=365))
                            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
                            .sign(key, hashes.SHA256()))
                    with open(key_path, "wb") as f:
                        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
                    with open(cert_path, "wb") as f:
                        f.write(cert.public_bytes(serialization.Encoding.PEM))
                    print(f"SSL cert generated via cryptography library: {cert_path}")
                except ImportError:
                    print("HTTPS requested but neither openssl nor cryptography package available.")
                    print("Install: pip install cryptography  OR set WEALTH_OS_HTTPS=0")
                    use_https = False
        if use_https and cert_path.exists() and key_path.exists():
            import ssl
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_ctx.load_cert_chain(str(cert_path), str(key_path))

    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    protocol = "https" if ssl_ctx else "http"
    print(f"Nickel&Dime: {protocol}://{host}:{port}")
    print("One interface: Summary | Balances | Budget | Holdings. Saves -> config + Excel History.")
    if DEMO_MODE:
        print("[DEMO MODE] Write operations disabled. Sample data loaded.")
    if ssl_ctx:
        print("HTTPS enabled (self-signed cert). Browser may show a security warning - this is normal.")
    print("Ctrl+C to stop.")
    app.run(host=host, port=port, debug=False, use_reloader=not DEMO_MODE, ssl_context=ssl_ctx)


if __name__ == "__main__":
    main()
