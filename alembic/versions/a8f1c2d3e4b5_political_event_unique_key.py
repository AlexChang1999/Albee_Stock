"""political_events 加 (author, posted_at) 唯一鍵（防重判重複落表）

雲端洗版根治：同作者同一發文時間只能落一列。重啟回補 / 搬 DB 後重判舊貼文時，
靠這個唯一鍵在 DB 端擋掉重複落表（→ record_event 撞鍵回 None → runner 不重發通知）。

加約束前先清掉既有重複列（保留每組最小 id），否則加唯一鍵會失敗。

Revision ID: a8f1c2d3e4b5
Revises: 2639cd3d3e17
Create Date: 2026-06-15 00:00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a8f1c2d3e4b5"
down_revision = "2639cd3d3e17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 先 dedup：同 (author, posted_at) 只保留最小 id，其餘刪除。
    # NOT IN (SELECT MIN(id) ... GROUP BY ...) 在 SQLite 與 PostgreSQL 皆可用。
    op.execute(
        """
        DELETE FROM political_events
        WHERE id NOT IN (
            SELECT min_id FROM (
                SELECT MIN(id) AS min_id
                FROM political_events
                GROUP BY author, posted_at
            ) AS keep
        )
        """
    )
    # batch 模式：SQLite 不能直接 ADD CONSTRAINT，env.py 已設 render_as_batch
    with op.batch_alter_table("political_events") as batch_op:
        batch_op.create_unique_constraint(
            "uq_political_author_posted", ["author", "posted_at"]
        )


def downgrade() -> None:
    with op.batch_alter_table("political_events") as batch_op:
        batch_op.drop_constraint("uq_political_author_posted", type_="unique")
