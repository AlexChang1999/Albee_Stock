"""
機會清單 API（Phase 10 step-02）
=================================
唯讀端點：列出常駐探勘持久化的候選，依**樣本外 EV** 由高到低。
戰情頁（step-01）與未來董事會核准頁（step-06）取用同一份清單。

定位：純讀 opportunity 表，不在這裡跑海選 / 建 Bot / 上真錢（收集由排程的
run_opportunity_scan 負責、部署由人工核准負責）。
"""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Opportunity

router = APIRouter(tags=["Opportunities"])


def _serialize(o: Opportunity) -> dict:
    return {
        "id": o.id,
        "symbol": o.symbol,
        "strategy_key": o.strategy_key,
        "params": o.params,
        "oos_expected_value": o.oos_expected_value,
        "oos_win_rate_pct": o.oos_win_rate_pct,
        "sentiment": o.sentiment,
        "status": o.status,
        "scanned_at": o.scanned_at.isoformat() if o.scanned_at else None,
    }


@router.get("/opportunities")
def list_opportunities(
    limit: int = 50,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    列出機會清單，依 OOS EV 由高到低（NULL 排最後）。

    :param limit: 最多回幾筆（夾在 1~200）。
    :param status: 可選狀態篩選（new/seen/deployed/expired）。
    """
    q = db.query(Opportunity)
    if status:
        q = q.filter(Opportunity.status == status)
    rows = (
        q.order_by(Opportunity.oos_expected_value.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [_serialize(o) for o in rows]
