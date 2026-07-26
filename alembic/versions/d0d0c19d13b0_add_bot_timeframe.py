"""add bot timeframe（M2 多 timeframe 地基）

Revision ID: d0d0c19d13b0
Revises: 2768500820b2
Create Date: 2026-07-02

只加 bots.timeframe 一欄（預設 "1Day" = 舊行為不變）。

註：autogenerate 當時還偵測到其他 drift（validation_symbols 表、bots.knowledge_id、
strategy_knowledge.promotion_* 等）——那些是 main 分支的模型欄位，Neon 上本來就該有，
develop 尚未合入而已。**已人工剪掉那些 DROP**，遷移只做本次真正要做的一件事，
不誤刪 main 分支的資料。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd0d0c19d13b0'
down_revision: Union[str, Sequence[str], None] = '2768500820b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """加 bots.timeframe（server_default 讓既有列自動補 "1Day"）。"""
    op.add_column(
        'bots',
        sa.Column('timeframe', sa.String(), server_default='1Day', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('bots', 'timeframe')
