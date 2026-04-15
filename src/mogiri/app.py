"""Flask application entry point for `flask` CLI commands (e.g. flask db migrate).

This module is used only by the `flask` CLI. The `mogiri serve` command
uses create_app() directly.
"""

import os

from flask import Flask
from flask_migrate import Migrate

from mogiri.config import Config
from mogiri.models import db

migrate = Migrate()


def create_app():
    """Minimal app for flask CLI (no scheduler, no auto-upgrade)."""
    app = Flask(__name__)

    yaml_config = Config.from_yaml()
    app.config.update(yaml_config)

    data_dir = app.config.get("DATA_DIR", Config.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    project_root = os.path.abspath(os.path.join(app.root_path, "..", ".."))
    migrations_dir = os.path.join(project_root, "migrations")
    if os.path.isdir(migrations_dir):
        migrate.init_app(app, db, directory=migrations_dir)
    else:
        migrate.init_app(app, db)

    return app


app = create_app()
