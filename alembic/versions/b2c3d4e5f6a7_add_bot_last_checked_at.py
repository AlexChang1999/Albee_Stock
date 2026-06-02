"""add bot.last_checked_at (監聽狀態可視化)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-02

新增 bots.last_checked_at 欄位：記錄每個 Bot 最後一次成功跑完監測的時間，
讓前端能顯示「最後檢查：X 秒前」、確認排程真的在運作。nullable，None = 還沒跑過。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("bots", schema=None) as batch_op:
        batch_op.add_column(sa.Column("last_checked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("bots", schema=None) as batch_op:
        batch_op.drop_column("last_checked_at")
