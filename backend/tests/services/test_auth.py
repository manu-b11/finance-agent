import pytest

from app.core.errors import AuthenticationError, ConflictError
from app.schemas.user import UserCreate
from app.services import auth as auth_service


def make_data(email: str = "ana@example.com", password: str = "clave-segura-1") -> UserCreate:
    return UserCreate(email=email, password=password)


async def test_register_hashes_password_and_normalizes_email(session):
    user = await auth_service.register_user(session, make_data("Ana@Example.com"))
    assert user.email == "ana@example.com"
    assert user.password_hash != "clave-segura-1"
    assert user.timezone == "America/Bogota"


async def test_register_duplicate_email_raises_conflict(session):
    await auth_service.register_user(session, make_data())
    with pytest.raises(ConflictError):
        await auth_service.register_user(session, make_data("ANA@example.com"))


async def test_authenticate_with_valid_credentials(session):
    created = await auth_service.register_user(session, make_data())
    user = await auth_service.authenticate_user(session, "ana@example.com", "clave-segura-1")
    assert user.id == created.id


async def test_authenticate_with_wrong_password(session):
    await auth_service.register_user(session, make_data())
    with pytest.raises(AuthenticationError):
        await auth_service.authenticate_user(session, "ana@example.com", "otra-clave-1")


async def test_authenticate_unknown_email(session):
    with pytest.raises(AuthenticationError):
        await auth_service.authenticate_user(session, "nadie@example.com", "clave-segura-1")
