"""add bot protective_order_id (維運安全軌 H1 Step 2)

券商端止損：bots 表加 protective_order_id 欄，記錄進場後掛在 Alpaca 券商端的
GTC stop / trailing stop 保護單訂單 id（None = 沒掛）。
存 DB 才能在後端重啟後不重複掛單、並在券商端成交後回填交易紀錄。

SQLite 加欄位一律走 batch_alter_table（render_as_batch=True 已在 env.py 設）。

Revision ID: a3b4c5d6e7f8
Revises: 9445466485df
Create Date: 2026-06-11 12:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a3b4c5d6e7f8"
down_revision = "9445466485df"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bots", schema=None) as batch_op:
        batch_op.add_column(sa.Column("protective_order_id", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("bots", schema=None) as batch_op:
        batch_op.drop_column("protective_order_id")
