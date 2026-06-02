"""add bot.peak_price (追蹤止損最高價持久化)

Revision ID: a1b2c3d4e5f6
Revises: e475240e3a97
Create Date: 2026-06-02

新增 bots.peak_price 欄位：把「持倉期間最高價」從記憶體改存資料庫，
後端重啟後追蹤止損不會被重置。nullable，None = 空手或尚未進場。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "e475240e3a97"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite 改欄位很弱，一律走 batch 模式（alembic/env.py 已設 render_as_batch=True）
    with op.batch_alter_table("bots", schema=None) as batch_op:
        batch_op.add_column(sa.Column("peak_price", sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("bots", schema=None) as batch_op:
        batch_op.drop_column("peak_price")
