PAYLOAD = {"email": "ana@example.com", "password": "clave-segura-1"}


async def register(client, payload=PAYLOAD):
    return await client.post("/auth/register", json=payload)


async def login_token(client) -> str:
    response = await client.post("/auth/login", json=PAYLOAD)
    return response.json()["access_token"]


async def test_register_returns_user_without_password(client):
    response = await register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ana@example.com"
    assert "password" not in body
    assert "password_hash" not in body


async def test_register_duplicate_returns_409(client):
    await register(client)
    response = await register(client)
    assert response.status_code == 409
    assert response.json()["code"] == "conflict"


async def test_register_short_password_returns_422(client):
    response = await register(client, {"email": "ana@example.com", "password": "corta"})
    assert response.status_code == 422


async def test_register_invalid_timezone_returns_422(client):
    response = await register(client, {**PAYLOAD, "timezone": "Marte/Olimpo"})
    assert response.status_code == 422


async def test_login_returns_token(client):
    await register(client)
    response = await client.post("/auth/login", json=PAYLOAD)
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"


async def test_login_wrong_password_returns_401(client):
    await register(client)
    response = await client.post("/auth/login", json={**PAYLOAD, "password": "incorrecta-1"})
    assert response.status_code == 401


async def test_me_with_token(client):
    await register(client)
    token = await login_token(client)
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "ana@example.com"


async def test_me_without_token_returns_401(client):
    response = await client.get("/auth/me")
    assert response.status_code == 401


async def test_me_with_invalid_token_returns_401(client):
    response = await client.get("/auth/me", headers={"Authorization": "Bearer token-falso"})
    assert response.status_code == 401
