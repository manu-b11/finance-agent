import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationError, ConflictError
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == normalize_email(email)))
    return result.scalar_one_or_none()


async def register_user(session: AsyncSession, data: UserCreate) -> User:
    if await get_user_by_email(session, data.email) is not None:
        raise ConflictError("Ya existe una cuenta con ese correo.")
    user = User(
        email=normalize_email(data.email),
        name=data.name,
        password_hash=hash_password(data.password),
        timezone=data.timezone,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("Ya existe una cuenta con ese correo.") from exc
    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError("Correo o contraseña incorrectos.")
    return user
