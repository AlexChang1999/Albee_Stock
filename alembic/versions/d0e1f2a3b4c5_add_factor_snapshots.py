"""add factor_snapshots (Phase 10 step-03)

因子數值表：常駐掃描每輪順手把 watchlist 各檔的 7 個市場狀態因子（regime_features）
+ regime 標籤落成快照，供查詢 / CSV 匯出 / 報表。因子是觀測佐證，不是交易訊號。

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-06-08 18:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "factor_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("as_of", sa.DateTime(), nullable=False),
        sa.Column("volume_ratio", sa.Float(), nullable=True),
        sa.Column("return_5d", sa.Float(), nullable=True),
        sa.Column("return_20d", sa.Float(), nullable=True),
        sa.Column("volatility_20d", sa.Float(), nullable=True),
        sa.Column("trend_strength", sa.Float(), nullable=True),
        sa.Column("atr_pct", sa.Float(), nullable=True),
        sa.Column("range_position", sa.Float(), nullable=True),
        sa.Column("regime", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_factor_snapshots_id"), "factor_snapshots", ["id"], unique=False)
    op.create_index(op.f("ix_factor_snapshots_symbol"), "factor_snapshots", ["symbol"], unique=False)
    op.create_index(op.f("ix_factor_snapshots_as_of"), "factor_snapshots", ["as_of"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_factor_snapshots_as_of"), table_name="factor_snapshots")
    op.drop_index(op.f("ix_factor_snapshots_symbol"), table_name="factor_snapshots")
    op.drop_index(op.f("ix_factor_snapshots_id"), table_name="factor_snapshots")
    op.drop_table("factor_snapshots")
