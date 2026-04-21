import pytest

from mogiri import create_app


@pytest.fixture()
def auth_app(tmp_path):
    """App with API auth enabled."""
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "DATA_DIR": tmp_path,
        "WTF_CSRF_ENABLED": False,
        "AUTH_ENABLED": True,
        "API_TOKEN": "test-secret-token",
    })
    yield app


@pytest.fixture()
def auth_client(auth_app):
    return auth_app.test_client()


def test_api_rejects_without_token(auth_client):
    resp = auth_client.get("/api/jobs")
    assert resp.status_code == 401
    assert "Authentication required" in resp.get_json()["error"]


def test_api_rejects_wrong_token(auth_client):
    resp = auth_client.get("/api/jobs", headers={"Authorization": "Bearer wrong-token"})
    assert resp.status_code == 401


def test_api_accepts_correct_token(auth_client):
    headers = {"Authorization": "Bearer test-secret-token"}
    resp = auth_client.get("/api/jobs", headers=headers)
    assert resp.status_code == 200


def test_api_post_with_token(auth_client):
    resp = auth_client.post("/api/jobs", json={
        "name": "test", "command": "echo hi",
    }, headers={"Authorization": "Bearer test-secret-token"})
    assert resp.status_code == 201


def test_web_ui_not_affected_by_api_auth(auth_client):
    """Web UI routes should not require API token."""
    resp = auth_client.get("/jobs/")
    assert resp.status_code == 200


def test_api_auth_disabled_allows_all(tmp_path):
    """When auth.enabled is false, API requests succeed without token."""
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "DATA_DIR": tmp_path,
        "WTF_CSRF_ENABLED": False,
        "AUTH_ENABLED": False,
    })
    client = app.test_client()
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
