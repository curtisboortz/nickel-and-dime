"""Authentication routes: register, login, logout, password reset, email verification."""

import secrets
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from ..extensions import db, bcrypt, limiter
from ..models.user import User, Subscription
from ..models.settings import UserSettings

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

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
            return render_template("auth/register.html")

        user = User(email=email, name=name or email.split("@")[0], plan="pro")
        user.set_password(password)

        verify_token = secrets.token_urlsafe(32)
        user.verify_token = verify_token

        db.session.add(user)

        settings = UserSettings(user=user)
        db.session.add(settings)

        trial_end = datetime.now(timezone.utc) + timedelta(days=14)
        sub = Subscription(
            user=user, plan="pro", status="trialing",
            current_period_end=trial_end,
        )
        db.session.add(sub)

        db.session.commit()

        from ..services.email_service import send_email_verification
        send_email_verification(user, verify_token)

        login_user(user)
        flash(
            "Welcome! Your 14-day Pro trial is active. "
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

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            login_user(user, remember=remember)
            next_page = request.args.get("next")
            if next_page:
                parsed = urlparse(next_page)
                if parsed.netloc or parsed.scheme:
                    next_page = None
            return redirect(next_page or url_for("pages.dashboard_page"))

        flash("Invalid email or password.", "error")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("pages.landing"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def forgot_password():
    import sys
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        print(f"[ForgotPW] Lookup email: {email}", flush=True, file=sys.stderr)
        user = User.query.filter_by(email=email).first()
        print(f"[ForgotPW] User found: {user is not None}", flush=True, file=sys.stderr)
        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
            db.session.commit()

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
        flash("Password updated. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token)
