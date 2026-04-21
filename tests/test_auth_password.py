import pytest

from mogiri import create_app


@pytest.fixture()
def pw_app(tmp_path):
    """App with password authentication enabled."""
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "DATA_DIR": tmp_path,
        "WTF_CSRF_ENABLED": False,
        "AUTH_ENABLED": False,
        "AUTH_PASSWORD": "secret123",
    })
    yield app


@pytest.fixture()
def pw_client(pw_app):
    return pw_app.test_client()


def test_web_ui_redirects_to_login(pw_client):
    """Unauthenticated requests to Web UI are redirected to login."""
    resp = pw_client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_login_page_renders(pw_client):
    resp = pw_client.get("/login")
    assert resp.status_code == 200
    assert b"Password" in resp.data


def test_login_wrong_password(pw_client):
    resp = pw_client.post("/login", data={"password": "wrong"})
    assert resp.status_code == 200
    assert b"incorrect" in resp.data


def test_login_correct_password(pw_client):
    resp = pw_client.post(
        "/login", data={"password": "secret123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    # After login, Web UI should be accessible
    resp2 = pw_client.get("/")
    assert resp2.status_code == 200


def test_logout(pw_client):
    # Login first
    pw_client.post("/login", data={"password": "secret123"})
    resp = pw_client.get("/")
    assert resp.status_code == 200

    # Logout
    pw_client.post("/logout")

    # Should redirect to login again
    resp = pw_client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_api_not_affected_by_password(pw_client):
    """API endpoints are not affected by password auth."""
    resp = pw_client.get("/api/jobs")
    assert resp.status_code == 200


def test_static_not_affected_by_password(pw_client):
    """Static files should be accessible without login."""
    resp = pw_client.get("/static/style.css")
    assert resp.status_code == 200


def test_no_password_no_login_required(tmp_path):
    """When password is not set, Web UI is freely accessible."""
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "DATA_DIR": tmp_path,
        "WTF_CSRF_ENABLED": False,
        "AUTH_ENABLED": False,
        "AUTH_PASSWORD": "",
    })
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
