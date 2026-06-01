"""
FastAPI 入口
============
這是後端的「大門」。啟動後會提供一組 API 給前端（或你用瀏覽器/工具）呼叫。

啟動方式（在專案根目錄、啟動 venv 後）：
    uvicorn backend.main:app --reload

啟動後打開瀏覽器看自動產生的 API 文件：
    http://127.0.0.1:8000/docs

備註：Phase 1 先把 API 都放這個檔案，方便理解；
Phase 2 再依 CLAUDE.md 的規劃拆分到 routers/。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import init_db, get_db
from backend.models import Bot, TradeLog
from backend.services.alpaca_client import alpaca_client
from backend.bots.bot_manager import bot_manager, run_bot_once
from backend.services.backtest_engine import run_backtest


# lifespan：定義 app「啟動時」與「關閉時」要做的事。
# 這是 FastAPI 現在推薦的寫法（取代舊的 @app.on_event）。
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- 啟動時 ---
    init_db()  # 把資料庫的表建好（如果還沒建）
    print(f"🚀 Albee Stock 啟動完成（模擬交易模式：{settings.IS_PAPER}）")
    yield
    # --- 關閉時 ---（目前沒事要做，先留空）


app = FastAPI(title="Albee Stock 交易機器人", lifespan=lifespan)

# CORS：允許前端（Vite 開發伺服器，預設 5173 埠）呼叫這個後端。
# 沒有這段，瀏覽器會以「跨來源」為由擋掉前端的 API 請求。
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],  # 允許所有 HTTP 方法（GET/POST...）
    allow_headers=["*"],
)


# ---------- 請求/回應的資料格式（Pydantic） ----------
class BotCreate(BaseModel):
    """建立 Bot 時要傳的資料。"""
    name: str
    strategy: str = "ma_crossover"
    symbol: str
    params: dict = {}
    trade_amount: float = 1000.0


class BacktestRequest(BaseModel):
    """執行回測時要傳的資料。"""
    strategy: str = "ma_crossover"
    symbol: str
    params: dict = {}
    days: int = 365  # 回測往前抓幾天
    initial_cash: float = 10000.0  # 初始資金


# ---------- 基本 ----------
@app.get("/")
def root():
    """健康檢查：確認服務有在跑。"""
    return {"message": "Albee Stock 後端運行中", "paper_trading": settings.IS_PAPER}


@app.get("/account")
def get_account():
    """取得 Alpaca 帳戶資訊。"""
    try:
        acc = alpaca_client.get_account()
        return {
            "status": str(acc.status),
            "cash": acc.cash,
            "buying_power": acc.buying_power,
            "portfolio_value": acc.portfolio_value,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"連線 Alpaca 失敗：{e}")


# ---------- Bot 管理 ----------
@app.post("/bots")
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


@app.put("/bots/{bot_id}")
def update_bot(bot_id: int, payload: BotCreate, db: Session = Depends(get_db)):
    """編輯一個既有的 Bot。"""
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="找不到這個 Bot")
    # 更新欄位
    bot.name = payload.name
    bot.strategy = payload.strategy
    bot.symbol = payload.symbol.upper()
    bot.params = payload.params
    bot.trade_amount = payload.trade_amount
    db.commit()
    db.refresh(bot)
    return {"id": bot.id, "name": bot.name, "symbol": bot.symbol}


@app.delete("/bots/{bot_id}")
def delete_bot(bot_id: int, db: Session = Depends(get_db)):
    """刪除一個 Bot（會先停掉它的排程）。"""
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="找不到這個 Bot")
    bot_manager.stop_bot(bot_id)  # 先停掉定時排程，避免刪了還在跑
    db.delete(bot)
    db.commit()
    return {"message": f"已刪除 Bot：{bot.name}"}


@app.get("/bots")
def list_bots(db: Session = Depends(get_db)):
    """列出所有 Bot。"""
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
        }
        for b in bots
    ]


@app.post("/bots/{bot_id}/run")
def run_bot_now(bot_id: int, db: Session = Depends(get_db)):
    """手動讓某個 Bot 立刻跑一次策略（測試用）。"""
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="找不到這個 Bot")
    run_bot_once(bot)
    return {"message": f"Bot {bot.name} 已執行一次"}


@app.post("/bots/{bot_id}/start")
def start_bot(bot_id: int, interval: int = 60, db: Session = Depends(get_db)):
    """啟動 Bot 的定時執行。"""
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="找不到這個 Bot")
    bot.is_active = True
    db.commit()
    bot_manager.start_bot(bot, interval_seconds=interval)
    return {"message": f"Bot {bot.name} 已啟動"}


@app.post("/bots/{bot_id}/stop")
def stop_bot(bot_id: int, db: Session = Depends(get_db)):
    """停止 Bot 的定時執行。"""
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="找不到這個 Bot")
    bot.is_active = False
    db.commit()
    bot_manager.stop_bot(bot_id)
    return {"message": f"Bot {bot.name} 已停止"}


@app.get("/trades")
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


@app.post("/backtest")
def backtest(payload: BacktestRequest):
    """
    執行回測：用歷史資料模擬策略表現，回傳績效。
    這不會真的下單，純粹是「如果過去這樣做，結果會如何」的試算。
    """
    try:
        return run_backtest(
            strategy_name=payload.strategy,
            symbol=payload.symbol.upper(),
            params=payload.params,
            days=payload.days,
            initial_cash=payload.initial_cash,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"回測失敗：{e}")
