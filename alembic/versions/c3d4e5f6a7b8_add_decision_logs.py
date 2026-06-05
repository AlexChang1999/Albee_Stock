"""add decision_logs (決策審計軌跡 Phase 6 step-08)

Revision ID: c3d4e5f6a7b8
Revises: 42855ad7c572
Create Date: 2026-06-05

新增 decision_logs 表：記錄每一次 Bot 檢查「為何在這個時點買 / 賣 / 不動」，
連「沒成交但有決策」的時點（觀望 / 續抱 / 休市 / 購買力不足 / 熔斷）都留紀錄。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "42855ad7c572"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "decision_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=True),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("signal", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_decision_logs_id"), "decision_logs", ["id"], unique=False)
    op.create_index(op.f("ix_decision_logs_bot_id"), "decision_logs", ["bot_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_decision_logs_bot_id"), table_name="decision_logs")
    op.drop_index(op.f("ix_decision_logs_id"), table_name="decision_logs")
    op.drop_table("decision_logs")
