from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_session
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserRead
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, session: AsyncSession = Depends(get_session)) -> User:
    return await auth_service.register_user(session, data)


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    user = await auth_service.authenticate_user(session, data.email, data.password)
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
