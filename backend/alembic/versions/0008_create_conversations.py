"""create conversations and link chat messages

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversations_user_id_updated_at",
        "conversations",
        ["user_id", "updated_at"],
        unique=False,
    )

    op.add_column(
        "chat_messages", sa.Column("conversation_id", sa.Uuid(), nullable=True)
    )
    # Cada usuario con mensajes previos recibe una conversación con su primer mensaje.
    op.execute(
        """
        INSERT INTO conversations (id, user_id, title, created_at, updated_at)
        SELECT
            md5(m.user_id::text)::uuid,
            m.user_id,
            COALESCE(
                (
                    SELECT left(regexp_replace(c.content, '\\s+', ' ', 'g'), 120)
                    FROM chat_messages c
                    WHERE c.user_id = m.user_id AND c.role = 'user'
                    ORDER BY c.id ASC
                    LIMIT 1
                ),
                'Conversación anterior'
            ),
            MIN(m.created_at),
            MAX(m.created_at)
        FROM chat_messages m
        GROUP BY m.user_id
        """
    )
    op.execute(
        "UPDATE chat_messages SET conversation_id = md5(user_id::text)::uuid"
    )
    op.alter_column("chat_messages", "conversation_id", nullable=False)
    op.create_index(
        "ix_chat_messages_conversation_id_id",
        "chat_messages",
        ["conversation_id", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_conversation_id_id", table_name="chat_messages")
    op.drop_column("chat_messages", "conversation_id")
    op.drop_index("ix_conversations_user_id_updated_at", table_name="conversations")
    op.drop_table("conversations")
