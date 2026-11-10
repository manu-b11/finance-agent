import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import llm_client
from app.agent.llm_client import ChatFn
from app.core.database import get_session
from app.core.errors import AuthenticationError
from app.core.security import decode_access_token
from app.models.user import User
from app.services import auth as auth_service
from app.services import push as push_service

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None:
        raise AuthenticationError("Falta el token de autenticación.")
    subject = decode_access_token(credentials.credentials)
    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise AuthenticationError("Token inválido o expirado.") from exc
    user = await auth_service.get_user_by_id(session, user_id)
    if user is None:
        raise AuthenticationError("Token inválido o expirado.")
    return user


def get_chat_fn() -> ChatFn:
    return llm_client.chat


def get_push_sender() -> push_service.PushSender:
    return push_service.web_push_sender
