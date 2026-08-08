"""Auth endpoint tests — registration, login, /me, rate limiting."""
import pytest

from tests.conftest import REDIS_AVAILABLE, auth_headers


def test_register_success(test_client):
    response = test_client.post("/api/v1/auth/register", json={
        "email": "newuser@example.com",
        "password": "Password1",
        "full_name": "New User",
        "role": "analyst",
    })
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "newuser@example.com"
    assert body["role"] == "analyst"
    assert "id" in body
    assert "password" not in body and "hashed_password" not in body


def test_register_duplicate_email(test_client):
    payload = {
        "email": "dupe@example.com",
        "password": "Password1",
        "role": "analyst",
    }
    first = test_client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    second = test_client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


def test_login_success(test_client):
    test_client.post("/api/v1/auth/register", json={
        "email": "login@example.com",
        "password": "Password1",
        "role": "analyst",
    })
    response = test_client.post("/api/v1/auth/login", json={
        "email": "login@example.com",
        "password": "Password1",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "login@example.com"


def test_login_wrong_password(test_client):
    test_client.post("/api/v1/auth/register", json={
        "email": "wrongpass@example.com",
        "password": "Password1",
        "role": "analyst",
    })
    response = test_client.post("/api/v1/auth/login", json={
        "email": "wrongpass@example.com",
        "password": "Incorrect9",
    })
    assert response.status_code == 401  # not 404, not 403


def test_login_wrong_email(test_client):
    response = test_client.post("/api/v1/auth/login", json={
        "email": "nosuchuser@example.com",
        "password": "Password1",
    })
    # Same 401 as wrong password — anti account-enumeration
    assert response.status_code == 401


def test_get_me_authenticated(test_client, analyst_token):
    response = test_client.get("/api/v1/auth/me", headers=auth_headers(analyst_token))
    assert response.status_code == 200
    assert response.json()["email"] == "analyst@example.com"


def test_get_me_unauthenticated(test_client):
    response = test_client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Rate limiter requires Redis")
def test_rate_limit_login(test_client):
    from app.core.rate_limiter import limiter

    limiter.enabled = True
    try:
        payload = {"email": "ratelimit@example.com", "password": "Password1"}
        statuses = [
            test_client.post("/api/v1/auth/login", json=payload).status_code
            for _ in range(6)
        ]
        # 5/minute limit → the 6th attempt in quick succession is rejected
        assert statuses[-1] == 429
    finally:
        limiter.enabled = False
