import atexit
import json
import os

from flask import Flask
from flask_migrate import Migrate, upgrade
from flask_wtf.csrf import CSRFProtect

from mogiri.config import Config, ensure_api_token
from mogiri.models import db
from mogiri.routes import register_routes
from mogiri.scheduler import init_scheduler, shutdown_scheduler

migrate = Migrate()
csrf = CSRFProtect()


def _get_migrations_dir(app):
    """Return the migrations directory path, or None if it doesn't exist."""
    # Walk up from src/mogiri/ to project root
    project_root = os.path.abspath(os.path.join(app.root_path, "..", ".."))
    d = os.path.join(project_root, "migrations")
    return d if os.path.isdir(d) else None


def create_app(config=None, config_path=None):
    app = Flask(__name__)

    # Load YAML config merged with defaults and env vars
    yaml_config = Config.from_yaml(config_path)
    app.config.update(yaml_config)

    # Override with explicit config (e.g. tests)
    if config:
        app.config.update(config)

    # Ensure data directory exists
    data_dir = app.config.get("DATA_DIR", Config.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)

    if app.config.get("AUTH_ENABLED", True) and not app.config.get("TESTING"):
        app.config["API_TOKEN"] = ensure_api_token(data_dir)

    db.init_app(app)

    migrations_dir = _get_migrations_dir(app)
    if migrations_dir:
        migrate.init_app(app, db, directory=migrations_dir)

    with app.app_context():
        if migrations_dir and not app.config.get("TESTING"):
            # Apply pending migrations (creates tables if needed)
            upgrade(directory=migrations_dir)
        else:
            # Tests or no migrations dir — create tables directly from models
            db.create_all()

    app.jinja_env.filters["from_json"] = json.loads

    register_routes(app)

    csrf.init_app(app)
    from mogiri.routes.api import bp as api_bp
    csrf.exempt(api_bp)

    if not app.config.get("TESTING"):
        init_scheduler(app)
        atexit.register(shutdown_scheduler)

    return app
