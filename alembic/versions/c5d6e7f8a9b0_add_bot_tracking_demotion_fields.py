"""add bot tracking/demotion fields (維運安全軌 H3 Step 7)

tracking error 自動降級：bots 表加四欄——
- tracking_breach_count（連續違規次數，既有列回填 0）
- tracking_last_rt_count（上次對帳時的回合數，防重複計數，既有列回填 0）
- demoted_at / demote_reason（被自動降級的時間與原因，可為 NULL）

降級只停新決策、不平倉、不撤券商端保護單；單向不自動恢復。
SQLite 加欄位一律走 batch_alter_table（render_as_batch=True 已在 env.py 設）。

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-06-11 15:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bots", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("tracking_breach_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("tracking_last_rt_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("demoted_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("demote_reason", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("bots", schema=None) as batch_op:
        batch_op.drop_column("demote_reason")
        batch_op.drop_column("demoted_at")
        batch_op.drop_column("tracking_last_rt_count")
        batch_op.drop_column("tracking_breach_count")
