"""Page routes: landing, dashboard, and tab-specific content."""

from datetime import datetime, timezone

from flask import Blueprint, render_template, redirect, url_for, Response, abort, jsonify, send_from_directory, current_app, request as flask_request
from flask_login import login_required, current_user

from ..utils.auth import is_pro

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/icon-192.png")
def serve_icon_192():
    return send_from_directory(current_app.static_folder + "/img", "icon-192.png")


@pages_bp.route("/icon-512.png")
def serve_icon_512():
    return send_from_directory(current_app.static_folder + "/img", "icon-512.png")


@pages_bp.route("/apple-touch-icon.png")
def serve_apple_icon():
    return send_from_directory(current_app.static_folder + "/img", "apple-touch-icon.png")


@pages_bp.route("/favicon.ico")
def serve_favicon():
    return send_from_directory(current_app.static_folder + "/img", "favicon.ico")


@pages_bp.route("/sw.js")
def serve_sw():
    return send_from_directory(current_app.static_folder, "sw.js",
                               mimetype="application/javascript")


@pages_bp.route("/health")
def health():
    """Lightweight healthcheck endpoint for Railway. No DB or template needed."""
    return "ok", 200


@pages_bp.route("/api/diag")
@login_required
def diagnostics():
    """Admin-only diagnostics: full system health report."""
    import os, traceback
    from datetime import datetime, timezone, timedelta
    if not getattr(current_user, "is_admin", False):
        abort(403)

    now = datetime.now(timezone.utc)
    stale_threshold = now - timedelta(hours=1)
    health = "healthy"
    issues = []
    result = {"health": health, "issues": issues, "timestamp": now.isoformat()}

    try:
        from ..models.market import PriceCache, FredCache, SentimentCache, EconCalendarCache
        from ..models.user import User, Subscription

        prices = PriceCache.query.all()
        fresh_prices = [p for p in prices if p.updated_at and p.updated_at.replace(tzinfo=timezone.utc) > stale_threshold]
        stale_prices = [p for p in prices if not p.updated_at or p.updated_at.replace(tzinfo=timezone.utc) <= stale_threshold]
        price_sample = {p.symbol: {"price": p.price, "updated": str(p.updated_at)} for p in prices[:30]}
        result["prices"] = {
            "total": len(prices), "fresh": len(fresh_prices),
            "stale": len(stale_prices), "sample": price_sample,
        }

        critical_symbols = ["^GSPC", "^DJI", "^IXIC", "GC=F", "SI=F", "^VIX", "^TNX", "BTC-USD", "ETH-USD", "DX-Y.NYB"]
        missing_prices = [s for s in critical_symbols if not any(p.symbol == s and p.price for p in prices)]
        result["prices"]["missing_critical"] = missing_prices
        if missing_prices:
            issues.append(f"Missing prices for: {', '.join(missing_prices)}")
        if len(stale_prices) > len(fresh_prices):
            issues.append(f"{len(stale_prices)}/{len(prices)} prices are stale (>1h)")
        if not prices:
            health = "critical"

        fred_rows = FredCache.query.all()
        fred_status = {}
        for f in fred_rows:
            age_min = int((now - f.updated_at.replace(tzinfo=timezone.utc)).total_seconds() / 60) if f.updated_at else -1
            has_data = bool(f.data) and len(f.data) > 0 if f.data else False
            fred_status[f.series_group] = {"has_data": has_data, "age_minutes": age_min}
        result["fred"] = fred_status
        if not fred_rows:
            issues.append("FRED cache is empty")

        sent_rows = SentimentCache.query.all()
        sentiment_status = {}
        for s in sent_rows:
            age_min = int((now - s.updated_at.replace(tzinfo=timezone.utc)).total_seconds() / 60) if s.updated_at else -1
            sentiment_status[s.source] = {"data": s.data, "age_minutes": age_min}
        result["sentiment"] = sentiment_status
        if not any(s.source == "cnn_fg" for s in sent_rows):
            issues.append("CNN Fear & Greed not cached")
        if not any(s.source == "crypto_fg" for s in sent_rows):
            issues.append("Crypto Fear & Greed not cached")

        cal = EconCalendarCache.query.first()
        if cal:
            cal_age = int((now - cal.updated_at.replace(tzinfo=timezone.utc)).total_seconds() / 60) if cal.updated_at else -1
            cal_weeks = list(cal.data.keys()) if cal.data else []
            result["calendar"] = {"age_minutes": cal_age, "weeks": cal_weeks}

        result["users"] = {
            "total": User.query.count(),
            "subscriptions": Subscription.query.count(),
            "active_subs": Subscription.query.filter(Subscription.status == "active").count(),
        }
    except Exception as exc:
        issues.append(f"Diag query error: {exc}")
        health = "error"

    if issues and health == "healthy":
        health = "degraded"
    result["health"] = health
    result["issues"] = issues

    result["env"] = {
        "run_scheduler": os.environ.get("RUN_SCHEDULER", "NOT SET"),
        "admin_emails_set": bool(os.environ.get("ADMIN_EMAILS")),
        "database_url_set": bool(os.environ.get("DATABASE_URL")),
        "flask_env": os.environ.get("FLASK_ENV", "NOT SET"),
        "stripe_key_set": bool(os.environ.get("STRIPE_SECRET_KEY")),
        "fred_key_set": bool(os.environ.get("FRED_API_KEY")),
        "cmc_key_set": bool(os.environ.get("CMC_API_KEY")),
        "redis_url_set": bool(os.environ.get("REDIS_URL")),
    }
    result["redis"] = {
        "connected": _redis_healthy(),
        "backend": "redis" if os.environ.get("REDIS_URL") else "in-memory",
    }
    return jsonify(result)


def _redis_healthy():
    try:
        from ..utils.redis_helpers import redis_health
        return redis_health()
    except Exception:
        return False


@pages_bp.route("/api/client-errors", methods=["POST"])
@login_required
def client_errors():
    """Receive client-side error reports from the NDDiag framework."""
    import logging
    data = flask_request.get_json(silent=True) or {}
    errors = data.get("errors", [])
    widgets = data.get("widgets", {})
    user_email = current_user.email if hasattr(current_user, "email") else "unknown"
    logger = logging.getLogger("nd.client")
    for err in errors[-20:]:
        logger.warning(
            "[ClientError] user=%s widget=%s detail=%s time=%s url=%s",
            user_email, err.get("widget", "?"), err.get("detail", "?"),
            err.get("time", "?"), data.get("url", "?"),
        )
    failed = [k for k, v in widgets.items() if v == "error"]
    if failed:
        logger.warning("[ClientReport] user=%s failed_widgets=%s", user_email, ",".join(failed))
    return jsonify({"received": len(errors)})


@pages_bp.route("/manifest.json")
def manifest():
    return redirect(url_for("static", filename="manifest.json"))


@pages_bp.route("/robots.txt")
def robots():
    return Response(
        "User-agent: *\nAllow: /\nDisallow: /dashboard\nDisallow: /api/\nSitemap: /sitemap.xml\n",
        mimetype="text/plain",
    )


@pages_bp.route("/sitemap.xml")
def sitemap():
    from ..models.blog import BlogPost
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    static_paths = ["/", "/login", "/register", "/billing/pricing", "/blog"]
    for path in static_paths:
        xml += f"  <url><loc>https://nickelanddime.io{path}</loc></url>\n"
    posts = BlogPost.query.filter_by(published=True).all()
    for p in posts:
        lastmod = (p.updated_at or p.created_at).strftime("%Y-%m-%d") if p.updated_at or p.created_at else ""
        xml += f'  <url><loc>https://nickelanddime.io/blog/{p.slug}</loc>'
        if lastmod:
            xml += f"<lastmod>{lastmod}</lastmod>"
        xml += "</url>\n"
    xml += "</urlset>\n"
    return Response(xml, mimetype="application/xml")


@pages_bp.route("/lp/macro-investors")
def lp_macro():
    """Dedicated ad landing page for macro-focused investors."""
    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard_page"))
    return render_template("lp_macro.html", now=datetime.now(timezone.utc))


@pages_bp.route("/")
def landing():
    """Landing / marketing page for logged-out visitors, dashboard for logged-in."""
    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard_page"))
    return render_template("landing.html", now=datetime.now(timezone.utc))


@pages_bp.route("/dashboard")
@pages_bp.route("/dashboard/<tab>")
@login_required
def dashboard_page(tab="summary"):
    """Main dashboard view. Tab content loaded via AJAX for non-default tabs."""
    from ..models.settings import UserSettings, CustomPulseCard
    valid_tabs = [
        "summary", "balances", "holdings", "budget",
        "import", "history", "economics", "technical", "ai",
    ]
    if tab not in valid_tabs:
        tab = "summary"
    try:
        us = UserSettings.query.filter_by(
            user_id=current_user.id
        ).first()
    except Exception:
        from ..extensions import db
        db.session.rollback()
        us = None
    wo = (us.widget_order if us and isinstance(us.widget_order, dict) else {}) or {}
    hidden_pulse = wo.get("hidden_pulse", [])
    pulse_size = wo.get("pulse_size", "compact")
    pulse_order = us.pulse_order if us and isinstance(us.pulse_order, list) else []
    custom_cards = CustomPulseCard.query.filter_by(
        user_id=current_user.id
    ).order_by(CustomPulseCard.position).all()
    show_onboarding = (
        us is None
        or not getattr(us, "onboarding_completed", False)
    )
    return render_template(
        "dashboard/layout.html",
        active_tab=tab,
        user=current_user,
        is_pro=is_pro(),
        hidden_pulse=hidden_pulse,
        pulse_size=pulse_size,
        pulse_order=pulse_order,
        custom_pulse_cards=custom_cards,
        show_onboarding=show_onboarding,
    )


@pages_bp.route("/api/dashboard-layout", methods=["GET"])
@login_required
def get_dashboard_layout():
    """Return the user's saved grid layout, or an empty list for defaults."""
    from ..models.settings import UserSettings
    us = UserSettings.query.filter_by(user_id=current_user.id).first()
    layout = (us.dashboard_layout if us and us.dashboard_layout else None)
    return jsonify({"layout": layout})


@pages_bp.route("/api/dashboard-layout", methods=["POST"])
@login_required
def save_dashboard_layout():
    """Persist the user's grid layout."""
    from ..extensions import db
    from ..models.settings import UserSettings
    data = flask_request.get_json(silent=True) or {}
    layout = data.get("layout", [])
    us = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not us:
        us = UserSettings(user_id=current_user.id)
        db.session.add(us)
    us.dashboard_layout = layout
    db.session.commit()
    return jsonify({"ok": True})


@pages_bp.route("/api/tab-content/<tab_name>")
@login_required
def tab_content(tab_name):
    """Return HTML fragment for a lazy-loaded tab."""
    if tab_name == "economics":
        return render_template("dashboard/partials/economics.html", is_pro=is_pro())
    abort(404)


@pages_bp.route("/economics")
@login_required
def economics():
    return redirect(url_for("pages.dashboard_page", tab="economics"))


@pages_bp.route("/technical")
@login_required
def technical():
    return redirect(url_for("pages.dashboard_page", tab="technical"))


@pages_bp.route("/billing/pricing")
@login_required
def pricing():
    """Plan comparison and upgrade page."""
    return render_template("billing/pricing.html", user=current_user)


@pages_bp.route("/billing/account")
@login_required
def billing_account():
    """Subscription management page."""
    return render_template("billing/account.html", user=current_user)


@pages_bp.route("/terms")
def terms():
    return render_template("legal/terms.html")


@pages_bp.route("/privacy")
def privacy():
    return render_template("legal/privacy.html")


@pages_bp.route("/disclaimer")
def disclaimer():
    return render_template("legal/disclaimer.html")
