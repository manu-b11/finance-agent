import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models.user import User
from app.schemas.savings_goal import (
    ContributionBody,
    ContributionCreate,
    GoalCreate,
    GoalProgressRead,
    GoalRead,
    GoalUpdate,
)
from app.services import savings_goal as goal_service

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=list[GoalProgressRead])
async def list_goals(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[GoalProgressRead]:
    return await goal_service.list_goals(session, current_user.id)


@router.post("", response_model=GoalProgressRead, status_code=status.HTTP_201_CREATED)
async def create_goal(
    payload: GoalCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GoalProgressRead:
    return await goal_service.create_goal(session, current_user.id, payload)


@router.patch("/{goal_id}", response_model=GoalProgressRead)
async def update_goal(
    goal_id: uuid.UUID,
    payload: GoalUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GoalProgressRead:
    return await goal_service.update_goal(session, current_user.id, goal_id, payload)


@router.delete("/{goal_id}", response_model=GoalRead)
async def delete_goal(
    goal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GoalRead:
    return await goal_service.delete_goal(session, current_user.id, goal_id)


@router.post(
    "/{goal_id}/contributions",
    response_model=GoalProgressRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_contribution(
    goal_id: uuid.UUID,
    payload: ContributionBody,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GoalProgressRead:
    data = ContributionCreate(
        goal_id=goal_id,
        amount=payload.amount,
        contributed_on=payload.contributed_on,
    )
    _, progress = await goal_service.add_contribution(session, current_user.id, data)
    return progress
