"""
Bot 管理 API
============
跟「Bot」有關的所有路由都集中在這裡：
建立、列出、編輯、刪除、查績效，以及手動執行/啟動/停止排程。

這裡用 FastAPI 的 APIRouter（路由器）。可以把它想成「一疊路由的小包裹」，
最後在 main.py 用 app.include_router() 一次掛上去。

prefix="/bots" 代表這個檔案裡的路由路徑前面都會自動加上 /bots，
所以下面寫 "" 其實就是 /bots，"/{bot_id}" 就是 /bots/{bot_id}。
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Bot, TradeLog
from backend.bots.bot_manager import bot_manager, run_bot_once
from backend.services.performance import compute_bot_stats

# tags=["Bots"] 只是讓 /docs 文件頁把這組 API 歸在「Bots」分類下，比較好找。
router = APIRouter(prefix="/bots", tags=["Bots"])


# ---------- 請求資料格式（Pydantic） ----------
class BotCreate(BaseModel):
    """建立或編輯 Bot 時要傳的資料。"""
    name: str
    strategy: str = "ma_crossover"
    symbol: str
    params: dict = {}
    trade_amount: float = 1000.0


# ---------- 內部小工具 ----------
def _bot_stats(db: Session, bot_id: int) -> dict:
    """查出某個 Bot 的交易紀錄（由舊到新），算出績效指標。"""
    rows = (
        db.query(TradeLog)
        .filter(TradeLog.bot_id == bot_id)
        .order_by(TradeLog.created_at.asc())
        .all()
    )
    trades = [{"side": r.side, "qty": r.qty, "price": r.price} for r in rows]
    return compute_bot_stats(trades)


def _get_bot_or_404(db: Session, bot_id: int) -> Bot:
    """共用：查出 Bot，找不到就回 404，避免每個路由重複寫。"""
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="找不到這個 Bot")
    return bot


# ---------- 路由 ----------
@router.post("")
def create_bot(payload: BotCreate, db: Session = Depends(get_db)):
    """建立一個新的 Bot。"""
    bot = Bot(
        name=payload.name,
        strategy=payload.strategy,
        symbol=payload.symbol.upper(),
        params=payload.params,
        trade_amount=payload.trade_amount,
    )
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return {"id": bot.id, "name": bot.name, "symbol": bot.symbol}


@router.put("/{bot_id}")
def update_bot(bot_id: int, payload: BotCreate, db: Session = Depends(get_db)):
    """編輯一個既有的 Bot。"""
    bot = _get_bot_or_404(db, bot_id)
    bot.name = payload.name
    bot.strategy = payload.strategy
    bot.symbol = payload.symbol.upper()
    bot.params = payload.params
    bot.trade_amount = payload.trade_amount
    db.commit()
    db.refresh(bot)
    return {"id": bot.id, "name": bot.name, "symbol": bot.symbol}


@router.delete("/{bot_id}")
def delete_bot(bot_id: int, db: Session = Depends(get_db)):
    """刪除一個 Bot（會先停掉它的排程）。"""
    bot = _get_bot_or_404(db, bot_id)
    bot_manager.stop_bot(bot_id)  # 先停掉定時排程，避免刪了還在跑
    db.delete(bot)
    db.commit()
    return {"message": f"已刪除 Bot：{bot.name}"}


@router.get("")
def list_bots(db: Session = Depends(get_db)):
    """列出所有 Bot（含各自的績效指標）。"""
    bots = db.query(Bot).all()
    return [
        {
            "id": b.id,
            "name": b.name,
            "strategy": b.strategy,
            "symbol": b.symbol,
            "params": b.params,
            "trade_amount": b.trade_amount,
            "is_active": b.is_active,
            # 績效指標：依該 Bot 的真實交易紀錄計算（沒交易時各項為 0）
            "stats": _bot_stats(db, b.id),
        }
        for b in bots
    ]


@router.get("/{bot_id}/stats")
def get_bot_stats(bot_id: int, db: Session = Depends(get_db)):
    """單獨取得某個 Bot 的績效指標。"""
    _get_bot_or_404(db, bot_id)
    return _bot_stats(db, bot_id)


@router.post("/{bot_id}/run")
def run_bot_now(bot_id: int, db: Session = Depends(get_db)):
    """手動讓某個 Bot 立刻跑一次策略（測試用，休市時間也能跑）。"""
    bot = _get_bot_or_404(db, bot_id)
    # 手動執行多半是為了測試，略過開市檢查，休市時段也能驗證流程
    run_bot_once(bot, ignore_market_hours=True)
    return {"message": f"Bot {bot.name} 已執行一次"}


@router.post("/{bot_id}/start")
def start_bot(bot_id: int, interval: int = 60, db: Session = Depends(get_db)):
    """啟動 Bot 的定時執行。"""
    bot = _get_bot_or_404(db, bot_id)
    bot.is_active = True
    db.commit()
    bot_manager.start_bot(bot, interval_seconds=interval)
    return {"message": f"Bot {bot.name} 已啟動"}


@router.post("/{bot_id}/stop")
def stop_bot(bot_id: int, db: Session = Depends(get_db)):
    """停止 Bot 的定時執行。"""
    bot = _get_bot_or_404(db, bot_id)
    bot.is_active = False
    db.commit()
    bot_manager.stop_bot(bot_id)
    return {"message": f"Bot {bot.name} 已停止"}
