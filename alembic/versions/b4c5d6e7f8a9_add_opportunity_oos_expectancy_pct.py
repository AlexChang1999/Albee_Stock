"""add opportunity oos_expectancy_pct (維運安全軌 H3 Step 6)

tracking error 對帳的回測側基準：opportunities 表加 oos_expectancy_pct
（OOS 期望值佔本金 %）。回測全進全出複利 vs Paper 固定 trade_amount，
美元 EV 不可直接比，一律用 % 歸一化後比對。

既有列為 NULL，常駐掃描下次更新該機會時自然回填（不做歷史回填）。
SQLite 加欄位一律走 batch_alter_table（render_as_batch=True 已在 env.py 設）。

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-06-11 14:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("opportunities", schema=None) as batch_op:
        batch_op.add_column(sa.Column("oos_expectancy_pct", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("opportunities", schema=None) as batch_op:
        batch_op.drop_column("oos_expectancy_pct")
