"""
時間框架（timeframe）單一事實來源（M2：多 timeframe 資料地基）
==============================================================
全系統的 K 線時間框架都用這裡定義的字串 key（"1Min"、"5Min"…"1Day"），
資料層（alpaca / yfinance / bar_cache）、回測引擎、年化指標共用同一份表，
避免每層各自映射、悄悄分岔。

設計原則：
- 預設 "1Day"：所有既有呼叫不帶 timeframe → 行為與改版前 bit-for-bit 一致。
- 「一天有幾根 bar」用美股正規交易時段（RTH）9:30–16:00 = 6.5 小時 = 390 分鐘計。
- 年化基數 = 252 交易日 × 每日 bar 數——分鐘 K 的 Sharpe/Sortino 若沿用 252 會
  嚴重失真（把 5 分鐘報酬當日報酬年化），必須用這裡的 periods_per_year。
"""

# 支援的 timeframe → (數量, 單位, 每個交易日約有幾根 bar)
# 單位字串對齊 alpaca-py 的 TimeFrameUnit 名稱（Minute/Hour/Day）
_SPEC: dict[str, tuple[int, str, float]] = {
    "1Min":  (1,  "Minute", 390.0),
    "5Min":  (5,  "Minute", 78.0),
    "15Min": (15, "Minute", 26.0),
    "30Min": (30, "Minute", 13.0),
    "1Hour": (1,  "Hour",   6.5),
    "2Hour": (2,  "Hour",   3.25),
    "4Hour": (4,  "Hour",   1.625),
    "1Day":  (1,  "Day",    1.0),
}

# 全部合法 key（回測研究矩陣、前端下拉選單都吃這份）
ALL_TIMEFRAMES: list[str] = list(_SPEC.keys())

DEFAULT_TIMEFRAME = "1Day"

# 一年約 252 個交易日（與 analytics 舊常數一致）
TRADING_DAYS_PER_YEAR = 252


def validate(timeframe: str) -> str:
    """驗證 timeframe 字串合法，回傳正規化後的 key；不合法直接拋 ValueError（快炸快修）。"""
    if timeframe in _SPEC:
        return timeframe
    # 容錯大小寫（"1min" → "1Min"）
    for key in _SPEC:
        if key.lower() == str(timeframe).lower():
            return key
    raise ValueError(f"不支援的 timeframe：{timeframe}（可用：{'、'.join(ALL_TIMEFRAMES)}）")


def amount_unit(timeframe: str) -> tuple[int, str]:
    """回 (數量, 單位名)，給 alpaca_client 映射 TimeFrame(amount, TimeFrameUnit.X) 用。"""
    amt, unit, _ = _SPEC[validate(timeframe)]
    return amt, unit


def bars_per_day(timeframe: str) -> float:
    """每個交易日約有幾根 bar（RTH 390 分鐘計）。"""
    return _SPEC[validate(timeframe)][2]


def periods_per_year(timeframe: str) -> float:
    """
    年化基數：一年約有幾根 bar（= 252 × 每日 bar 數）。

    Sharpe/Sortino/年化波動的年化倍率都要用這個數字——
    1Day=252、1Hour≈1638、5Min≈19656。用錯基數指標就全錯。
    """
    return TRADING_DAYS_PER_YEAR * bars_per_day(timeframe)


def is_intraday(timeframe: str) -> bool:
    """是不是日內框架（非 1Day）。日內資料鏈有額外限制（資料源、快取新鮮度）。"""
    return validate(timeframe) != "1Day"


def bars_to_calendar_days(bars: int, timeframe: str) -> int:
    """
    「需要 N 根 bar」→「往前抓幾個日曆天」。

    先把 bar 數換成交易日數（除以每日 bar 數、無條件進位），
    再沿用 lookback 的慣例：交易日 → 日曆日 ×7/5、+5 天吸收國定假日。
    日內框架最少也抓 2 天（跨一個交易日邊界才有完整 session）。
    """
    import math

    trading_days = math.ceil(bars / bars_per_day(timeframe))
    days = math.ceil(trading_days * 7 / 5) + 5
    return max(days, 2)
