"""add bot exit policy columns

Phase 16 M4 可插拔出場政策：bots 加三欄
- exit_policy_key    ：政策代號（fixed_pct/atr/swing/vwap；None = 沿用舊 % 欄位）
- exit_policy_params ：政策參數 JSON
- exit_plan          ：目前持倉的出場計畫（內部狀態，斷電重啟 stop 不漂移）

注意：autogenerate 當時混進了別台機器造成的 DB 漂移
（validation_symbols 表、bots.knowledge_id、strategy_knowledge 三欄的 drop），
已全數手工剔除——本遷移只做「加三欄」，不動任何別人的東西。

Revision ID: 03274cbd08de
Revises: d0d0c19d13b0
Create Date: 2026-07-02 19:45:54.797419

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '03274cbd08de'
down_revision: Union[str, Sequence[str], None] = 'd0d0c19d13b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('bots', sa.Column('exit_policy_key', sa.String(), nullable=True))
    op.add_column('bots', sa.Column('exit_policy_params', sa.JSON(), nullable=True))
    op.add_column('bots', sa.Column('exit_plan', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('bots', 'exit_plan')
    op.drop_column('bots', 'exit_policy_params')
    op.drop_column('bots', 'exit_policy_key')
