from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pymupdf
import pytest

from app.schemas.report import CategoryTotal, MonthlyReportRead
from app.schemas.transaction import TransactionRead
from app.services import report_pdf


def make_report(**overrides) -> MonthlyReportRead:
    data = {
        "month": "2026-11",
        "start_date": date(2026, 11, 1),
        "end_date": date(2026, 11, 30),
        "total_income": Decimal("5500.50"),
        "total_expenses": Decimal("1000.00"),
        "balance": Decimal("4500.50"),
        "transaction_count": 6,
        "categories": [
            CategoryTotal(
                category="alimentacion",
                label="Alimentación",
                total=Decimal("800.00"),
                percentage=Decimal("80.00"),
            ),
            CategoryTotal(
                category="transporte",
                label="Transporte",
                total=Decimal("200.00"),
                percentage=Decimal("20.00"),
            ),
        ],
        "top_category": "alimentacion",
        "generated_on": date(2026, 11, 8),
    }
    data.update(overrides)
    return MonthlyReportRead(**data)


def read_pdf(content: bytes) -> tuple[str, int, int]:
    document = pymupdf.open(stream=content, filetype="pdf")
    try:
        text = "".join(page.get_text() for page in document)
        images = sum(len(page.get_images()) for page in document)
        return text, document.page_count, images
    finally:
        document.close()


def test_pdf_contains_period_totals_and_category_distribution():
    content = report_pdf.render_monthly_report(make_report())
    assert content.startswith(b"%PDF")
    text, pages, images = read_pdf(content)
    assert pages == 1
    assert images >= 1
    assert "Informe financiero mensual" in text
    assert "Noviembre de 2026" in text
    assert "2026-11-01" in text and "2026-11-30" in text
    assert "$5.500,50" in text
    assert "$1.000" in text
    assert "$4.500,50" in text
    assert "Alimentación" in text and "Transporte" in text
    assert "80,00 %" in text
    assert "no constituye asesoría financiera profesional" in " ".join(text.split())


def test_pdf_lists_individual_expenses():
    expense = TransactionRead(
        id=uuid4(),
        type="expense",
        amount=Decimal("120.50"),
        concept="Corte de cabello",
        category="belleza",
        occurred_on=date(2026, 11, 10),
        created_at=datetime(2026, 11, 10, 12, 0, tzinfo=UTC),
    )
    content = report_pdf.render_monthly_report(
        make_report(expenses=[expense], expense_count=1)
    )
    text, _, _ = read_pdf(content)
    assert "Gastos del mes" in text
    assert "Corte de cabello" in text
    assert "Belleza" in text
    assert "$120,50" in text


def test_pdf_for_month_without_expenses_has_no_chart_and_says_so():
    report = make_report(
        total_income=Decimal("0"),
        total_expenses=Decimal("0"),
        balance=Decimal("0"),
        transaction_count=0,
        categories=[],
        top_category=None,
    )
    text, pages, images = read_pdf(report_pdf.render_monthly_report(report))
    assert pages == 1
    assert images == 0
    assert "No hay gastos registrados en este periodo." in text


def test_pdf_with_six_categories_fits_one_page():
    categories = [
        CategoryTotal(
            category=f"c{index}",
            label=f"Categoría {index}",
            total=Decimal(100 - index),
            percentage=Decimal("16.67"),
        )
        for index in range(6)
    ]
    text, pages, _ = read_pdf(report_pdf.render_monthly_report(make_report(categories=categories)))
    assert pages == 1
    assert "Generado el 2026-11-08." in text


def test_pdf_with_many_categories_renders():
    categories = [
        CategoryTotal(
            category=f"c{index}",
            label=f"Categoría {index}",
            total=Decimal(100 - index),
            percentage=Decimal("10.00"),
        )
        for index in range(10)
    ]
    text, _, images = read_pdf(report_pdf.render_monthly_report(make_report(categories=categories)))
    assert images >= 1
    assert "Categoría 9" in text


@pytest.mark.parametrize(
    "value,expected",
    [
        (Decimal("0"), "$0"),
        (Decimal("1234567"), "$1.234.567"),
        (Decimal("12200.50"), "$12.200,50"),
        (Decimal("999.99"), "$999,99"),
        (Decimal("-150"), "-$150"),
        (Decimal("-1234.5"), "-$1.234,50"),
    ],
)
def test_money_format(value, expected):
    assert report_pdf.format_money(value) == expected


def test_percentage_format_and_month_title():
    assert report_pdf.format_percentage(Decimal("15.03")) == "15,03 %"
    assert report_pdf.month_title(make_report(start_date=date(2027, 3, 1))) == "Marzo de 2027"
