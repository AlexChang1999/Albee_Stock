"""add strategy_knowledge.deployed_at (curated→bot 自動部署冪等)

知識庫策略自動部署成 Paper Bot 的排程需要一個冪等戳記：strategy_knowledge 表加
deployed_at（nullable）。None = 還沒部署過；自動 / 手動部署成功後戳上時間，排程才不會
重複對同一筆知識建 Bot。

SQLite 加欄位一律走 batch_alter_table（render_as_batch=True 已在 env.py 設）。
既有列 deployed_at 預設 NULL（視為「還沒部署」，下次排程會納入考量）。

Revision ID: b9c0d1e2f3a4
Revises: a8f1c2d3e4b5
Create Date: 2026-06-18 12:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b9c0d1e2f3a4"
down_revision = "a8f1c2d3e4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("strategy_knowledge", schema=None) as batch_op:
        batch_op.add_column(sa.Column("deployed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("strategy_knowledge", schema=None) as batch_op:
        batch_op.drop_column("deployed_at")
