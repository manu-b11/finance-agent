import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.savings_goal import (
    ContributionCreate,
    ContributionRead,
    GoalCreate,
    GoalListQuery,
    GoalRef,
    GoalUpdate,
)
from app.services import savings_goal as goal_service


async def create_savings_goal(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    args = GoalCreate.model_validate(raw_args)
    progress = await goal_service.create_goal(session, user_id, args)
    return progress.model_dump(mode="json")


async def update_savings_goal(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    changes = dict(raw_args)
    ref = GoalRef.model_validate({"goal_id": changes.pop("goal_id", None)})
    data = GoalUpdate.model_validate(changes)
    progress = await goal_service.update_goal(session, user_id, ref.goal_id, data)
    return progress.model_dump(mode="json")


async def delete_savings_goal(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    ref = GoalRef.model_validate(raw_args)
    deleted = await goal_service.delete_goal(session, user_id, ref.goal_id)
    return {"deleted": True, "goal": deleted.model_dump(mode="json")}


async def list_savings_goals(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    GoalListQuery.model_validate(raw_args)
    goals = await goal_service.list_goals(session, user_id)
    items = [goal.model_dump(mode="json") for goal in goals]
    return {"count": len(items), "goals": items}


async def add_goal_contribution(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    args = ContributionCreate.model_validate(raw_args)
    contribution, progress = await goal_service.add_contribution(session, user_id, args)
    return {
        "contribution": ContributionRead.model_validate(contribution).model_dump(mode="json"),
        "progress": progress.model_dump(mode="json"),
    }
