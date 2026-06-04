"""add bot.auto_created (模式 B 自動駕駛標記)

Revision ID: c3d4e5f6a7b8
Revises: 42855ad7c572
Create Date: 2026-06-04

新增 bots.auto_created 欄位：標記該 Bot 是否由「模式 B 自動駕駛」自動建立。
自動駕駛用它做兩件事：① 同標的去重（不重複自動建）② 計算自動 Bot 是否達上限。
預設 False（既有 Bot 與手動建立的都算 False），nullable=False 帶 server_default。
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
    # server_default="0"：讓既有資料列在加欄當下就有預設值 False，避免 NOT NULL 失敗。
    with op.batch_alter_table("bots", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "auto_created",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("bots", schema=None) as batch_op:
        batch_op.drop_column("auto_created")
