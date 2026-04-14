"""hCaptcha server-side verification."""

import logging

import requests
from flask import current_app

log = logging.getLogger(__name__)

VERIFY_URL = "https://api.hcaptcha.com/siteverify"


def captcha_enabled() -> bool:
    return bool(
        current_app.config.get("HCAPTCHA_SITE_KEY")
        and current_app.config.get("HCAPTCHA_SECRET_KEY")
    )


def verify_captcha(response_token: str) -> bool:
    """Verify an hCaptcha response token. Returns True if valid or if captcha is disabled."""
    if not captcha_enabled():
        return True

    if not response_token:
        return False

    try:
        resp = requests.post(
            VERIFY_URL,
            data={
                "secret": current_app.config["HCAPTCHA_SECRET_KEY"],
                "response": response_token,
            },
            timeout=10,
        )
        return resp.json().get("success", False)
    except Exception:
        log.exception("hCaptcha verification request failed")
        return False
