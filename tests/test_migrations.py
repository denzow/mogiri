"""Test that all migrations apply cleanly from scratch."""

from alembic import command
from flask_migrate import Migrate


def test_migrations_upgrade_from_scratch(tmp_path):
    """Run all migrations from empty DB to head — catches NOT NULL, bad SQL, etc."""
    from flask import Flask

    from mogiri.models import db

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path / 'test.db'}"
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"timeout": 30}}

    db.init_app(app)
    migrate = Migrate(app, db)

    with app.app_context():
        config = migrate.get_config("migrations")
        # Run upgrade to head — this will fail if any migration has issues
        command.upgrade(config, "head")

        # Verify tables exist
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())
        assert "jobs" in tables
        assert "executions" in tables
        assert "workflows" in tables
        assert "workflow_edges" in tables
        assert "workflow_node_positions" in tables


def test_migrations_downgrade_to_base(tmp_path):
    """Upgrade to head then downgrade to base — catches bad downgrade SQL."""
    from flask import Flask

    from mogiri.models import db

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path / 'test.db'}"
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"timeout": 30}}

    db.init_app(app)
    migrate = Migrate(app, db)

    with app.app_context():
        config = migrate.get_config("migrations")
        command.upgrade(config, "head")
        command.downgrade(config, "base")

        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names()) - {"alembic_version"}
        assert len(tables) == 0, f"Tables remaining after downgrade: {tables}"
