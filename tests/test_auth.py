from httpx import AsyncClient


async def test_signup_success(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/signup",
        json={
            "email": "new@example.com",
            "password": "validpass123",
            "full_name": "New User",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@example.com"
    assert body["full_name"] == "New User"
    assert "id" in body
    assert "hashed_password" not in body


async def test_signup_duplicate_email(client: AsyncClient) -> None:
    payload = {
        "email": "dup@example.com",
        "password": "validpass123",
        "full_name": "Dup",
    }
    first = await client.post("/api/auth/signup", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/auth/signup", json=payload)
    assert second.status_code == 409
    assert "error" in second.json()


async def test_login_success(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/signup",
        json={
            "email": "login@example.com",
            "password": "validpass123",
            "full_name": "Login",
        },
    )

    resp = await client.post(
        "/api/auth/login",
        data={"username": "login@example.com", "password": "validpass123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 0


async def test_login_bad_password(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/signup",
        json={
            "email": "badpw@example.com",
            "password": "validpass123",
            "full_name": "Bad Pw",
        },
    )

    resp = await client.post(
        "/api/auth/login",
        data={"username": "badpw@example.com", "password": "wrongpass"},
    )
    assert resp.status_code == 401
