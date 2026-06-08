"""add automation_config

把模式 B 自動部署規則（AUTO_DEPLOY_*）從 .env 唯讀搬進 DB 單列表，讓前端可編輯。
建表後立刻種一筆 id=1 的預設列（值用本檔寫死的常數，不 import settings，避免遷移依賴環境）。

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-08 12:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("ev_threshold", sa.Float(), nullable=False),
        sa.Column("winrate_threshold", sa.Float(), nullable=False),
        sa.Column("max_bots", sa.Integer(), nullable=False),
        sa.Column("cash_per_bot", sa.Float(), nullable=False),
        sa.Column("scan_hour", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_automation_config_id"), "automation_config", ["id"], unique=False)

    # 種一筆預設規則（id=1）。值對齊 .env 的 AUTO_DEPLOY_* 預設（寫死常數，不依賴環境）。
    automation_config = sa.table(
        "automation_config",
        sa.column("id", sa.Integer),
        sa.column("enabled", sa.Boolean),
        sa.column("ev_threshold", sa.Float),
        sa.column("winrate_threshold", sa.Float),
        sa.column("max_bots", sa.Integer),
        sa.column("cash_per_bot", sa.Float),
        sa.column("scan_hour", sa.Integer),
    )
    op.bulk_insert(
        automation_config,
        [{
            "id": 1,
            "enabled": False,
            "ev_threshold": 150.0,
            "winrate_threshold": 55.0,
            "max_bots": 5,
            "cash_per_bot": 1000.0,
            "scan_hour": 8,
        }],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_automation_config_id"), table_name="automation_config")
    op.drop_table("automation_config")
