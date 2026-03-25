"""WSGI entry point for production deployment."""

import os
os.environ.setdefault("FLASK_ENV", "prod")

from app import create_app

app = create_app()
