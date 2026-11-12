"""add cards to chat messages

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Se guardan solo referencias (por ejemplo el id de una factura), no los datos.
    op.add_column("chat_messages", sa.Column("cards", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "cards")
