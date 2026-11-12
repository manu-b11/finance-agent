from decimal import Decimal

CENTS = Decimal("0.01")


def format_cop(value: Decimal | str | int) -> str:
    """Formatea un valor como pesos colombianos: 40000 → $40.000."""
    cents = Decimal(value).quantize(CENTS)
    sign = "-" if cents < 0 else ""
    integer, fraction = f"{abs(cents):.2f}".split(".")
    grouped = f"{int(integer):,}".replace(",", ".")
    suffix = "" if fraction == "00" else f",{fraction}"
    return f"{sign}${grouped}{suffix}"
