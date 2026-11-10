import pytest

from app.schemas.budget import BudgetSet, BudgetStatusQuery
from app.schemas.invoice import (
    DraftItem,
    InvoiceConfirm,
    InvoiceHeaderUpdate,
    InvoiceListQuery,
    InvoiceRef,
    ItemPosition,
    ItemUpdate,
)
from app.schemas.reminder import ReminderCreate, ReminderListQuery, ReminderRef, ReminderUpdate
from app.schemas.report import MonthlyReportQuery
from app.schemas.savings_goal import (
    ContributionCreate,
    GoalCreate,
    GoalListQuery,
    GoalRef,
    GoalUpdate,
)
from app.schemas.transaction import (
    PeriodQuery,
    TransactionCreate,
    TransactionFilters,
    TransactionRef,
    TransactionUpdate,
)
from app.tools import registry

MODELS = {
    "add_transaction": TransactionCreate,
    "update_transaction": TransactionUpdate,
    "delete_transaction": TransactionRef,
    "list_transactions": TransactionFilters,
    "get_balance": PeriodQuery,
    "set_budget": BudgetSet,
    "get_budget_status": BudgetStatusQuery,
    "create_savings_goal": GoalCreate,
    "update_savings_goal": GoalUpdate,
    "delete_savings_goal": GoalRef,
    "list_savings_goals": GoalListQuery,
    "add_goal_contribution": ContributionCreate,
    "get_expenses_by_category": PeriodQuery,
    "get_monthly_report": MonthlyReportQuery,
    "create_reminder": ReminderCreate,
    "update_reminder": ReminderUpdate,
    "cancel_reminder": ReminderRef,
    "list_reminders": ReminderListQuery,
    "get_invoice": InvoiceRef,
    "list_draft_invoices": InvoiceListQuery,
    "update_invoice": InvoiceHeaderUpdate,
    "update_invoice_item": ItemUpdate,
    "add_invoice_item": DraftItem,
    "delete_invoice_item": ItemPosition,
    "confirm_invoice": InvoiceConfirm,
    "discard_invoice": InvoiceRef,
}

POPPED_ARGUMENTS = {
    "update_transaction": {"transaction_id"},
    "update_savings_goal": {"goal_id"},
    "update_reminder": {"reminder_id"},
    "update_invoice": {"invoice_id"},
    "update_invoice_item": {"invoice_id", "position"},
    "add_invoice_item": {"invoice_id"},
}


def test_every_tool_is_registered():
    assert set(registry.TOOLS) == set(MODELS)


@pytest.mark.parametrize("name", sorted(MODELS))
def test_declared_properties_match_pydantic_fields(name):
    declared = set(registry.TOOLS[name].parameters["properties"])
    fields = set(MODELS[name].model_fields) | POPPED_ARGUMENTS.get(name, set())
    assert declared == fields


@pytest.mark.parametrize("name", sorted(MODELS))
def test_user_id_is_never_exposed_to_the_model(name):
    assert "user_id" not in registry.TOOLS[name].parameters["properties"]


@pytest.mark.parametrize("name", sorted(MODELS))
def test_required_fields_are_declared_properties(name):
    parameters = registry.TOOLS[name].parameters
    assert set(parameters.get("required", [])) <= set(parameters["properties"])


def test_confirm_invoice_requires_explicit_user_confirmation_flag():
    assert "user_confirmed" in registry.TOOLS["confirm_invoice"].parameters["required"]


def test_unknown_tool_returns_none():
    assert registry.get_tool("nope") is None
