"""add raw_strategy_finds (Phase 10 step-04)

市場蒐集員收件匣：爬蟲從 RSS / 部落格收回來的「策略描述文字」原料落這張表，
當人 / strategy-builder 寫成策略的素材。只存原始文字，不存回測結果、不代表已上線。

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-06-09 10:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raw_strategy_finds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default=""),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="new"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_raw_strategy_finds_id"), "raw_strategy_finds", ["id"], unique=False)
    op.create_index(op.f("ix_raw_strategy_finds_source_url"), "raw_strategy_finds", ["source_url"], unique=False)
    op.create_index(op.f("ix_raw_strategy_finds_status"), "raw_strategy_finds", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_raw_strategy_finds_status"), table_name="raw_strategy_finds")
    op.drop_index(op.f("ix_raw_strategy_finds_source_url"), table_name="raw_strategy_finds")
    op.drop_index(op.f("ix_raw_strategy_finds_id"), table_name="raw_strategy_finds")
    op.drop_table("raw_strategy_finds")
