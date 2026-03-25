"""Management script for Nickel&Dime.

Usage:
    python manage.py db init        # Initialize migrations directory
    python manage.py db migrate     # Generate migration from model changes
    python manage.py db upgrade     # Apply migrations to database
    python manage.py seed           # Import data from existing config.json / price_history.json
    python manage.py shell          # Interactive shell with app context
"""

import os
import sys
import click
from flask.cli import FlaskGroup

os.environ.setdefault("FLASK_ENV", "dev")

from app import create_app

app = create_app()


@app.cli.command("seed")
@click.option("--config-path", default="config.json", help="Path to config.json")
@click.option("--history-path", default="price_history.json", help="Path to price_history.json")
@click.option("--email", required=True, help="Email for the user account to seed into")
@click.option("--password", required=True, help="Password for the user account")
def seed_data(config_path, history_path, email, password):
    """Import existing flat-file data into the database for a user."""
    from scripts.migrate_data import migrate_all
    migrate_all(config_path, history_path, email, password)


if __name__ == "__main__":
    app.cli()
