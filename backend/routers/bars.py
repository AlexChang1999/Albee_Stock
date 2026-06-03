"""
歷史 K 線 API
=============
提供前端原生圖表（lightweight-charts）需要的歷史日 K 線資料。

GET /bars/{symbol}?days=120&source=alpaca
  → 回傳一個陣列，每筆是一根日 K：
    { "time": "2026-06-03", "open":..., "high":..., "low":..., "close":..., "volume":... }

設計重點：
- 直接重用 services/market_data.get_bars（同一份資料源契約，alpaca / yfinance 都支援）。
- time 用 "YYYY-MM-DD" 字串：lightweight-charts 的日線圖直接吃這個格式。
- 把 DataFrame 轉成「乾淨、能進 JSON」的 list（避開 numpy 型別 / NaN 不能序列化的問題）。
"""

import math

from fastapi import APIRouter, HTTPException

from backend.services.market_data import get_bars

router = APIRouter(tags=["Bars"])


def _to_candles(df) -> list[dict]:
    """
    把 get_bars 回傳的 DataFrame（欄位 timestamp/open/high/low/close/volume）
    轉成 lightweight-charts 要的 candle 陣列。

    抽成純函式好寫測試：餵一個假 DataFrame 進來就能驗證轉換，不用真的連網。
    """
    if df is None or df.empty:
        return []

    candles = []
    for row in df.itertuples(index=False):
        # timestamp 可能是 pandas Timestamp / datetime；統一取日期字串 "YYYY-MM-DD"
        ts = row.timestamp
        time_str = ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10]

        # 任何 NaN（停牌、缺值）就跳過這根，避免前端圖表炸掉
        ohlc = [row.open, row.high, row.low, row.close]
        if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in ohlc):
            continue

        candles.append({
            "time": time_str,
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": int(row.volume) if not math.isnan(float(row.volume)) else 0,
        })

    return candles


@router.get("/bars/{symbol}")
def list_bars(symbol: str, days: int = 120, source: str = "alpaca"):
    """
    取某股票最近 N 天的日 K 線（給前端畫圖用）。

    :param symbol: 股票代號，例如 "AAPL"
    :param days: 往前抓幾天（預設 120）
    :param source: 資料源 "alpaca"（預設）或 "yfinance"（免費）
    """
    try:
        df = get_bars(symbol.upper(), days=days, source=source)
        return {"symbol": symbol.upper(), "candles": _to_candles(df)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"取得 K 線失敗：{e}")
