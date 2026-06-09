"""
政治專討員 API（Phase 10 step-05）
====================================
唯讀端點：列出政治專討員判讀落表的政治事件（political_events），依發文時間由新到舊。
另提供 /political/risk：把最近的政治情緒接既有風險煞車後的「現況」（給戰情頁顯示）。

★ 定位：純讀 + 呈現「煞車現況」，**這裡不下單、不改部位、不猜方向**。是否真的縮部位，
  由 services/political.political_size_factor（預設關）+ 既有 event_risk 決定，UI 只如實顯示。
"""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import PoliticalEvent
from backend.services import political

router = APIRouter(prefix="/political", tags=["Political"])


def _serialize(e: PoliticalEvent) -> dict:
    return {
        "id": e.id,
        "source": e.source,
        "author": e.author,
        "content_summary": e.content_summary,
        "label": e.label,
        "score": e.score,
        "reason": e.reason,
        "posted_at": e.posted_at.isoformat() if e.posted_at else None,
        "posts_last_24h": e.posts_last_24h,
        "posts_last_1h": e.posts_last_1h,
    }


@router.get("/events")
def list_events(
    limit: int = 50,
    label: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    列出政治事件，依發文時間由新到舊。

    :param limit: 最多回幾筆（夾在 1~200）。
    :param label: 可選情緒篩選（bullish/bearish/neutral）。
    """
    q = db.query(PoliticalEvent)
    if label:
        q = q.filter(PoliticalEvent.label == label)
    rows = (
        q.order_by(PoliticalEvent.posted_at.desc(), PoliticalEvent.id.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [_serialize(e) for e in rows]


@router.get("/risk")
def current_risk(db: Session = Depends(get_db)):
    """
    回「政治風險煞車」的現況：是否啟用、要不要不開新倉 / 縮多少部位。

    純呈現——數字一律來自 political_size_factor（接既有 event_risk）。預設旗標關時
    回 size_factor=1.0（放行），代表此刻政治員完全不影響下單。
    """
    return political.political_size_factor(db)
