"""Authentication routes: register, login, logout, password reset, email verification."""

import secrets
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user

from ..extensions import db, bcrypt, limiter, cache
from ..models.user import User, Subscription, PromoCode
from ..models.settings import UserSettings
from ..utils.captcha import verify_captcha, captcha_enabled
from ..utils.audit import log_event

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_TTL = 900  # 15 minutes

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard_page"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        name = request.form.get("name", "").strip()

        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("auth/register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("auth/register.html")

        if not verify_captcha(request.form.get("h-captcha-response", "")):
            flash("Please complete the CAPTCHA.", "error")
            return render_template("auth/register.html")

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
            return render_template("auth/register.html")

        promo_code_str = request.form.get("promo_code", "").strip().upper()
        trial_days = 14
        promo = None
        if promo_code_str:
            promo = PromoCode.query.filter_by(code=promo_code_str).first()
            if not promo or not promo.is_valid:
                flash("Invalid or expired promo code.", "error")
                return render_template("auth/register.html")
            trial_days = promo.trial_days

        user = User(email=email, name=name or email.split("@")[0], plan="pro")
        user.set_password(password)

        verify_token = secrets.token_urlsafe(32)
        user.verify_token = verify_token

        db.session.add(user)

        settings = UserSettings(user=user)
        db.session.add(settings)

        trial_end = datetime.now(timezone.utc) + timedelta(days=trial_days)
        sub = Subscription(
            user=user, plan="pro", status="trialing",
            current_period_end=trial_end,
        )
        db.session.add(sub)

        if promo:
            promo.times_used += 1

        db.session.commit()

        try:
            from ..services.new_user_template import apply_new_user_template
            apply_new_user_template(user.id)
        except Exception as e:
            current_app.logger.warning(
                "New-user template apply failed for %s: %s", user.email, e
            )
            db.session.rollback()

        from ..services.email_service import send_email_verification, send_welcome
        send_email_verification(user, verify_token)
        send_welcome(user)

        login_user(user)
        trial_label = f"{trial_days}-day" if trial_days != 90 else "3-month"
        flash(
            f"Welcome! Your {trial_label} Pro trial is active. "
            "Check your email to verify your address.",
            "success",
        )
        return redirect(url_for("pages.dashboard_page"))

    return render_template("auth/register.html")


@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    """Verify a user's email address via the token sent at registration."""
    user = User.query.filter_by(verify_token=token).first()
    if not user:
        flash("Invalid or expired verification link.", "error")
        return redirect(url_for("auth.login"))

    user.email_verified = True
    user.verify_token = None
    db.session.commit()

    flash("Email verified! Thank you.", "success")
    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard_page"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-verification")
@login_required
def resend_verification():
    """Resend the email verification link."""
    if current_user.email_verified:
        flash("Your email is already verified.", "info")
        return redirect(url_for("pages.dashboard_page"))

    token = secrets.token_urlsafe(32)
    current_user.verify_token = token
    db.session.commit()

    from ..services.email_service import send_email_verification
    send_email_verification(current_user, token)

    flash("Verification email sent. Check your inbox.", "info")
    return redirect(url_for("pages.dashboard_page"))


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per hour")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard_page"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"

        fail_key = f"login_fail:{email}"
        fail_count = cache.get(fail_key) or 0
        if fail_count >= MAX_LOGIN_ATTEMPTS:
            flash("Too many failed attempts, try again later.", "error")
            return render_template("auth/login.html")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            cache.delete(fail_key)
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            login_user(user, remember=remember)
            log_event("login_success", user_id=user.id)

            from flask import session as flask_session
            old_data = dict(flask_session)
            flask_session.clear()
            flask_session.update(old_data)

            if user.mfa_enabled and user.totp_secret:
                flask_session["_mfa_verified"] = False
                next_page = request.args.get("next", "")
                return redirect(url_for("auth.mfa_challenge", next=next_page))

            flask_session["_mfa_verified"] = True

            try:
                from ..services.portfolio_service import backfill_snapshots
                backfill_snapshots(user.id)
            except Exception:
                pass

            next_page = request.args.get("next")
            if next_page:
                parsed = urlparse(next_page)
                if parsed.netloc or parsed.scheme:
                    next_page = None
            return redirect(next_page or url_for("pages.dashboard_page"))

        cache.set(fail_key, fail_count + 1, timeout=LOGIN_LOCKOUT_TTL)
        log_event("login_failed", detail={"email": email})
        flash("Invalid email or password.", "error")

    return render_template("auth/login.html")


@auth_bp.route("/mfa-challenge", methods=["GET", "POST"])
@login_required
def mfa_challenge():
    """Prompt for TOTP code after password login when MFA is enabled."""
    from flask import session as flask_session
    import pyotp
    from ..utils.encryption import decrypt

    if not current_user.mfa_enabled:
        return redirect(url_for("pages.dashboard_page"))

    if flask_session.get("_mfa_verified"):
        return redirect(url_for("pages.dashboard_page"))

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        secret = decrypt(current_user.totp_secret)
        totp = pyotp.TOTP(secret)
        if totp.verify(code, valid_window=1):
            old_data = dict(flask_session)
            flask_session.clear()
            flask_session.update(old_data)
            flask_session["_mfa_verified"] = True
            log_event("mfa_challenge_success")
            next_page = request.args.get("next")
            if next_page:
                parsed = urlparse(next_page)
                if parsed.netloc or parsed.scheme:
                    next_page = None
            return redirect(next_page or url_for("pages.dashboard_page"))
        log_event("mfa_challenge_failed")
        flash("Invalid verification code.", "error")

    return render_template("auth/mfa_challenge.html")


@auth_bp.route("/logout")
@login_required
def logout():
    from flask import session as flask_session, make_response
    log_event("logout")
    # Wipe any user-specific session data first, THEN call logout_user.
    # Order matters: logout_user() sets session["_remember"] = "clear" so
    # Flask-Login can drop the persistent remember-me cookie at end of
    # request. Calling flask_session.clear() afterward would remove that
    # flag and the remember cookie would survive, silently re-authenticating
    # the user on the next request.
    flask_session.clear()
    logout_user()
    resp = make_response(redirect(url_for("pages.landing")))
    # Belt-and-braces: explicitly delete the remember-me cookie too, in case
    # logout_user couldn't (e.g. cookie name was customized in config).
    remember_cookie = current_app.config.get("REMEMBER_COOKIE_NAME", "remember_token")
    resp.delete_cookie(remember_cookie, path="/")
    return resp


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def forgot_password():
    import sys
    if request.method == "POST":
        if not verify_captcha(request.form.get("h-captcha-response", "")):
            flash("Please complete the CAPTCHA.", "error")
            return render_template("auth/forgot_password.html")

        email = request.form.get("email", "").strip().lower()
        print(f"[ForgotPW] Lookup email: {email}", flush=True, file=sys.stderr)
        user = User.query.filter_by(email=email).first()
        print(f"[ForgotPW] User found: {user is not None}", flush=True, file=sys.stderr)
        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
            db.session.commit()
            log_event("password_reset_requested", user_id=user.id)

            from ..services.email_service import send_password_reset_sync
            err = send_password_reset_sync(user, token)
            if err:
                print(f"[ForgotPW] EMAIL ERROR: {err}", flush=True, file=sys.stderr)

        flash("If that email exists, a reset link has been sent.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    expiry = user.reset_token_expiry if user else None
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if not user or not expiry or expiry < datetime.now(timezone.utc):
        flash("Invalid or expired reset link.", "error")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("auth/reset_password.html", token=token)

        user.set_password(password)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        log_event("password_reset_completed", user_id=user.id)
        flash("Password updated. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token)
