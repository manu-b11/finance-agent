"""create reminders and push subscriptions

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reminders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("concept", sa.String(length=255), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("start_local", sa.DateTime(), nullable=False),
        sa.Column("frequency", sa.String(length=10), nullable=False),
        sa.Column("interval_count", sa.Integer(), nullable=True),
        sa.Column("interval_unit", sa.String(length=10), nullable=True),
        sa.Column("month_days", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("weekdays", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "frequency IN ('once', 'daily', 'weekly', 'biweekly', 'monthly', 'custom')",
            name="ck_reminders_frequency",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'completed', 'cancelled')", name="ck_reminders_status"
        ),
        sa.CheckConstraint(
            "interval_unit IS NULL OR interval_unit IN ('days', 'weeks', 'months')",
            name="ck_reminders_interval_unit",
        ),
        sa.CheckConstraint(
            "interval_count IS NULL OR interval_count >= 1", name="ck_reminders_interval_count"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reminders_status_next_run_at", "reminders", ["status", "next_run_at"], unique=False
    )
    op.create_index("ix_reminders_user_id_status", "reminders", ["user_id", "status"], unique=False)
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(length=255), nullable=False),
        sa.Column("auth", sa.String(length=255), nullable=False),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint"),
    )
    op.create_index(
        "ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
    op.drop_index("ix_reminders_user_id_status", table_name="reminders")
    op.drop_index("ix_reminders_status_next_run_at", table_name="reminders")
    op.drop_table("reminders")
