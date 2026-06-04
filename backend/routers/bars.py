"""
K 線歷史資料 API
================
給前端的原生圖表（lightweight-charts）吃的 OHLC 日 K 線端點。

為什麼要這支：
- 前端原本用 TradingView 的 <iframe> widget，畫面是「別人的視窗」，
  React 無法把後端算出的進場價／止損線疊上去。
- 改用 lightweight-charts 後，K 線資料得自己從後端供應 ── 就是這支端點。

資料源沿用 services/market_data.py 的統一分派器（alpaca / yfinance），
所以這裡不直接碰任何資料商 SDK，只負責「把 DataFrame 轉成前端要的 JSON」。
"""

from fastapi import APIRouter, HTTPException

from backend.services import market_data

router = APIRouter(tags=["Bars"])


@router.get("/bars/{symbol}")
def get_bars(symbol: str, days: int = 120, source: str = "alpaca"):
    """
    取得某股票最近 N 天的日 K 線，回傳 lightweight-charts 能直接吃的格式。

    :param symbol: 股票代號，例如 "AAPL"（一律轉大寫）
    :param days: 往前抓幾天（日曆天，預設 120 天）
    :param source: 資料源，"alpaca"（預設）或 "yfinance"
    :return: {"symbol": "AAPL", "source": "...", "bars": [{time, open, high, low, close, volume}, ...]}

    lightweight-charts 的日線資料 time 欄位用 "YYYY-MM-DD" 字串即可，
    bars 依「舊 → 新」排序（市場資料源已保證此契約）。
    """
    symbol = symbol.upper()
    try:
        df = market_data.get_bars(symbol, days=days, source=source)
    except ValueError as e:
        # 不支援的 source ── 屬使用者輸入錯誤，回 400
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # 資料源連線／抓取失敗
        raise HTTPException(status_code=400, detail=f"取得 K 線失敗：{e}")

    # 抓不到資料（空 DataFrame）→ 回空陣列，讓前端顯示「無資料」而非報錯
    if df is None or df.empty:
        return {"symbol": symbol, "source": source, "bars": []}

    # DataFrame → 前端 JSON。timestamp 轉成 "YYYY-MM-DD"。
    bars = [
        {
            "time": row.timestamp.strftime("%Y-%m-%d"),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume),
        }
        for row in df.itertuples(index=False)
    ]
    return {"symbol": symbol, "source": source, "bars": bars}
