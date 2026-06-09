"""add strategy_knowledge table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-08 09:00:00.000000

Phase 8 step-01：策略知識庫資料表（candidate → validated → curated / rejected）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "strategy_knowledge",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("theory", sa.Text(), nullable=True),
        sa.Column("scenario", sa.Text(), nullable=True),
        sa.Column("usage_note", sa.Text(), nullable=True),
        sa.Column("strategy_key", sa.String(), nullable=False),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("composite_of", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("oos_metrics", sa.JSON(), nullable=True),
        sa.Column("regime_affinity", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("strategy_knowledge", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_strategy_knowledge_id"), ["id"], unique=False)
        batch_op.create_index(batch_op.f("ix_strategy_knowledge_status"), ["status"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("strategy_knowledge", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_strategy_knowledge_status"))
        batch_op.drop_index(batch_op.f("ix_strategy_knowledge_id"))

    op.drop_table("strategy_knowledge")
