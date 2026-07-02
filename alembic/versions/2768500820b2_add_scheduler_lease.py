"""add scheduler_lease（選主租約單列表）

Revision ID: 2768500820b2
Revises: f7a8b9c0d1e2
Create Date: 2026-07-02

註：這個 revision id 是「補建」的——Neon 上的 alembic_version 已指向 2768500820b2
（某台機器先跑了 autogenerate+upgrade 但沒 commit 遷移檔，成了幽靈 rev），
且 scheduler_lease 表已存在、欄位與本檔一致。本檔用同一個 id 重建血緣：
- Neon：版本指標可解析，upgrade head 為 no-op（已在此 rev）
- 新機器/全新 DB：upgrade head 正常建表
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2768500820b2"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduler_lease",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("holder_id", sa.String(length=64), nullable=True),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("acquired_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scheduler_lease_id"), "scheduler_lease", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_scheduler_lease_id"), table_name="scheduler_lease")
    op.drop_table("scheduler_lease")
