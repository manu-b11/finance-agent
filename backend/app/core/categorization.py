import unicodedata

from app.models.transaction import ExpenseCategory

# Orden de prioridad: lo más específico primero. La primera coincidencia gana.
CATEGORY_KEYWORDS: tuple[tuple[ExpenseCategory, tuple[str, ...]], ...] = (
    (
        ExpenseCategory.BEAUTY,
        (
            "maquillaje",
            "labial",
            "pestanina",
            "pestana",
            "cosmetico",
            "belleza",
            "peluqueria",
            "corte de cabello",
            "cabello",
            "unas",
            "manicure",
            "pedicure",
            "perfume",
            "crema facial",
            "skincare",
        ),
    ),
    (
        ExpenseCategory.FOOD,
        (
            "mercado",
            "supermercado",
            "restaurante",
            "comida",
            "almuerzo",
            "cena",
            "desayuno",
            "pan",
            "leche",
            "cafe",
            "pizza",
            "hamburg",
            "salchipapa",
            "fruta",
            "verdura",
            "carne",
            "pollo",
            "arroz",
            "domicilio",
            "rappi",
        ),
    ),
    (
        ExpenseCategory.TRANSPORT,
        (
            "bus",
            "taxi",
            "uber",
            "didi",
            "metro",
            "gasolina",
            "combustible",
            "peaje",
            "parqueadero",
            "pasaje",
            "transporte",
            "moto",
        ),
    ),
    (
        ExpenseCategory.HEALTH,
        (
            "farmacia",
            "medico",
            "doctor",
            "hospital",
            "clinica",
            "medicina",
            "odontolog",
            "examen",
            "laboratorio",
            "terapia",
        ),
    ),
    (
        ExpenseCategory.EDUCATION,
        (
            "universidad",
            "colegio",
            "curso",
            "matricula",
            "libro",
            "cuaderno",
            "utiles",
            "educacion",
            "semestre",
        ),
    ),
    (
        ExpenseCategory.ENTERTAINMENT,
        (
            "cine",
            "concierto",
            "teatro",
            "videojuego",
            "juego",
            "bar",
            "discoteca",
            "salida",
        ),
    ),
    (
        ExpenseCategory.CLOTHING,
        (
            "ropa",
            "camisa",
            "pantalon",
            "zapato",
            "tenis",
            "sudadera",
            "chaqueta",
            "vestido",
            "falda",
            "blusa",
            "medias",
        ),
    ),
    (
        ExpenseCategory.HOME,
        (
            "mueble",
            "sofa",
            "cama",
            "almohada",
            "cortina",
            "aseo",
            "limpieza",
            "detergente",
            "escoba",
            "olla",
            "sarten",
            "bombillo",
        ),
    ),
    (
        ExpenseCategory.PETS,
        ("mascota", "perro", "gato", "veterinaria", "arena", "concentrado"),
    ),
    (ExpenseCategory.GIFTS, ("regalo", "obsequio", "cumpleanos", "flores")),
    (ExpenseCategory.TRAVEL, ("vuelo", "hotel", "viaje", "turismo", "airbnb", "maleta")),
    (
        ExpenseCategory.SUBSCRIPTIONS,
        ("netflix", "spotify", "disney", "hbo", "suscripcion", "youtube premium", "prime"),
    ),
    (
        ExpenseCategory.SPORTS,
        ("gimnasio", "gym", "deporte", "futbol", "bicicleta", "natacion", "yoga", "pesas"),
    ),
    (
        ExpenseCategory.TECHNOLOGY,
        (
            "celular",
            "computador",
            "laptop",
            "tablet",
            "audifono",
            "tecnologia",
            "cargador",
            "monitor",
            "teclado",
            "mouse",
            "software",
        ),
    ),
    (ExpenseCategory.INSURANCE, ("seguro", "poliza", "soat")),
    (ExpenseCategory.TAXES, ("impuesto", "predial", "renta", "dian", "declaracion")),
    (ExpenseCategory.HOUSING, ("arriendo", "alquiler", "hipoteca", "vivienda", "administracion")),
    (
        ExpenseCategory.UTILITIES,
        ("luz", "agua", "gas", "internet", "telefono", "energia", "alcantarillado"),
    ),
)


def _normalize(text: str) -> str:
    lowered = text.lower().strip()
    return "".join(
        char for char in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(char)
    )


def infer_category(concept: str) -> ExpenseCategory:
    """Deduce la categoría de un gasto por su concepto; si no, usa 'otros'."""
    text = _normalize(concept)
    for category, keywords in CATEGORY_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return category
    return ExpenseCategory.OTHER
