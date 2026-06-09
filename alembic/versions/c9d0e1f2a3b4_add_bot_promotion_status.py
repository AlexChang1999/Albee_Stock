"""add bot promotion status (Phase 10 step-06)

董事會核准頁：bots 表加三個「晉升狀態」欄位，記錄 Bot 從 Paper 晉升到真錢的
人工核准軌跡（paper / proposed_live / approved_live / rejected）+ 提議時間 + 理由。

★安全紅線：promotion_status="approved_live" 只是「人已同意」的旗標，不放行真錢。
真錢仍須 ALPACA_BASE_URL 實盤 + ALLOW_LIVE_TRADING=true 雙閘把關。本遷移不碰那道安全閥。

SQLite 加欄位一律走 batch_alter_table（render_as_batch=True 已在 env.py 設）。
既有列以 server_default="paper" 回填 promotion_status。

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-06-08 17:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bots", schema=None) as batch_op:
        # 既有 Bot 列回填 "paper"（都還沒被提議晉升）
        batch_op.add_column(
            sa.Column("promotion_status", sa.String(), nullable=False, server_default="paper")
        )
        batch_op.add_column(sa.Column("promotion_proposed_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("promotion_reason", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("bots", schema=None) as batch_op:
        batch_op.drop_column("promotion_reason")
        batch_op.drop_column("promotion_proposed_at")
        batch_op.drop_column("promotion_status")
