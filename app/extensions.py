"""Shared Flask extension instances.

Created here (not in __init__.py) to avoid circular imports.
Each extension is initialized in create_app() via ext.init_app(app).
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
bcrypt = Bcrypt()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per minute"])
mail = Mail()

login_manager.login_view = "auth.login"
login_manager.login_message_category = "info"
