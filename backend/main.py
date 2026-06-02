"""
FastAPI 入口
============
這是後端的「大門」。啟動後會提供一組 API 給前端（或你用瀏覽器/工具）呼叫。

啟動方式（在專案根目錄、啟動 venv 後）：
    uvicorn backend.main:app --reload

啟動後打開瀏覽器看自動產生的 API 文件：
    http://127.0.0.1:8000/docs

本檔只負責三件事：
1. 建立 app、設定 CORS、定義啟動/關閉流程（lifespan）
2. 提供最基本的端點（健康檢查 /、帳戶 /account）
3. 把各功能的路由（routers/）掛上去

實際的 API 細節分散在 backend/routers/ 底下，依功能各自一個檔案。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import init_db
from backend.services.alpaca_client import alpaca_client
from backend.routers import bots, backtest, orders


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


# ---------- 基本端點 ----------
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


# ---------- 掛上各功能的路由 ----------
# include_router 會把 routers/ 裡定義好的那一疊路由併進這個 app。
app.include_router(bots.router)
app.include_router(backtest.router)
app.include_router(orders.router)
