"""
回測 API
========
用歷史資料模擬策略表現，不會真的下單。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.backtest_engine import run_backtest

router = APIRouter(tags=["Backtest"])


class BacktestRequest(BaseModel):
    """執行回測時要傳的資料。"""
    strategy: str = "ma_crossover"
    symbol: str
    params: dict = {}
    days: int = 365  # 回測往前抓幾天
    initial_cash: float = 10000.0  # 初始資金
    source: str = "alpaca"  # 資料源："alpaca"（預設）或 "yfinance"（免費）


@router.post("/backtest")
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
            source=payload.source,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"回測失敗：{e}")
