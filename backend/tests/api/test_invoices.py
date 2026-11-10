import io
import json

import pymupdf
from PIL import Image

from app.api.deps import get_chat_fn
from app.main import app
from tests.agent.fakes import FakeChat, text_response

PAYLOAD = {"email": "ana@example.com", "password": "clave-segura-1"}
OTHER = {"email": "beto@example.com", "password": "clave-segura-1"}

EXTRACTION = {
    "readable": True,
    "merchant": "Supermercado Éxito",
    "invoice_number": "FE-1023",
    "date": "2026-11-05",
    "items": [{"description": "Leche", "quantity": 2, "unit_price": 4500}],
    "total": 9000,
    "category": "alimentacion",
}


async def auth_headers(client, payload=PAYLOAD) -> dict[str, str]:
    await client.post("/auth/register", json=payload)
    response = await client.post("/auth/login", json=payload)
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (200, 300), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def pdf() -> bytes:
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "Factura")
    data = document.tobytes()
    document.close()
    return data


def use_chat(fake) -> None:
    app.dependency_overrides[get_chat_fn] = lambda: fake


def upload(client, headers, content: bytes, name: str, mime: str):
    return client.post("/invoices", files={"file": (name, content, mime)}, headers=headers)


async def test_upload_requires_authentication(client):
    response = await client.post("/invoices", files={"file": ("f.png", png(), "image/png")})
    assert response.status_code == 401


async def test_upload_png_returns_draft_and_sends_image_to_model(client):
    headers = await auth_headers(client)
    fake = FakeChat(text_response(json.dumps(EXTRACTION)))
    use_chat(fake)
    response = await upload(client, headers, png(), "factura.png", "image/png")
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["merchant"] == "Supermercado Éxito"
    assert body["total"] == "9000.00"
    assert body["items"][0]["line_total"] == "9000.00"
    assert body["missing_fields"] == []
    assert body["transaction_id"] is None
    images = fake.calls[0][0][1].images
    assert len(images) == 1 and images[0].mime_type == "image/jpeg"


async def test_upload_pdf_is_supported(client):
    headers = await auth_headers(client)
    use_chat(FakeChat(text_response(json.dumps(EXTRACTION))))
    response = await upload(client, headers, pdf(), "factura.pdf", "application/pdf")
    assert response.status_code == 201


async def test_upload_reports_missing_data_instead_of_failing(client):
    headers = await auth_headers(client)
    use_chat(FakeChat(text_response(json.dumps({"merchant": "Tienda", "total": 5000}))))
    response = await upload(client, headers, png(), "f.png", "image/png")
    assert response.status_code == 201
    assert response.json()["missing_fields"] == ["issued_on", "category"]


async def test_upload_invalid_file_returns_415_and_never_calls_model(client):
    headers = await auth_headers(client)
    fake = FakeChat()
    use_chat(fake)
    response = await upload(client, headers, b"hola", "nota.txt", "text/plain")
    assert response.status_code == 415
    assert response.json()["code"] == "invalid_file"
    assert fake.calls == []


async def test_upload_oversized_file_is_rejected(client, monkeypatch):
    from app.services import invoice as invoice_service

    monkeypatch.setattr(invoice_service.settings, "invoice_max_bytes", 100)
    monkeypatch.setattr("app.api.invoices.settings.invoice_max_bytes", 100)
    headers = await auth_headers(client)
    use_chat(FakeChat())
    response = await upload(client, headers, png(), "f.png", "image/png")
    assert response.status_code == 415
    assert "tamaño" in response.json()["message"]


async def test_unreadable_invoice_returns_422(client):
    headers = await auth_headers(client)
    use_chat(FakeChat(text_response(json.dumps({"readable": False}))))
    response = await upload(client, headers, png(), "f.png", "image/png")
    assert response.status_code == 422
    assert response.json()["code"] == "incomplete_information"
    listed = await client.get("/invoices/00000000-0000-0000-0000-000000000000", headers=headers)
    assert listed.status_code == 404


async def test_garbled_model_output_returns_500_processing_error(client):
    headers = await auth_headers(client)
    use_chat(FakeChat(text_response("no puedo ayudarte con eso")))
    response = await upload(client, headers, png(), "f.png", "image/png")
    assert response.status_code == 500
    assert response.json()["code"] == "processing_error"


async def test_get_invoice_is_scoped_to_its_owner(client):
    ana = await auth_headers(client)
    beto = await auth_headers(client, OTHER)
    use_chat(FakeChat(text_response(json.dumps(EXTRACTION))))
    created = (await upload(client, ana, png(), "f.png", "image/png")).json()
    own = await client.get(f"/invoices/{created['id']}", headers=ana)
    assert own.status_code == 200
    assert own.json()["merchant"] == "Supermercado Éxito"
    other = await client.get(f"/invoices/{created['id']}", headers=beto)
    assert other.status_code == 404
    anonymous = await client.get(f"/invoices/{created['id']}")
    assert anonymous.status_code == 401
