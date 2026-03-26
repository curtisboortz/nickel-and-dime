"""Page routes: landing, dashboard, and tab-specific content."""

from datetime import datetime, timezone

from flask import Blueprint, render_template, redirect, url_for, Response, abort, jsonify, send_from_directory, current_app
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


@pages_bp.route("/health")
def health():
    """Lightweight healthcheck endpoint for Railway. No DB or template needed."""
    return "ok", 200


@pages_bp.route("/api/diag")
@login_required
def diagnostics():
    """Admin-only diagnostics: DB counts, scheduler status, env checks."""
    import os
    if not getattr(current_user, "is_admin", False):
        abort(403)

    from ..extensions import db
    from ..models.market import PriceCache
    from ..models.user import User, Subscription

    prices = PriceCache.query.all()
    price_summary = {p.symbol: {"price": p.price, "updated": str(p.updated_at)} for p in prices[:20]}

    users = User.query.count()
    subs = Subscription.query.count()

    return jsonify({
        "price_cache_count": len(prices),
        "price_sample": price_summary,
        "user_count": users,
        "subscription_count": subs,
        "run_scheduler": os.environ.get("RUN_SCHEDULER", "NOT SET"),
        "admin_emails": os.environ.get("ADMIN_EMAILS", "NOT SET"),
        "database_url_set": bool(os.environ.get("DATABASE_URL")),
        "flask_env": os.environ.get("FLASK_ENV", "NOT SET"),
    })


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
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for path in ["/", "/login", "/register", "/billing/pricing"]:
        xml += f"  <url><loc>https://nickelanddime.io{path}</loc></url>\n"
    xml += "</urlset>\n"
    return Response(xml, mimetype="application/xml")


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
    valid_tabs = [
        "summary", "balances", "holdings", "budget",
        "import", "history", "economics", "technical",
    ]
    if tab not in valid_tabs:
        tab = "summary"
    return render_template(
        "dashboard/layout.html",
        active_tab=tab,
        user=current_user,
        is_pro=is_pro(),
    )


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
