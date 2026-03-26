"""Flask configuration classes loaded from environment variables."""

import os


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get("FLASK_SECRET", "dev-secret-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Stripe
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRO_PRICE_ID = os.environ.get("STRIPE_PRO_PRICE_ID", "")

    # External API keys
    FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

    # Mail (for email verification / password reset)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@nickeldime.io")

    # Rate limiting
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")


class DevConfig(Config):
    """Local development."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "nickeldime_dev.db",
        ),
    )


class ProdConfig(Config):
    """Production (Railway / Render / etc.)."""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "")

    @staticmethod
    def init_app(app):
        # Railway uses postgres:// but SQLAlchemy needs postgresql://
        uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if uri.startswith("postgres://"):
            app.config["SQLALCHEMY_DATABASE_URI"] = uri.replace(
                "postgres://", "postgresql://", 1
            )


class TestConfig(Config):
    """Automated tests."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


config_by_name = {
    "dev": DevConfig,
    "prod": ProdConfig,
    "test": TestConfig,
}
