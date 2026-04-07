"""Email sending service for transactional emails.

Uses Flask-Mail for delivery. Falls back to logging if MAIL_USERNAME is not
configured (development / CI environments).
"""

import logging
from threading import Thread

from flask import current_app, render_template
from flask_mail import Message

from ..extensions import mail

log = logging.getLogger("nd.email")


def _send_async(app, msg):
    """Send a message inside an app context (called from a background thread)."""
    import sys
    with app.app_context():
        try:
            mail.send(msg)
            print(f"[Email] Sent to {msg.recipients}: {msg.subject}", flush=True, file=sys.stderr)
        except Exception as e:
            print(f"[Email] FAILED to {msg.recipients}: {e}", flush=True, file=sys.stderr)


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

    import sys
    if not app.config.get("MAIL_USERNAME"):
        print(f"[Email] SKIPPED (no MAIL_USERNAME): to={to} subject={subject}", flush=True, file=sys.stderr)
        return
    print(f"[Email] Preparing: to={to} subject={subject} server={app.config.get('MAIL_SERVER')}:{app.config.get('MAIL_PORT')}", flush=True, file=sys.stderr)

    recipients = [to] if isinstance(to, str) else to
    msg = Message(
        subject=f"Nickel&Dime - {subject}",
        recipients=recipients,
    )

    try:
        msg.html = render_template(f"{template}.html", **kwargs)
    except Exception:
        pass

    try:
        msg.body = render_template(f"{template}.txt", **kwargs)
    except Exception:
        if not msg.html:
            log.error("No template found for %s", template)
            return

    thread = Thread(target=_send_async, args=(app, msg))
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

    if not app.config.get("MAIL_USERNAME"):
        return "MAIL_USERNAME not configured"

    msg = Message(
        subject="Nickel&Dime - Reset Your Password",
        recipients=[user.email],
    )
    try:
        msg.html = render_template("email/reset_password.html", user=user, reset_url=reset_url)
    except Exception as e:
        return f"Template error: {e}"

    try:
        msg.body = render_template("email/reset_password.txt", user=user, reset_url=reset_url)
    except Exception:
        pass

    try:
        mail.send(msg)
        return None
    except Exception as e:
        return str(e)


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
