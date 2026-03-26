"""WSGI entry point for production deployment."""

import os
import sys

if not os.environ.get("FLASK_ENV"):
    os.environ["FLASK_ENV"] = "prod"

from app import create_app

app = create_app()
print(
    f"[wsgi] App created | ENV={os.environ.get('FLASK_ENV')} "
    f"DB={bool(app.config.get('SQLALCHEMY_DATABASE_URI'))} "
    f"SCHEDULER={'on' if os.environ.get('RUN_SCHEDULER') == '1' else 'off'}",
    flush=True,
)
