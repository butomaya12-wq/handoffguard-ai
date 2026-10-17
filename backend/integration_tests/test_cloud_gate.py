"""Security tests for the public-demo perimeter, without external services."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.cloud import COOKIE_NAME, create_cloud_app


ROLE_TOKENS = {
    "ci-cloud-" + role + "-" + ("x" * 32): {"role": role, "id": "ci-" + role}
    for role in ("sales", "production", "approver")
}
ACCESS_KEY = "ci-access-key-" + "a" * 40
COOKIE_SECRET = "ci-cookie-secret-" + "b" * 40


@pytest.fixture
def cloud_env(monkeypatch):
    monkeypatch.setenv("HANDOFFGUARD_DEMO_ACCESS_KEY", ACCESS_KEY)
    monkeypatch.setenv("HANDOFFGUARD_DEMO_COOKIE_SECRET", COOKIE_SECRET)
    monkeypatch.setenv("HANDOFFGUARD_AUTH_TOKENS", json.dumps(ROLE_TOKENS))


@pytest.fixture
def cloud_client(tmp_path, cloud_env):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>SAFE_TEST_REACT_ROOT</html>")
    with TestClient(
        create_cloud_app(
            static_directory=dist,
            _testing_database_url=f"sqlite:///{tmp_path / 'isolated-cloud-test.db'}",
        ),
        base_url="https://testserver",
        follow_redirects=False,
    ) as client:
        yield client


def test_reviewer_gate_is_strict_even_when_role_bearer_token_is_known(cloud_client):
    bearer = {"Authorization": f"Bearer {next(iter(ROLE_TOKENS))}"}
    assert cloud_client.get("/").status_code == 302
    assert cloud_client.get("/").headers["location"] == "/demo/login"
    assert cloud_client.get("/demo/login").status_code == 200
    assert cloud_client.get("/health").status_code == 200
    # Knowing one API role token must never bypass the outer reviewer cookie.
    blocked = cloud_client.get("/api/v1/orders/nonexistent", headers=bearer)
    assert blocked.status_code == 401
    assert blocked.json()["detail"] == "Reviewer access required"
    assert cloud_client.get("/openapi.json").status_code == 401
    assert cloud_client.get("/docs").status_code == 401
    assert cloud_client.get("/", cookies={COOKIE_NAME: "forged-cookie"}).status_code == 302


def test_reviewer_login_cookie_then_server_role_authorization(cloud_client):
    bad_login = cloud_client.post("/demo/login", data={"access_key": "wrong"})
    assert bad_login.status_code == 401
    assert COOKIE_NAME not in bad_login.headers.get("set-cookie", "")

    login = cloud_client.post("/demo/login", data={"access_key": ACCESS_KEY})
    assert login.status_code == 303, login.text
    cookie_header = login.headers["set-cookie"].lower()
    assert COOKIE_NAME in cookie_header
    assert "httponly" in cookie_header
    assert "secure" in cookie_header
    assert "samesite=lax" in cookie_header

    frontend = cloud_client.get("/")
    assert frontend.status_code == 200, frontend.text
    assert "SAFE_TEST_REACT_ROOT" in frontend.text

    # Reviewer access alone does not authorize business API calls.
    assert cloud_client.get("/api/v1/orders/not-found").status_code == 401
    sales = next(k for k, v in ROLE_TOKENS.items() if v["role"] == "sales")
    api = cloud_client.get("/api/v1/orders/not-found",
                           headers={"Authorization": f"Bearer {sales}"})
    assert api.status_code == 404, api.text

    logout = cloud_client.post("/demo/logout")
    assert logout.status_code == 303
    assert cloud_client.get("/").status_code == 302
    assert cloud_client.get("/api/v1/orders/not-found",
                            headers={"Authorization": f"Bearer {sales}"}).status_code == 401


def test_bruteforce_rejection_is_bounded(cloud_client):
    for _ in range(10):
        assert cloud_client.post("/demo/login", data={"access_key": "bad"}).status_code == 401
    assert cloud_client.post("/demo/login", data={"access_key": ACCESS_KEY}).status_code == 429


def test_cloud_startup_rejects_sqlite_and_missing_secure_config(tmp_path, cloud_env, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("safe fake build")
    monkeypatch.setenv("HANDOFFGUARD_DATABASE_URL", "sqlite:////data/test.db")
    with pytest.raises(RuntimeError, match="managed PostgreSQL"):
        create_cloud_app(static_directory=dist)

    # Even with a valid PG driver URL, a missing reviewer gate fails closed.
    monkeypatch.setenv(
        "HANDOFFGUARD_DATABASE_URL",
        "postgresql+psycopg://test:test@127.0.0.1:5432/nonexistent",
    )
    monkeypatch.delenv("HANDOFFGUARD_DEMO_COOKIE_SECRET")
    with pytest.raises(RuntimeError, match="secure demo access secrets"):
        create_cloud_app(static_directory=dist)
