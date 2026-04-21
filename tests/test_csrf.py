import re

import pytest

from mogiri import create_app


@pytest.fixture()
def csrf_app(tmp_path):
    """App with CSRF enabled for testing CSRF behavior."""
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "DATA_DIR": tmp_path,
        "WTF_CSRF_ENABLED": True,
        "SECRET_KEY": "test-secret",
    })
    yield app


@pytest.fixture()
def csrf_client(csrf_app):
    return csrf_app.test_client()


def _extract_csrf_token(html):
    match = re.search(r'name="csrf-token" content="([^"]+)"', html)
    assert match, "CSRF meta tag not found in page"
    return match.group(1)


def test_csrf_rejects_post_without_token(csrf_client):
    """POST to a Web UI endpoint without CSRF token should be rejected."""
    response = csrf_client.post("/settings/", data={
        "ai_provider": "claude",
    })
    assert response.status_code == 400


def test_csrf_allows_post_with_token(csrf_client):
    """POST with a valid CSRF token should succeed."""
    resp = csrf_client.get("/settings/")
    token = _extract_csrf_token(resp.data.decode())

    response = csrf_client.post("/settings/", data={
        "ai_provider": "claude",
    }, headers={"X-CSRFToken": token})
    assert response.status_code in (200, 302)


def test_csrf_allows_api_without_token(csrf_client):
    """API endpoints are exempt from CSRF — should succeed without token."""
    response = csrf_client.post("/api/jobs", json={
        "name": "test", "command": "echo hi",
    })
    assert response.status_code == 201
