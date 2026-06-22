"""add political_events (Phase 10 step-05)

政治專討員從 Discord 偵測的政治貼文判讀落表：內容摘要 + 多空/風險分數 + 發文時間
+ 頻率特徵。定位是「煞車」（接 event_risk 降風險），不是「油門」（不猜方向）。

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-06-09 11:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "political_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default=""),
        sa.Column("author", sa.String(), nullable=False, server_default=""),
        sa.Column("content_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("label", sa.String(), nullable=False, server_default="neutral"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column("posts_last_24h", sa.Integer(), nullable=True),
        sa.Column("posts_last_1h", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_political_events_id"), "political_events", ["id"], unique=False)
    op.create_index(op.f("ix_political_events_posted_at"), "political_events", ["posted_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_political_events_posted_at"), table_name="political_events")
    op.drop_index(op.f("ix_political_events_id"), table_name="political_events")
    op.drop_table("political_events")
