"""Nickel&Dime application factory."""

import os
import logging
from flask import Flask
from .config import config_by_name


def _configure_logging(app):
    """Set up structured logging for Railway/production visibility."""
    level = logging.DEBUG if app.debug else logging.INFO
    fmt = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))

    for logger_name in ("nd", "nd.client", "nd.scheduler", "nd.market", "nd.sentiment", "nd.fred", "nd.calendar"):
        lg = logging.getLogger(logger_name)
        lg.setLevel(level)
        if not lg.handlers:
            lg.addHandler(handler)

    app.logger.setLevel(level)


def create_app(config_name=None):
    """Create and configure the Flask application."""
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "dev") or "dev"

    if config_name not in config_by_name:
        print(f"[WARN] Unknown FLASK_ENV={config_name!r}, falling back to 'prod'")
        config_name = "prod"

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    if hasattr(config_by_name[config_name], "init_app"):
        config_by_name[config_name].init_app(app)

    _configure_logging(app)
    _init_extensions(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_template_globals(app)
    _register_shell_context(app)
    _register_domain_redirect(app)

    if not app.config.get("TESTING") and os.environ.get("RUN_SCHEDULER") == "1":
        _init_scheduler(app)

    return app


def _init_extensions(app):
    """Bind all Flask extensions to the app instance."""
    from .extensions import (
        db, migrate, login_manager, bcrypt, csrf, limiter, mail,
        cache, sess, talisman,
    )

    redis_url = app.config.get("REDIS_URL")
    if redis_url:
        import redis as _redis
        _redis_client = _redis.Redis.from_url(redis_url)
        app.config["SESSION_REDIS"] = _redis_client
        app.config["CACHE_REDIS_URL"] = redis_url
        app.extensions["redis"] = _redis_client
    else:
        app.extensions.setdefault("redis", None)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    mail.init_app(app)
    cache.init_app(app)
    sess.init_app(app)

    if app.config.get("TALISMAN_ENABLED", True):
        csp = {
            "default-src": "'self'",
            "script-src": [
                "'self'",
                "'unsafe-inline'",
                "https://js.stripe.com",
                "https://cdn.jsdelivr.net",
                "https://js.hcaptcha.com",
                "https://newassets.hcaptcha.com",
            ],
            "style-src": [
                "'self'",
                "'unsafe-inline'",
                "https://fonts.googleapis.com",
                "https://newassets.hcaptcha.com",
            ],
            "font-src": [
                "'self'",
                "https://fonts.gstatic.com",
            ],
            "img-src": [
                "'self'",
                "data:",
                "https:",
            ],
            "connect-src": [
                "'self'",
                "https://api.stripe.com",
                "https://cdn.plaid.com",
                "https://production.plaid.com",
                "https://sandbox.plaid.com",
                "https://api.hcaptcha.com",
            ],
            "frame-src": [
                "'self'",
                "https://js.stripe.com",
                "https://cdn.plaid.com",
                "https://newassets.hcaptcha.com",
            ],
            "object-src": "'none'",
            "base-uri": "'self'",
        }
        talisman.init_app(
            app,
            force_https=not app.debug,
            content_security_policy=csp,
            content_security_policy_nonce_in=["script-src"],
            session_cookie_secure=not app.debug,
            strict_transport_security=not app.debug,
            strict_transport_security_max_age=31536000,
            referrer_policy="strict-origin-when-cross-origin",
        )

    from .models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))


def _register_blueprints(app):
    """Register all route blueprints."""
    from .blueprints.auth import auth_bp
    from .blueprints.pages import pages_bp
    from .blueprints.api_market import api_market_bp
    from .blueprints.api_portfolio import api_portfolio_bp
    from .blueprints.api_budget import api_budget_bp
    from .blueprints.api_economics import api_economics_bp
    from .blueprints.api_billing import api_billing_bp
    from .blueprints.api_import import api_import_bp
    from .blueprints.api_settings import api_settings_bp
    from .blueprints.api_plaid import api_plaid_bp
    from .blueprints.api_referral import api_referral_bp
    from .blueprints.blog import blog_bp
    from .blueprints.api_ai import api_ai_bp
    from .blueprints.api_mfa import api_mfa_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(blog_bp)
    app.register_blueprint(api_market_bp, url_prefix="/api")
    app.register_blueprint(api_portfolio_bp, url_prefix="/api")
    app.register_blueprint(api_budget_bp, url_prefix="/api")
    app.register_blueprint(api_economics_bp, url_prefix="/api")
    app.register_blueprint(api_billing_bp, url_prefix="/api")
    app.register_blueprint(api_import_bp, url_prefix="/api")
    app.register_blueprint(api_settings_bp, url_prefix="/api")
    app.register_blueprint(api_plaid_bp, url_prefix="/api")
    app.register_blueprint(api_referral_bp, url_prefix="/api")
    app.register_blueprint(api_ai_bp, url_prefix="/api")
    app.register_blueprint(api_mfa_bp, url_prefix="/api")


def _register_error_handlers(app):
    """Register custom error pages."""
    from flask import render_template, jsonify, request

    @app.errorhandler(400)
    def bad_request(e):
        if request.path.startswith("/api/"):
            msg = getattr(e, "description", "Bad request")
            return jsonify({"error": msg}), 400
        return render_template("errors/500.html"), 400

    @app.errorhandler(403)
    def forbidden(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Forbidden", "upgrade": True, "upgrade_url": "/billing/pricing"}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def request_too_large(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Request too large"}), 413
        return render_template("errors/500.html"), 413

    @app.errorhandler(429)
    def rate_limited(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Too many requests. Please slow down."}), 429
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def server_error(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error"}), 500
        return render_template("errors/500.html"), 500


def _init_scheduler(app):
    """Start the APScheduler background jobs."""
    from .tasks.scheduler import init_scheduler
    try:
        init_scheduler(app)
        app.logger.info("Background scheduler started")
    except Exception as e:
        app.logger.warning("Scheduler init failed: %s", e)


def _register_template_globals(app):
    """Inject common variables into all templates."""
    from datetime import datetime, timezone
    from flask_login import current_user
    import time

    _boot_ts = str(int(time.time()))

    @app.context_processor
    def inject_globals():
        ctx = {
            "now": datetime.now(timezone.utc),
            "trial_days_left": None,
            "v": _boot_ts,
            "hcaptcha_site_key": app.config.get("HCAPTCHA_SITE_KEY", ""),
        }

        try:
            if current_user.is_authenticated and not getattr(current_user, "is_admin", False):
                sub = current_user.subscription
                if sub and sub.status == "trialing" and sub.current_period_end:
                    delta = sub.current_period_end - datetime.now(timezone.utc)
                    ctx["trial_days_left"] = max(0, delta.days)
        except Exception:
            pass

        return ctx


def _register_domain_redirect(app):
    """301 redirect Railway subdomain traffic to the canonical domain + MFA gate."""
    from flask import request, redirect as flask_redirect, session
    from flask_login import current_user as _cu

    CANONICAL = "nickelanddime.io"

    _MFA_EXEMPT = ("/mfa-challenge", "/logout", "/static", "/api/mfa/", "/health")

    @app.before_request
    def _redirect_old_domain():
        host = request.host.split(":")[0]
        if host.endswith(".up.railway.app"):
            return flask_redirect(
                f"https://{CANONICAL}{request.full_path}", code=301
            )

    @app.before_request
    def _enforce_mfa():
        if not _cu.is_authenticated:
            return
        if not getattr(_cu, "mfa_enabled", False):
            return
        if session.get("_mfa_verified"):
            return
        if any(request.path.startswith(p) for p in _MFA_EXEMPT):
            return
        return flask_redirect("/mfa-challenge")


def _register_shell_context(app):
    """Expose objects to `flask shell` for debugging."""
    from .extensions import db
    from .models.user import User, Subscription

    @app.shell_context_processor
    def make_context():
        return {"db": db, "User": User, "Subscription": Subscription}
