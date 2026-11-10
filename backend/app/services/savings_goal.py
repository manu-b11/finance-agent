import uuid
from datetime import date
from decimal import ROUND_HALF_UP, ROUND_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import local_today
from app.core.errors import NotFoundError
from app.models.savings_goal import SavingsContribution, SavingsGoal
from app.schemas.savings_goal import (
    ContributionCreate,
    GoalCreate,
    GoalProgressRead,
    GoalRead,
    GoalUpdate,
)
from app.services import auth as auth_service

CENTS = Decimal("0.01")


async def _today(session: AsyncSession, user_id: uuid.UUID) -> date:
    user = await auth_service.get_user_by_id(session, user_id)
    if user is None:
        raise NotFoundError("No se encontró el usuario.")
    return local_today(user.timezone)


async def _get_owned(
    session: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID
) -> SavingsGoal:
    result = await session.execute(
        select(SavingsGoal).where(SavingsGoal.id == goal_id, SavingsGoal.user_id == user_id)
    )
    goal = result.scalar_one_or_none()
    if goal is None:
        raise NotFoundError("No se encontró esa meta de ahorro.")
    return goal


async def _accumulated_by_goal(
    session: AsyncSession, user_id: uuid.UUID, goal_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Decimal]:
    if not goal_ids:
        return {}
    result = await session.execute(
        select(SavingsContribution.goal_id, func.sum(SavingsContribution.amount))
        .where(
            SavingsContribution.user_id == user_id,
            SavingsContribution.goal_id.in_(goal_ids),
        )
        .group_by(SavingsContribution.goal_id)
    )
    return {goal_id: Decimal(total) for goal_id, total in result.all()}


def build_progress(goal: SavingsGoal, accumulated: Decimal, today: date) -> GoalProgressRead:
    """Monto ahorrado, saldo pendiente y porcentaje (RF-30, RB-13)."""
    target = Decimal(goal.target_amount).quantize(CENTS)
    accumulated = accumulated.quantize(CENTS)
    remaining = max(target - accumulated, Decimal("0")).quantize(CENTS)
    percentage = (accumulated / target * 100).quantize(CENTS, rounding=ROUND_HALF_UP)
    completed = accumulated >= target
    days_remaining: int | None = None
    suggested: Decimal | None = None
    if goal.deadline is not None:
        days_remaining = (goal.deadline - today).days
        if not completed and days_remaining >= 0:
            months_left = max(1, (days_remaining + 29) // 30)
            suggested = (remaining / months_left).quantize(CENTS, rounding=ROUND_UP)
    return GoalProgressRead(
        id=goal.id,
        name=goal.name,
        target_amount=target,
        deadline=goal.deadline,
        accumulated=accumulated,
        remaining=remaining,
        percentage=percentage,
        completed=completed,
        days_remaining=days_remaining,
        suggested_monthly_contribution=suggested,
    )


async def _progress_for(
    session: AsyncSession, user_id: uuid.UUID, goal: SavingsGoal
) -> GoalProgressRead:
    accumulated = (await _accumulated_by_goal(session, user_id, [goal.id])).get(
        goal.id, Decimal("0")
    )
    return build_progress(goal, accumulated, await _today(session, user_id))


async def create_goal(
    session: AsyncSession, user_id: uuid.UUID, data: GoalCreate
) -> GoalProgressRead:
    goal = SavingsGoal(
        user_id=user_id,
        name=data.name,
        target_amount=data.target_amount,
        deadline=data.deadline,
    )
    session.add(goal)
    await session.commit()
    await session.refresh(goal)
    return await _progress_for(session, user_id, goal)


async def update_goal(
    session: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID, data: GoalUpdate
) -> GoalProgressRead:
    goal = await _get_owned(session, user_id, goal_id)
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(goal, field, value)
    await session.commit()
    await session.refresh(goal)
    return await _progress_for(session, user_id, goal)


async def delete_goal(
    session: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID
) -> GoalRead:
    goal = await _get_owned(session, user_id, goal_id)
    snapshot = GoalRead.model_validate(goal)
    await session.delete(goal)
    await session.commit()
    return snapshot


async def list_goals(session: AsyncSession, user_id: uuid.UUID) -> list[GoalProgressRead]:
    result = await session.execute(
        select(SavingsGoal)
        .where(SavingsGoal.user_id == user_id)
        .order_by(SavingsGoal.created_at, SavingsGoal.name)
    )
    goals = list(result.scalars().all())
    accumulated = await _accumulated_by_goal(session, user_id, [goal.id for goal in goals])
    today = await _today(session, user_id)
    return [build_progress(goal, accumulated.get(goal.id, Decimal("0")), today) for goal in goals]


async def add_contribution(
    session: AsyncSession, user_id: uuid.UUID, data: ContributionCreate
) -> tuple[SavingsContribution, GoalProgressRead]:
    """Registra un aporte en su propia tabla; no crea ningún gasto (RB-11)."""
    goal = await _get_owned(session, user_id, data.goal_id)
    contribution = SavingsContribution(
        goal_id=goal.id,
        user_id=user_id,
        amount=data.amount,
        contributed_on=data.contributed_on or await _today(session, user_id),
    )
    session.add(contribution)
    await session.commit()
    await session.refresh(contribution)
    return contribution, await _progress_for(session, user_id, goal)
