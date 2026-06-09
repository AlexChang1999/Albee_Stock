"""
市場蒐集員 API（Phase 10 step-04）
====================================
收件匣端點：列出爬蟲收回來的原始策略素材（raw_strategy_finds），並讓人標記
status 流轉（new → triaged → built / discarded）。

定位：純讀 / 改狀態的「靈感收件匣」，**這裡不爬網、不寫策略碼、不建 Bot、不上真錢**。
收料由排程的 run_collector_scan 負責；寫成策略走 strategy-builder + OOS 閘 + 人工核准。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import RawStrategyFind

router = APIRouter(prefix="/collector", tags=["Collector"])

# 合法的 status 流轉值（防前端亂塞）
_VALID_STATUS = {"new", "triaged", "built", "discarded"}


class StatusUpdate(BaseModel):
    status: str


def _serialize(f: RawStrategyFind) -> dict:
    return {
        "id": f.id,
        "source": f.source,
        "source_url": f.source_url,
        "title": f.title,
        "summary": f.summary,
        "status": f.status,
        "fetched_at": f.fetched_at.isoformat() if f.fetched_at else None,
    }


@router.get("/finds")
def list_finds(
    limit: int = 50,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    列出收件匣素材，依抓取時間由新到舊。

    :param limit: 最多回幾筆（夾在 1~200）。
    :param status: 可選狀態篩選（new/triaged/built/discarded）。
    """
    q = db.query(RawStrategyFind)
    if status:
        q = q.filter(RawStrategyFind.status == status)
    rows = (
        q.order_by(RawStrategyFind.fetched_at.desc(), RawStrategyFind.id.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [_serialize(f) for f in rows]


@router.patch("/finds/{find_id}")
def update_find_status(find_id: int, body: StatusUpdate, db: Session = Depends(get_db)):
    """
    更新一筆素材的 status（人工策展：看過 → triaged / 已寫成策略 → built / 丟棄 → discarded）。

    **只改狀態旗標**，不觸發任何爬網 / 建策略 / 部署動作。
    """
    if body.status not in _VALID_STATUS:
        raise HTTPException(status_code=400, detail=f"不合法的 status：{body.status}")
    find = db.query(RawStrategyFind).filter(RawStrategyFind.id == find_id).first()
    if find is None:
        raise HTTPException(status_code=404, detail="找不到這筆素材")
    find.status = body.status
    db.commit()
    db.refresh(find)
    return _serialize(find)
