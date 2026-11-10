import io
from decimal import Decimal

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.report import CategoryTotal, MonthlyReportRead

MONTH_NAMES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
CHART_COLORS = (
    "#2563eb",
    "#16a34a",
    "#f59e0b",
    "#dc2626",
    "#7c3aed",
    "#0891b2",
    "#db2777",
    "#65a30d",
    "#6b7280",
    "#ea580c",
)
DISCLAIMER = (
    "Informe generado con los movimientos registrados por el usuario. "
    "La información es de carácter informativo y no constituye asesoría financiera profesional."
)
INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#6b7280")
LINE = colors.HexColor("#e5e7eb")
HEADER_BG = colors.HexColor("#f3f4f6")


def format_money(value: Decimal) -> str:
    sign = "-" if value < 0 else ""
    cents = abs(value).quantize(Decimal("0.01"))
    integer, fraction = f"{cents:.2f}".split(".")
    grouped = f"{int(integer):,}".replace(",", ".")
    suffix = "" if fraction == "00" else f",{fraction}"
    return f"{sign}${grouped}{suffix}"


def format_percentage(value: Decimal) -> str:
    return f"{value:.2f}".replace(".", ",") + " %"


def month_title(report: MonthlyReportRead) -> str:
    return f"{MONTH_NAMES[report.start_date.month - 1].capitalize()} de {report.start_date.year}"


def _chart(categories: list[CategoryTotal]) -> io.BytesIO:
    figure = Figure(figsize=(6.4, 3.4), dpi=150)
    FigureCanvasAgg(figure)
    axes = figure.add_subplot(111)
    values = [float(item.total) for item in categories]
    palette = [CHART_COLORS[index % len(CHART_COLORS)] for index in range(len(categories))]
    axes.pie(
        values,
        colors=palette,
        startangle=90,
        counterclock=False,
        wedgeprops={"linewidth": 1, "edgecolor": "white"},
    )
    axes.legend(
        [f"{item.label} ({format_percentage(item.percentage)})" for item in categories],
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        frameon=False,
        fontsize=9,
    )
    axes.set_aspect("equal")
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", bbox_inches="tight")
    buffer.seek(0)
    return buffer


def _summary_table(report: MonthlyReportRead, styles: dict[str, ParagraphStyle]) -> Table:
    balance_color = colors.HexColor("#16a34a") if report.balance >= 0 else colors.HexColor("#dc2626")
    rows = [
        ["Ingresos", format_money(report.total_income)],
        ["Gastos", format_money(report.total_expenses)],
        ["Balance", format_money(report.balance)],
    ]
    table = Table(rows, colWidths=[9 * cm, 7 * cm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
                ("TEXTCOLOR", (1, 2), (1, 2), balance_color),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE),
                ("LINEABOVE", (0, 2), (-1, 2), 1, INK),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _category_table(categories: list[CategoryTotal]) -> Table:
    rows = [["Categoría", "Total", "% del gasto"]]
    rows.extend(
        [item.label, format_money(item.total), format_percentage(item.percentage)]
        for item in categories
    )
    table = Table(rows, colWidths=[8 * cm, 4.5 * cm, 3.5 * cm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def render_monthly_report(report: MonthlyReportRead) -> bytes:
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("title", parent=base["Title"], textColor=INK, alignment=0, fontSize=22),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], textColor=MUTED, fontSize=11),
        "heading": ParagraphStyle(
            "heading", parent=base["Heading2"], textColor=INK, fontSize=14, spaceBefore=18, spaceAfter=8
        ),
        "body": ParagraphStyle("body", parent=base["Normal"], textColor=INK, fontSize=10, leading=14),
        "note": ParagraphStyle("note", parent=base["Normal"], textColor=MUTED, fontSize=8, leading=11),
    }
    story = [
        Paragraph("Informe financiero mensual", styles["title"]),
        Paragraph(
            f"{month_title(report)} · Periodo del {report.start_date.isoformat()} "
            f"al {report.end_date.isoformat()}",
            styles["subtitle"],
        ),
        Spacer(1, 14),
        Paragraph("Resumen", styles["heading"]),
        _summary_table(report, styles),
        Spacer(1, 6),
        Paragraph(f"Movimientos registrados en el periodo: {report.transaction_count}", styles["note"]),
        Paragraph("Distribución de gastos por categoría", styles["heading"]),
    ]
    if report.categories:
        story.append(Image(_chart(report.categories), width=14 * cm, height=7 * cm, kind="proportional"))
        story.append(Spacer(1, 8))
        story.append(_category_table(report.categories))
        top = report.categories[0]
        story.append(Spacer(1, 8))
        story.append(
            Paragraph(
                f"La categoría con mayor gasto fue {top.label}: {format_money(top.total)} "
                f"({format_percentage(top.percentage)} de los gastos).",
                styles["body"],
            )
        )
    else:
        story.append(Paragraph("No hay gastos registrados en este periodo.", styles["body"]))
    story.append(Spacer(1, 16))
    story.append(
        Paragraph(f"{DISCLAIMER}<br/>Generado el {report.generated_on.isoformat()}.", styles["note"])
    )

    buffer = io.BytesIO()
    SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2.2 * cm,
        rightMargin=2.2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"Informe financiero {report.month}",
        author="Agente de Finanzas Personales",
    ).build(story)
    return buffer.getvalue()
