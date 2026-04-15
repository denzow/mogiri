import atexit
import json

from flask import Flask

from mogiri.config import Config
from mogiri.models import db
from mogiri.routes import register_routes
from mogiri.scheduler import init_scheduler, shutdown_scheduler


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

    db.init_app(app)

    with app.app_context():
        db.create_all()

    app.jinja_env.filters["from_json"] = json.loads

    register_routes(app)

    if not app.config.get("TESTING"):
        init_scheduler(app)
        atexit.register(shutdown_scheduler)

    return app
