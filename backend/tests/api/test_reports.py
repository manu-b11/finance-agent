import io

import pymupdf

PAYLOAD = {"email": "ana@example.com", "password": "clave-segura-1"}
OTHER = {"email": "beto@example.com", "password": "clave-segura-1"}


async def auth_headers(client, payload=PAYLOAD) -> dict[str, str]:
    await client.post("/auth/register", json=payload)
    response = await client.post("/auth/login", json=payload)
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def add_transaction(client, headers, **fields):
    body = {"concept": "Movimiento", "occurred_on": "2026-11-05", **fields}
    return await client.post("/transactions", json=body, headers=headers)


def pdf_text(content: bytes) -> str:
    document = pymupdf.open(stream=io.BytesIO(content).read(), filetype="pdf")
    try:
        return "".join(page.get_text() for page in document)
    finally:
        document.close()


async def seed_via_service(client, session, headers):
    import uuid

    from app.tools import transactions as tools

    user_id = uuid.UUID((await client.get("/auth/me", headers=headers)).json()["id"])
    await tools.add_transaction(
        session,
        user_id,
        {"type": "income", "amount": 3000, "concept": "Salario", "occurred_on": "2026-11-01"},
    )
    await tools.add_transaction(
        session,
        user_id,
        {
            "type": "expense",
            "amount": 400,
            "concept": "Mercado",
            "occurred_on": "2026-11-05",
            "category": "alimentacion",
        },
    )


async def test_reports_require_authentication(client):
    assert (await client.get("/reports/monthly/2026-11")).status_code == 401
    assert (await client.get("/reports/monthly/2026-11/pdf")).status_code == 401


async def test_monthly_report_json(client, session):
    headers = await auth_headers(client)
    await seed_via_service(client, session, headers)
    response = await client.get("/reports/monthly/2026-11", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_income"] == "3000.00"
    assert body["total_expenses"] == "400.00"
    assert body["balance"] == "2600.00"
    assert body["categories"][0]["label"] == "Alimentación"
    assert body["top_category"] == "alimentacion"
    assert body["expense_count"] == 1
    assert [expense["concept"] for expense in body["expenses"]] == ["Mercado"]


async def test_monthly_report_pdf_download(client, session):
    headers = await auth_headers(client)
    await seed_via_service(client, session, headers)
    response = await client.get("/reports/monthly/2026-11/pdf", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="informe-financiero-2026-11.pdf"'
    )
    assert response.content.startswith(b"%PDF")
    text = pdf_text(response.content)
    assert "Noviembre de 2026" in text
    assert "$3.000" in text
    assert "Alimentación" in text
    assert "Gastos del mes" in text
    assert "Mercado" in text


async def test_pdf_only_contains_the_authenticated_users_data(client, session):
    ana = await auth_headers(client)
    beto = await auth_headers(client, OTHER)
    await seed_via_service(client, session, ana)
    response = await client.get("/reports/monthly/2026-11/pdf", headers=beto)
    assert response.status_code == 200
    text = pdf_text(response.content)
    assert "$3.000" not in text
    assert "Alimentación" not in text
    assert "No hay gastos registrados en este periodo." in text


async def test_invalid_month_returns_422(client):
    headers = await auth_headers(client)
    for month in ("2026-13", "26-11", "noviembre"):
        assert (await client.get(f"/reports/monthly/{month}", headers=headers)).status_code == 422
        assert (
            await client.get(f"/reports/monthly/{month}/pdf", headers=headers)
        ).status_code == 422


async def test_empty_month_still_generates_pdf(client):
    headers = await auth_headers(client)
    response = await client.get("/reports/monthly/2026-01/pdf", headers=headers)
    assert response.status_code == 200
    assert "No hay gastos registrados en este periodo." in pdf_text(response.content)
