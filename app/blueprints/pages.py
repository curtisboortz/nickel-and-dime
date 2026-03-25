"""Page routes: landing, dashboard, and tab-specific content."""

from datetime import datetime, timezone

from flask import Blueprint, render_template, redirect, url_for, Response
from flask_login import login_required, current_user

from ..utils.auth import is_pro

pages_bp = Blueprint("pages", __name__)


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
        xml += f"  <url><loc>https://nickeldime.io{path}</loc></url>\n"
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
        demo_mode=False,
    )


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
