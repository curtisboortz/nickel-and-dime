"""WSGI entry point for production deployment."""

import os

# Force prod config unless explicitly overridden
if not os.environ.get("FLASK_ENV"):
    os.environ["FLASK_ENV"] = "prod"

from app import create_app

app = create_app()
print(f"[wsgi] App created with FLASK_ENV={os.environ.get('FLASK_ENV')}, DB={bool(app.config.get('SQLALCHEMY_DATABASE_URI'))}")
