from datetime import timedelta
from decimal import Decimal

import pytest

from app.core.clock import local_today
from app.core.errors import NotFoundError
from app.schemas.savings_goal import ContributionCreate, GoalCreate, GoalUpdate
from app.schemas.user import UserCreate
from app.services import auth as auth_service
from app.services import savings_goal as service


async def make_user(session, email: str = "ana@example.com"):
    return await auth_service.register_user(
        session, UserCreate(email=email, password="clave-segura-1")
    )


async def new_goal(session, user_id, target="1000", deadline=None, name="Viaje"):
    return await service.create_goal(
        session,
        user_id,
        GoalCreate(name=name, target_amount=Decimal(target), deadline=deadline),
    )


async def test_new_goal_starts_with_zero_progress(session):
    user = await make_user(session)
    goal = await new_goal(session, user.id)
    assert goal.accumulated == Decimal("0.00")
    assert goal.remaining == Decimal("1000.00")
    assert goal.percentage == Decimal("0.00")
    assert goal.completed is False
    assert goal.days_remaining is None
    assert goal.suggested_monthly_contribution is None


async def test_contributions_update_progress(session):
    user = await make_user(session)
    user_id = user.id
    goal = await new_goal(session, user_id, target="1000")
    await service.add_contribution(
        session, user_id, ContributionCreate(goal_id=goal.id, amount=Decimal("250.50"))
    )
    _, progress = await service.add_contribution(
        session, user_id, ContributionCreate(goal_id=goal.id, amount=Decimal("100"))
    )
    assert progress.accumulated == Decimal("350.50")
    assert progress.remaining == Decimal("649.50")
    assert progress.percentage == Decimal("35.05")
    assert progress.completed is False


async def test_contribution_defaults_to_users_today(session):
    user = await make_user(session)
    goal = await new_goal(session, user.id)
    contribution, _ = await service.add_contribution(
        session, user.id, ContributionCreate(goal_id=goal.id, amount=Decimal("10"))
    )
    assert contribution.contributed_on == local_today(user.timezone)


async def test_goal_completed_when_target_reached_or_exceeded(session):
    user = await make_user(session)
    goal = await new_goal(session, user.id, target="100")
    _, progress = await service.add_contribution(
        session, user.id, ContributionCreate(goal_id=goal.id, amount=Decimal("120"))
    )
    assert progress.completed is True
    assert progress.remaining == Decimal("0.00")
    assert progress.percentage == Decimal("120.00")
    assert progress.suggested_monthly_contribution is None


async def test_deadline_gives_days_and_suggested_monthly_contribution(session):
    user = await make_user(session)
    today = local_today(user.timezone)
    goal = await new_goal(session, user.id, target="900", deadline=today + timedelta(days=90))
    assert goal.days_remaining == 90
    assert goal.suggested_monthly_contribution == Decimal("300.00")


async def test_suggested_contribution_rounds_up_and_covers_short_deadlines(session):
    user = await make_user(session)
    today = local_today(user.timezone)
    three_months = await new_goal(
        session, user.id, target="100", deadline=today + timedelta(days=90), name="A"
    )
    assert three_months.suggested_monthly_contribution == Decimal("33.34")
    soon = await new_goal(
        session, user.id, target="100", deadline=today + timedelta(days=5), name="B"
    )
    assert soon.suggested_monthly_contribution == Decimal("100.00")


async def test_overdue_goal_has_negative_days_and_no_suggestion(session):
    user = await make_user(session)
    today = local_today(user.timezone)
    goal = await new_goal(session, user.id, deadline=today - timedelta(days=3))
    assert goal.days_remaining == -3
    assert goal.suggested_monthly_contribution is None


async def test_list_goals_returns_progress_per_goal(session):
    user = await make_user(session)
    user_id = user.id
    first = await new_goal(session, user_id, target="1000", name="Viaje")
    second = await new_goal(session, user_id, target="200", name="Celular")
    await service.add_contribution(
        session, user_id, ContributionCreate(goal_id=first.id, amount=Decimal("500"))
    )
    goals = await service.list_goals(session, user_id)
    by_name = {goal.name: goal for goal in goals}
    assert by_name["Viaje"].accumulated == Decimal("500.00")
    assert by_name["Celular"].accumulated == Decimal("0.00")
    assert by_name["Celular"].id == second.id


async def test_update_goal_changes_only_sent_fields_and_can_clear_deadline(session):
    user = await make_user(session)
    today = local_today(user.timezone)
    goal = await new_goal(session, user.id, target="1000", deadline=today + timedelta(days=60))
    updated = await service.update_goal(
        session, user.id, goal.id, GoalUpdate(target_amount=Decimal("2000"))
    )
    assert updated.target_amount == Decimal("2000.00")
    assert updated.name == "Viaje"
    assert updated.deadline == today + timedelta(days=60)
    cleared = await service.update_goal(session, user.id, goal.id, GoalUpdate(deadline=None))
    assert cleared.deadline is None
    assert cleared.days_remaining is None


async def test_delete_goal_removes_its_contributions(session):
    user = await make_user(session)
    user_id = user.id
    goal = await new_goal(session, user_id)
    await service.add_contribution(
        session, user_id, ContributionCreate(goal_id=goal.id, amount=Decimal("10"))
    )
    deleted = await service.delete_goal(session, user_id, goal.id)
    assert deleted.name == "Viaje"
    assert await service.list_goals(session, user_id) == []
    with pytest.raises(NotFoundError):
        await service.add_contribution(
            session, user_id, ContributionCreate(goal_id=goal.id, amount=Decimal("10"))
        )


async def test_goals_cannot_be_accessed_by_other_users(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    goal = await new_goal(session, ana.id)
    with pytest.raises(NotFoundError):
        await service.update_goal(session, beto.id, goal.id, GoalUpdate(name="Mía"))
    with pytest.raises(NotFoundError):
        await service.delete_goal(session, beto.id, goal.id)
    with pytest.raises(NotFoundError):
        await service.add_contribution(
            session, beto.id, ContributionCreate(goal_id=goal.id, amount=Decimal("10"))
        )
    assert await service.list_goals(session, beto.id) == []
    assert len(await service.list_goals(session, ana.id)) == 1
