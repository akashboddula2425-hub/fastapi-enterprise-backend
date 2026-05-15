from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict[str, str]) -> str:
    resp = await client.post(
        "/api/projects",
        headers=headers,
        json={"name": "Test Project", "description": "for task tests"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_create_task(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    project_id = await _create_project(client, auth_headers)

    resp = await client.post(
        "/api/tasks",
        headers=auth_headers,
        json={
            "title": "First task",
            "description": "do the thing",
            "status": "pending",
            "priority": "high",
            "project_id": project_id,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "First task"
    assert body["status"] == "pending"
    assert body["priority"] == "high"
    assert body["project_id"] == project_id
    assert "id" in body


async def test_list_tasks_returns_created_task(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    project_id = await _create_project(client, auth_headers)

    create = await client.post(
        "/api/tasks",
        headers=auth_headers,
        json={
            "title": "Findable task",
            "priority": "medium",
            "project_id": project_id,
        },
    )
    assert create.status_code == 201
    created_id = create.json()["id"]

    resp = await client.get("/api/tasks", headers=auth_headers)
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()]
    assert created_id in ids


async def test_list_tasks_filters_by_status_and_priority(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    project_id = await _create_project(client, auth_headers)

    for title, status_val, priority_val in [
        ("A", "pending", "high"),
        ("B", "pending", "low"),
        ("C", "completed", "high"),
    ]:
        r = await client.post(
            "/api/tasks",
            headers=auth_headers,
            json={
                "title": title,
                "status": status_val,
                "priority": priority_val,
                "project_id": project_id,
            },
        )
        assert r.status_code == 201

    resp = await client.get(
        "/api/tasks?status=pending&priority=high",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()]
    assert titles == ["A"]


async def test_tasks_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/tasks")
    assert resp.status_code == 401
