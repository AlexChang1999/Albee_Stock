"""add opportunities + automation_config.scan_interval_min

Phase 10 step-02：常駐探勘把海選候選持久化進 opportunities 表（好策略不漏掉、關 app 也留著）；
automation_config 加 scan_interval_min 欄位（盤中常駐掃描的間隔，分鐘；0=關）。

SQLite 改既有表（加欄位）一律走 batch_alter_table（render_as_batch=True 已在 env.py 設）。
既有 id=1 規則列以 server_default="30" 回填。

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-06-08 15:30:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) 機會清單表
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("strategy_key", sa.String(), nullable=False),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("oos_expected_value", sa.Float(), nullable=True),
        sa.Column("oos_win_rate_pct", sa.Float(), nullable=True),
        sa.Column("sentiment", sa.JSON(), nullable=True),
        sa.Column("scanned_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_opportunities_id"), "opportunities", ["id"], unique=False)
    op.create_index(op.f("ix_opportunities_symbol"), "opportunities", ["symbol"], unique=False)
    op.create_index(op.f("ix_opportunities_status"), "opportunities", ["status"], unique=False)

    # 2) automation_config 加常駐掃描間隔欄位（既有 id=1 列以 server_default 回填 30）
    with op.batch_alter_table("automation_config", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("scan_interval_min", sa.Integer(), nullable=False, server_default="30")
        )


def downgrade() -> None:
    with op.batch_alter_table("automation_config", schema=None) as batch_op:
        batch_op.drop_column("scan_interval_min")

    op.drop_index(op.f("ix_opportunities_status"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_symbol"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_id"), table_name="opportunities")
    op.drop_table("opportunities")
