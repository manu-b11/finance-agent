import io
import os

import pymupdf
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings
from app.core.errors import InvalidFileError
from app.core.media import ImagePart

EXTENSION_KINDS = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".pdf": "pdf"}
MAX_SIDE = 2000
MAX_PIXELS = 50_000_000
UNSUPPORTED = "Solo se aceptan archivos JPG, JPEG, PNG o PDF."


def _detect_kind(content: bytes) -> str | None:
    if content.startswith(b"%PDF"):
        return "pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    return None


def _normalize_image(content: bytes) -> ImagePart:
    try:
        with Image.open(io.BytesIO(content)) as source:
            if source.width * source.height > MAX_PIXELS:
                raise InvalidFileError("La imagen es demasiado grande.")
            image = ImageOps.exif_transpose(source)
            if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.split()[-1])
                image = background
            else:
                image = image.convert("RGB")
            image.thumbnail((MAX_SIDE, MAX_SIDE))
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=85)
    except InvalidFileError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise InvalidFileError("La imagen está dañada o no se puede leer.") from exc
    return ImagePart(mime_type="image/jpeg", data=output.getvalue())


def _render_pdf(content: bytes) -> list[ImagePart]:
    try:
        document = pymupdf.open(stream=content, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        raise InvalidFileError("El PDF está dañado o no se puede leer.") from exc
    try:
        if document.needs_pass:
            raise InvalidFileError("El PDF está protegido con contraseña.")
        if document.page_count == 0:
            raise InvalidFileError("El PDF no tiene páginas.")
        images: list[ImagePart] = []
        for index in range(min(document.page_count, settings.invoice_max_pdf_pages)):
            page = document[index]
            longest = max(page.rect.width, page.rect.height)
            zoom = min(2.0, MAX_SIDE / longest) if longest else 1.0
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            images.append(ImagePart(mime_type="image/png", data=pixmap.tobytes("png")))
        return images
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        raise InvalidFileError("El PDF está dañado o no se puede leer.") from exc
    finally:
        document.close()


def prepare_images(content: bytes, filename: str | None) -> list[ImagePart]:
    if not content:
        raise InvalidFileError("El archivo está vacío.")
    kind = _detect_kind(content)
    if kind is None:
        raise InvalidFileError(UNSUPPORTED)
    if filename:
        expected = EXTENSION_KINDS.get(os.path.splitext(filename.lower())[1])
        if expected is None:
            raise InvalidFileError(UNSUPPORTED)
        if expected != kind:
            raise InvalidFileError("La extensión del archivo no coincide con su contenido.")
    if kind == "pdf":
        return _render_pdf(content)
    return [_normalize_image(content)]
