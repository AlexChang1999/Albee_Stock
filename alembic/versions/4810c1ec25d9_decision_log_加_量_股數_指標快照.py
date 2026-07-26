"""decision log 加 量/股數/指標快照

Revision ID: 4810c1ec25d9
Revises: dad6dd04845c
Create Date: 2026-06-23 00:47:20.524110

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4810c1ec25d9'
down_revision: Union[str, Sequence[str], None] = 'dad6dd04845c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 只新增 decision_logs 的三欄（量/股數/指標快照）。
    # 註：autogenerate 另偵測到要 drop 'validation_symbols'（DB 有、metadata 無對應 model），
    # 那是無關本次的雜訊，已手動移除——不可在這支遷移砍掉那張表。
    op.add_column('decision_logs', sa.Column('volume', sa.Float(), nullable=True))
    op.add_column('decision_logs', sa.Column('qty', sa.Float(), nullable=True))
    op.add_column('decision_logs', sa.Column('indicators', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('decision_logs', 'indicators')
    op.drop_column('decision_logs', 'qty')
    op.drop_column('decision_logs', 'volume')
