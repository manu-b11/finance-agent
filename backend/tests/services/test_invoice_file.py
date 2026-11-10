import io

import pymupdf
import pytest
from PIL import Image

from app.core.errors import InvalidFileError
from app.services import invoice_file


def image_bytes(fmt: str = "PNG", size=(300, 200), mode: str = "RGB") -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, size, "white").save(buffer, format=fmt)
    return buffer.getvalue()


def pdf_bytes(pages: int = 1, **save_kwargs) -> bytes:
    document = pymupdf.open()
    for number in range(pages):
        page = document.new_page()
        page.insert_text((72, 72), f"Factura pagina {number + 1}")
    data = document.tobytes(**save_kwargs)
    document.close()
    return data


@pytest.mark.parametrize(
    "fmt,name", [("PNG", "factura.png"), ("JPEG", "factura.jpg"), ("JPEG", "FACTURA.JPEG")]
)
def test_images_are_normalized_to_jpeg(fmt, name):
    parts = invoice_file.prepare_images(image_bytes(fmt), name)
    assert len(parts) == 1
    assert parts[0].mime_type == "image/jpeg"
    assert parts[0].data.startswith(b"\xff\xd8\xff")


def test_large_images_are_downscaled():
    parts = invoice_file.prepare_images(image_bytes("PNG", size=(4000, 3000)), "grande.png")
    with Image.open(io.BytesIO(parts[0].data)) as result:
        assert max(result.size) <= invoice_file.MAX_SIDE


def test_transparent_png_is_flattened_on_white():
    buffer = io.BytesIO()
    Image.new("RGBA", (50, 50), (0, 0, 0, 0)).save(buffer, format="PNG")
    parts = invoice_file.prepare_images(buffer.getvalue(), "t.png")
    with Image.open(io.BytesIO(parts[0].data)) as result:
        assert result.getpixel((10, 10))[0] > 240


def test_pdf_pages_are_rendered_as_png():
    parts = invoice_file.prepare_images(pdf_bytes(2), "factura.pdf")
    assert len(parts) == 2
    assert all(part.mime_type == "image/png" for part in parts)
    assert parts[0].data.startswith(b"\x89PNG")


def test_pdf_pages_are_capped(monkeypatch):
    monkeypatch.setattr(invoice_file.settings, "invoice_max_pdf_pages", 2)
    assert len(invoice_file.prepare_images(pdf_bytes(4), "f.pdf")) == 2


def test_filename_is_optional_when_content_is_valid():
    assert len(invoice_file.prepare_images(image_bytes("PNG"), None)) == 1


@pytest.mark.parametrize(
    "content,name",
    [
        (b"", "vacio.png"),
        (b"no soy una imagen", "a.png"),
        (b"GIF89a....", "a.gif"),
        (b"%PDF-1.4 roto", "roto.pdf"),
        (b"\x89PNG\r\n\x1a\nroto", "roto.png"),
        (b"\xff\xd8\xff\xe0roto", "roto.jpg"),
    ],
)
def test_invalid_or_corrupt_files_are_rejected(content, name):
    with pytest.raises(InvalidFileError):
        invoice_file.prepare_images(content, name)


def test_unsupported_extension_is_rejected():
    with pytest.raises(InvalidFileError):
        invoice_file.prepare_images(image_bytes("PNG"), "factura.gif")
    with pytest.raises(InvalidFileError):
        invoice_file.prepare_images(image_bytes("PNG"), "factura")


def test_extension_must_match_content():
    with pytest.raises(InvalidFileError):
        invoice_file.prepare_images(image_bytes("PNG"), "factura.pdf")
    with pytest.raises(InvalidFileError):
        invoice_file.prepare_images(pdf_bytes(), "factura.png")


def test_password_protected_pdf_is_rejected():
    protected = pdf_bytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secreto", owner_pw="secreto"
    )
    with pytest.raises(InvalidFileError) as error:
        invoice_file.prepare_images(protected, "protegido.pdf")
    assert "contraseña" in error.value.message
