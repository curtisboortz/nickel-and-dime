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
    with app.app_context():
        try:
            mail.send(msg)
            log.info("Email sent to %s: %s", msg.recipients, msg.subject)
        except Exception as e:
            log.error("Failed to send email to %s: %s", msg.recipients, e)


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

    if not app.config.get("MAIL_USERNAME"):
        log.warning("MAIL_USERNAME not set; email to %s skipped (subject: %s)", to, subject)
        return

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
    """Send a password reset email."""
    from flask import url_for
    reset_url = url_for("auth.reset_password", token=token, _external=True)
    send_email(
        to=user.email,
        subject="Reset Your Password",
        template="email/reset_password",
        user=user,
        reset_url=reset_url,
    )


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
