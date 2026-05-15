"""Failure-path coverage: 403/404/409/422 + DB error envelope."""

from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient

OTHER_EMAIL = "other@example.com"
OTHER_PASSWORD = "anotherpass123"


@pytest_asyncio.fixture
async def other_auth_headers(client: AsyncClient) -> dict[str, str]:
    """A *second* registered user, used for cross-user authorization tests."""
    await client.post(
        "/api/auth/signup",
        json={
            "email": OTHER_EMAIL,
            "password": OTHER_PASSWORD,
            "full_name": "Other",
        },
    )
    resp = await client.post(
        "/api/auth/login",
        data={"username": OTHER_EMAIL, "password": OTHER_PASSWORD},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_project(
    client: AsyncClient, headers: dict[str, str]
) -> dict[str, Any]:
    resp = await client.post(
        "/api/projects",
        headers=headers,
        json={"name": "P", "description": None},
    )
    assert resp.status_code == 201
    return resp.json()


# ── 401 ──────────────────────────────────────────────────────────────────────
async def test_projects_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/projects")
    assert resp.status_code == 401


async def test_analytics_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/analytics")
    assert resp.status_code == 401


async def test_invalid_token_is_401(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/projects",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert resp.status_code == 401


# ── 403 ──────────────────────────────────────────────────────────────────────
async def test_cannot_access_other_users_project(
    client: AsyncClient,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
) -> None:
    project = await _create_project(client, auth_headers)

    resp = await client.get(
        f"/api/projects/{project['id']}", headers=other_auth_headers
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == 403


async def test_cannot_create_task_in_other_users_project(
    client: AsyncClient,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
) -> None:
    project = await _create_project(client, auth_headers)

    resp = await client.post(
        "/api/tasks",
        headers=other_auth_headers,
        json={"title": "intruder", "project_id": project["id"]},
    )
    assert resp.status_code == 403


# ── 404 ──────────────────────────────────────────────────────────────────────
async def test_get_missing_project_is_404(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.get(
        "/api/projects/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == 404


async def test_get_missing_task_is_404(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.get(
        "/api/tasks/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── 409 ──────────────────────────────────────────────────────────────────────
async def test_duplicate_signup_returns_409_envelope(client: AsyncClient) -> None:
    payload = {
        "email": "dupcheck@example.com",
        "password": "validpass123",
        "full_name": "X",
    }
    first = await client.post("/api/auth/signup", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/auth/signup", json=payload)
    assert second.status_code == 409
    body = second.json()
    assert body["error"]["code"] == 409
    assert "exists" in body["error"]["message"].lower()


# ── 422 ──────────────────────────────────────────────────────────────────────
async def test_signup_password_too_short_is_422(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/signup",
        json={"email": "short@example.com", "password": "abc", "full_name": "x"},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == 422
    assert "details" in body["error"]


async def test_signup_invalid_email_is_422(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/signup",
        json={
            "email": "not-an-email",
            "password": "validpass123",
            "full_name": "x",
        },
    )
    assert resp.status_code == 422


# ── 500 (DB error envelope) ──────────────────────────────────────────────────
async def test_db_error_returns_generic_500_envelope(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy.exc import OperationalError

    from app.services import project_service as ps_module

    class ExplodingRepo:
        def __init__(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("simulated DB outage"))

    monkeypatch.setattr(ps_module, "ProjectRepository", ExplodingRepo)

    resp = await client.get("/api/projects", headers=auth_headers)
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == 500
    # The handler must NOT leak the underlying SQLAlchemy message.
    assert "simulated DB outage" not in body["error"]["message"]
    assert "SELECT 1" not in body["error"]["message"]


# ── Quote-client fallback (covered via update -> completed) ──────────────────
async def test_completion_quote_uses_fallback_when_external_fails(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    from app.integrations import quote_client as qc_module

    async def boom(*_args, **_kwargs):
        raise httpx.ConnectError("offline")

    # Patch the network call inside the integration module.
    monkeypatch.setattr(
        qc_module.httpx, "AsyncClient", lambda *a, **k: _FailingClient(boom)
    )

    project = await _create_project(client, auth_headers)
    create = await client.post(
        "/api/tasks",
        headers=auth_headers,
        json={"title": "to complete", "project_id": project["id"]},
    )
    task_id = create.json()["id"]

    resp = await client.patch(
        f"/api/tasks/{task_id}",
        headers=auth_headers,
        json={"status": "completed"},
    )
    # The request itself must succeed even though the external API failed.
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


class _FailingClient:
    """Minimal async context manager that fails on .get()."""

    def __init__(self, get_impl):
        self._get = get_impl

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, *args, **kwargs):
        return await self._get(*args, **kwargs)
