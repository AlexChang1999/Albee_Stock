"""
機會清單 API（Phase 10 step-02）
=================================
列出常駐探勘持久化的候選，依**樣本外 EV** 由高到低。
戰情頁（step-01）與未來董事會核准頁（step-06）取用同一份清單。

定位：主要讀 opportunity 表；另提供「立刻掃一輪」手動端點（POST /opportunities/scan），
讓使用者不必等盤中排程就強制跑一輪海選選標的。建 Bot / 上真錢仍由人工核准負責。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
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


@router.post("/opportunities/scan")
def scan_opportunities_now(db: Session = Depends(get_db)):
    """
    立刻強制跑一輪海選選標的（不必等盤中排程、不檢查開盤）。

    對 SCREENER_WATCHLIST 各檔跑回測漏斗 → 挑最佳策略+標的 → upsert 進機會清單。
    給戰情頁「立刻掃一輪」按鈕用。回掃出的候選筆數，前端掃完重抓清單即可看到。
    注意：watchlist 多檔 + 回測較重，可能要跑數十秒；需 Alpaca 金鑰才抓得到資料。
    """
    from backend.services.opportunity_scan import scan_once

    try:
        count = scan_once(db)
        db.commit()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"掃描失敗：{e}")
    return {"scanned": count, "message": f"掃完，產生 {count} 個候選機會"}
