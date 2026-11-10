import base64
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.services import push as service
from app.services.push import DeliveryResult, SubscriptionInfo
from scripts.generate_vapid_keys import generate


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class PushServer:
    def __init__(self, status: int):
        outer = self
        self.status = status
        self.requests: list[dict] = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                outer.requests.append({"headers": dict(self.headers), "body": body, "path": self.path})
                self.send_response(outer.status)
                self.end_headers()

            def log_message(self, *args):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}/push/device-1"


@pytest.fixture
def vapid(monkeypatch):
    public, private = generate()
    monkeypatch.setattr(service.settings, "vapid_private_key", private)
    monkeypatch.setattr(service.settings, "vapid_public_key", public)
    monkeypatch.setattr(service.settings, "vapid_subject", "mailto:tests@example.com")
    return public


def make_subscription(url: str) -> SubscriptionInfo:
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return SubscriptionInfo(endpoint=url, p256dh=b64url(public), auth=b64url(os.urandom(16)))


async def test_delivered_push_is_encrypted_and_signed_with_vapid(vapid):
    with PushServer(201) as server:
        result = await service.web_push_sender(make_subscription(server.url), json.dumps({"title": "Hola"}))
    assert result == DeliveryResult.DELIVERED
    request = server.requests[0]
    headers = {key.lower(): value for key, value in request["headers"].items()}
    assert headers["content-encoding"] == "aes128gcm"
    assert headers["authorization"].lower().startswith("vapid ")
    assert vapid in headers["authorization"]
    assert headers["ttl"] == str(service.PUSH_TTL_SECONDS)
    assert b"Hola" not in request["body"]
    assert len(request["body"]) > 0


@pytest.mark.parametrize("status,expected", [(404, DeliveryResult.GONE), (410, DeliveryResult.GONE), (500, DeliveryResult.FAILED), (429, DeliveryResult.FAILED), (401, DeliveryResult.FAILED)])
async def test_push_service_errors_are_classified(vapid, status, expected):
    with PushServer(status) as server:
        result = await service.web_push_sender(make_subscription(server.url), "{}")
    assert result == expected


async def test_unreachable_push_service_is_a_transient_failure(vapid):
    subscription = make_subscription("http://127.0.0.1:9/push/none")
    assert await service.web_push_sender(subscription, "{}") == DeliveryResult.FAILED


async def test_missing_vapid_configuration_fails_without_raising(monkeypatch):
    monkeypatch.setattr(service.settings, "vapid_private_key", "")
    assert await service.web_push_sender(make_subscription("http://127.0.0.1:9/x"), "{}") == DeliveryResult.FAILED


async def test_malformed_subscription_keys_fail_without_raising(vapid):
    broken = SubscriptionInfo(endpoint="http://127.0.0.1:9/x", p256dh="no-es-una-llave", auth="x")
    assert await service.web_push_sender(broken, "{}") == DeliveryResult.FAILED
