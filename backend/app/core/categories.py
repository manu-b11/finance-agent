from app.models.transaction import ExpenseCategory

UNCATEGORIZED = "sin_categoria"

# Etiquetas visibles para el usuario. Se comparten entre informes, PDF y tarjetas.
CATEGORY_LABELS = {
    ExpenseCategory.FOOD.value: "Alimentación",
    ExpenseCategory.TRANSPORT.value: "Transporte",
    ExpenseCategory.HOUSING.value: "Vivienda",
    ExpenseCategory.UTILITIES.value: "Servicios",
    ExpenseCategory.HEALTH.value: "Salud",
    ExpenseCategory.EDUCATION.value: "Educación",
    ExpenseCategory.ENTERTAINMENT.value: "Entretenimiento",
    ExpenseCategory.CLOTHING.value: "Ropa",
    ExpenseCategory.BEAUTY.value: "Belleza",
    ExpenseCategory.HOME.value: "Hogar",
    ExpenseCategory.PETS.value: "Mascotas",
    ExpenseCategory.GIFTS.value: "Regalos",
    ExpenseCategory.TRAVEL.value: "Viajes",
    ExpenseCategory.SUBSCRIPTIONS.value: "Suscripciones",
    ExpenseCategory.SPORTS.value: "Deporte",
    ExpenseCategory.TECHNOLOGY.value: "Tecnología",
    ExpenseCategory.INSURANCE.value: "Seguros",
    ExpenseCategory.TAXES.value: "Impuestos",
    ExpenseCategory.OTHER.value: "Otros",
    UNCATEGORIZED: "Sin categoría",
}


def category_label(value: str | None) -> str:
    if not value:
        return CATEGORY_LABELS[UNCATEGORIZED]
    return CATEGORY_LABELS.get(value, value.capitalize())
