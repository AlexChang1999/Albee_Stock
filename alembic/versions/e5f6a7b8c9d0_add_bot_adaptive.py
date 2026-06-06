"""add bot.adaptive (Phase 7 step-03 自適應選策略開關)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-06

新增 bots.adaptive 欄位（布林，預設 False）：開啟時 Bot 不固定用單一策略，
而是每輪依當下市場狀態查「狀態→最佳策略對照表」挑策略。預設關，向後相容。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite 改欄位很弱，一律走 batch 模式（alembic/env.py 已設 render_as_batch=True）。
    # 既有列補預設 0（False），故給 server_default；非空欄位才不會在舊資料上炸。
    with op.batch_alter_table("bots", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("adaptive", sa.Boolean(), nullable=False, server_default=sa.text("0"))
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("bots", schema=None) as batch_op:
        batch_op.drop_column("adaptive")
