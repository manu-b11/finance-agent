from app.api.deps import get_push_sender
from app.core.config import settings
from app.main import app
from tests.services.fakes import FakePushSender

PAYLOAD = {"email": "ana@example.com", "password": "clave-segura-1"}
OTHER = {"email": "beto@example.com", "password": "clave-segura-1"}
SUBSCRIPTION = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
    "expirationTime": None,
    "keys": {"p256dh": "BPubKey", "auth": "authSecret"},
}


async def auth_headers(client, payload=PAYLOAD) -> dict[str, str]:
    await client.post("/auth/register", json=payload)
    response = await client.post("/auth/login", json=payload)
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_push_endpoints_require_authentication(client):
    assert (await client.get("/push/public-key")).status_code == 401
    assert (await client.post("/push/subscriptions", json=SUBSCRIPTION)).status_code == 401
    assert (await client.request("DELETE", "/push/subscriptions", json={"endpoint": SUBSCRIPTION["endpoint"]})).status_code == 401
    assert (await client.post("/push/test")).status_code == 401


async def test_public_key_is_served_when_configured(client, monkeypatch):
    headers = await auth_headers(client)
    monkeypatch.setattr(settings, "vapid_public_key", "BClaveVAPID")
    response = await client.get("/push/public-key", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"public_key": "BClaveVAPID"}


async def test_public_key_reports_missing_configuration(client, monkeypatch):
    headers = await auth_headers(client)
    monkeypatch.setattr(settings, "vapid_public_key", "")
    response = await client.get("/push/public-key", headers=headers)
    assert response.status_code == 500
    assert "no están configuradas" in response.json()["message"]


async def test_subscribe_accepts_the_browser_subscription_shape(client):
    headers = await auth_headers(client)
    response = await client.post("/push/subscriptions", json=SUBSCRIPTION, headers=headers)
    assert response.status_code == 201
    assert response.json()["endpoint"] == SUBSCRIPTION["endpoint"]
    again = await client.post("/push/subscriptions", json=SUBSCRIPTION, headers=headers)
    assert again.status_code == 201
    assert again.json()["id"] == response.json()["id"]


async def test_subscribe_validates_the_payload(client):
    headers = await auth_headers(client)
    for body in (
        {**SUBSCRIPTION, "endpoint": "http://insecure.example/x"},
        {**SUBSCRIPTION, "endpoint": "https://x"},
        {"endpoint": SUBSCRIPTION["endpoint"]},
        {"endpoint": SUBSCRIPTION["endpoint"], "keys": {"p256dh": "k"}},
        {"endpoint": SUBSCRIPTION["endpoint"], "keys": {"p256dh": "", "auth": "a"}},
    ):
        assert (await client.post("/push/subscriptions", json=body, headers=headers)).status_code == 422


async def test_unsubscribe_removes_only_the_callers_subscription(client):
    ana = await auth_headers(client)
    beto = await auth_headers(client, OTHER)
    await client.post("/push/subscriptions", json=SUBSCRIPTION, headers=ana)
    body = {"endpoint": SUBSCRIPTION["endpoint"]}
    foreign = await client.request("DELETE", "/push/subscriptions", json=body, headers=beto)
    assert foreign.status_code == 204
    app.dependency_overrides[get_push_sender] = lambda: FakePushSender()
    assert (await client.post("/push/test", headers=ana)).status_code == 200
    own = await client.request("DELETE", "/push/subscriptions", json=body, headers=ana)
    assert own.status_code == 204
    assert (await client.post("/push/test", headers=ana)).status_code == 404


async def test_test_notification_reports_delivery_counts(client):
    headers = await auth_headers(client)
    await client.post("/push/subscriptions", json=SUBSCRIPTION, headers=headers)
    fake = FakePushSender()
    app.dependency_overrides[get_push_sender] = lambda: fake
    response = await client.post("/push/test", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"delivered": 1, "failed": 0, "gone": 0}
    assert fake.calls[0][0].endpoint == SUBSCRIPTION["endpoint"]
    assert fake.calls[0][1]["tag"] == "push-test"


async def test_test_notification_without_devices_returns_404(client):
    headers = await auth_headers(client)
    app.dependency_overrides[get_push_sender] = lambda: FakePushSender()
    response = await client.post("/push/test", headers=headers)
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_a_subscription_is_only_reachable_by_its_current_owner(client):
    ana = await auth_headers(client)
    beto = await auth_headers(client, OTHER)
    await client.post("/push/subscriptions", json=SUBSCRIPTION, headers=ana)
    await client.post("/push/subscriptions", json=SUBSCRIPTION, headers=beto)
    fake = FakePushSender()
    app.dependency_overrides[get_push_sender] = lambda: fake
    assert (await client.post("/push/test", headers=ana)).status_code == 404
    assert (await client.post("/push/test", headers=beto)).status_code == 200
