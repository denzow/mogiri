import pytest

from mogiri import create_app
from mogiri.models import db as _db
from mogiri import scheduler as _scheduler_module


@pytest.fixture()
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
            "DATA_DIR": tmp_path,
        }
    )
    # Set app reference for execute_job to use in tests
    _scheduler_module._app = app
    yield app
    _scheduler_module._app = None


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    with app.app_context():
        yield _db
