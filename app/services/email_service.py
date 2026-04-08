"""Email sending service for transactional emails.

Uses Resend HTTP API for delivery. Falls back to logging if MAIL_PASSWORD
(Resend API key) is not configured.
"""

import json
import logging
import sys
import urllib.request
import urllib.error
from threading import Thread

from flask import current_app, render_template

log = logging.getLogger("nd.email")


def _send_via_resend(api_key, from_addr, to, subject, html_body, text_body=None):
    """Send an email via Resend's HTTP API. Returns None on success or error string."""
    import re as _re
    match = _re.search(r'<([^>]+)>', from_addr)
    clean_email = match.group(1) if match else from_addr
    clean_from = f"Nickel&Dime <{clean_email}>"

    payload = {
        "from": clean_from,
        "to": [to] if isinstance(to, str) else to,
        "subject": subject,
    }
    if html_body:
        payload["html"] = html_body
    if text_body:
        payload["text"] = text_body

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "NickelAndDime/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return None
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()
        except Exception:
            body = ""
        return f"Resend HTTP {e.code}: {body}"
    except Exception as e:
        return f"Resend error: {e}"


def send_email(to, subject, template, **kwargs):
    """Send an email asynchronously using a background thread.

    Args:
        to: Recipient email address (or list of addresses).
        subject: Email subject line.
        template: Template path prefix (e.g. 'email/reset_password').
                  Renders both .html and .txt versions.
        **kwargs: Context variables passed to the templates.
    """
    app = current_app._get_current_object()
    api_key = app.config.get("MAIL_PASSWORD", "")
    from_addr = app.config.get("MAIL_DEFAULT_SENDER", "noreply@nickelanddime.io")

    if not api_key:
        print(f"[Email] SKIPPED (no MAIL_PASSWORD/API key): to={to} subject={subject}", flush=True, file=sys.stderr)
        return

    full_subject = f"Nickel&Dime - {subject}"
    html_body = None
    text_body = None

    try:
        html_body = render_template(f"{template}.html", **kwargs)
    except Exception:
        pass
    try:
        text_body = render_template(f"{template}.txt", **kwargs)
    except Exception:
        pass

    if not html_body and not text_body:
        print(f"[Email] No template found for {template}", flush=True, file=sys.stderr)
        return

    def _send():
        with app.app_context():
            err = _send_via_resend(api_key, from_addr, to, full_subject, html_body, text_body)
            if err:
                print(f"[Email] FAILED to {to}: {err}", flush=True, file=sys.stderr)
            else:
                print(f"[Email] Sent to {to}: {full_subject}", flush=True, file=sys.stderr)

    thread = Thread(target=_send)
    thread.daemon = True
    thread.start()


def send_password_reset(user, token):
    """Send a password reset email (async)."""
    from flask import url_for
    reset_url = url_for("auth.reset_password", token=token, _external=True)
    send_email(
        to=user.email,
        subject="Reset Your Password",
        template="email/reset_password",
        user=user,
        reset_url=reset_url,
    )


def send_password_reset_sync(user, token):
    """Send a password reset email synchronously. Returns error string or None."""
    from flask import url_for, current_app
    reset_url = url_for("auth.reset_password", token=token, _external=True)
    app = current_app._get_current_object()
    api_key = app.config.get("MAIL_PASSWORD", "")
    from_addr = app.config.get("MAIL_DEFAULT_SENDER", "noreply@nickelanddime.io")

    if not api_key:
        return "MAIL_PASSWORD (Resend API key) not configured"

    try:
        html_body = render_template("email/reset_password.html", user=user, reset_url=reset_url)
    except Exception as e:
        return f"Template error: {e}"

    text_body = None
    try:
        text_body = render_template("email/reset_password.txt", user=user, reset_url=reset_url)
    except Exception:
        pass

    return _send_via_resend(api_key, from_addr, user.email, "Nickel&Dime - Reset Your Password", html_body, text_body)


def send_email_verification(user, token):
    """Send an email verification email."""
    from flask import url_for
    verify_url = url_for("auth.verify_email", token=token, _external=True)
    send_email(
        to=user.email,
        subject="Verify Your Email",
        template="email/verify_email",
        user=user,
        verify_url=verify_url,
    )


def send_trial_ending(user, days_left):
    """Send a trial-ending reminder."""
    send_email(
        to=user.email,
        subject=f"Your Pro Trial Ends in {days_left} Day{'s' if days_left != 1 else ''}",
        template="email/trial_ending",
        user=user,
        days_left=days_left,
    )


def send_welcome(user):
    """Day-0 welcome email with onboarding tips."""
    send_email(
        to=user.email,
        subject="Welcome to Nickel & Dime",
        template="email/welcome",
        user=user,
    )


def send_feature_highlight(user):
    """Day-7 email highlighting features the user may have missed."""
    send_email(
        to=user.email,
        subject="Features You Might Have Missed",
        template="email/feature_highlight",
        user=user,
    )


def send_referral_prompt(user):
    """Day-14 email encouraging referral sharing."""
    send_email(
        to=user.email,
        subject="Give a Month, Get a Month Free",
        template="email/referral_prompt",
        user=user,
    )


def send_renewal_reminder(user):
    """Pre-renewal reminder for active subscribers."""
    send_email(
        to=user.email,
        subject="Your Pro Subscription Renews Soon",
        template="email/renewal_reminder",
        user=user,
    )
