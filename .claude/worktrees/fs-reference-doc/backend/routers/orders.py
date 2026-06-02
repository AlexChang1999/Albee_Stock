"""
交易（訂單）紀錄 API
====================
列出 Bot 送出過的所有交易紀錄。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import TradeLog

router = APIRouter(tags=["Orders"])


@router.get("/trades")
def list_trades(db: Session = Depends(get_db)):
    """列出所有交易紀錄（最新的在前）。"""
    trades = db.query(TradeLog).order_by(TradeLog.created_at.desc()).all()
    return [
        {
            "id": t.id,
            "bot_id": t.bot_id,
            "symbol": t.symbol,
            "side": t.side,
            "qty": t.qty,
            "price": t.price,
            "reason": t.reason,
            "created_at": t.created_at,
        }
        for t in trades
    ]
