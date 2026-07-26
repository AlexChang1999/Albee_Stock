"""add agent_audits (Agent Gateway 審計軌跡，採納自 QuantDinger)

Revision ID: f7a8b9c0d1e2
Revises: c5040cf68986
Create Date: 2026-06-27

新增 agent_audits 表：外部 AI agent 每次打 /api/agent/v1/* 留一筆 append-only 紀錄
（端點 / token 標籤 / 參數快照 / 狀態 / 說明 / 時間），方便事後查驗每個外部自動動作。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "c5040cf68986"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "agent_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("token_label", sa.String(), nullable=True),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("detail", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_audits_id"), "agent_audits", ["id"], unique=False)
    op.create_index(op.f("ix_agent_audits_endpoint"), "agent_audits", ["endpoint"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_agent_audits_endpoint"), table_name="agent_audits")
    op.drop_index(op.f("ix_agent_audits_id"), table_name="agent_audits")
    op.drop_table("agent_audits")
