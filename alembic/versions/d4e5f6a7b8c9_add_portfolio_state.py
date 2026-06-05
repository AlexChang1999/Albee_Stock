"""add portfolio_state (組合回撤熔斷峰值持久化 Phase 6 step-09)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-05

新增 portfolio_state 表（單列）：存帳戶總權益的歷史峰值，供組合回撤熔斷判斷。
峰值持久化後，後端重啟仍記得最高水位，熔斷不會因重啟而失效。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "portfolio_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("equity_peak", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_portfolio_state_id"), "portfolio_state", ["id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_portfolio_state_id"), table_name="portfolio_state")
    op.drop_table("portfolio_state")
