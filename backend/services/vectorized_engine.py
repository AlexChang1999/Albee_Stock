"""
向量化回測引擎（numpy / pandas）── 海選加速，零新依賴
========================================================
為什麼要這個？
  事件式引擎 `_run_on_df` 每根 K 棒都呼叫一次 `generate_signal(df[:i+1])`，
  而每次又把指標在整個視窗重算一遍 → 每組參數是 O(N²)。optimizer 要掃幾十組，
  資料一長就慢。

做法：
  把「整段資料的訊號」一次算完（向量化 rolling/ewm），得到每根一個 buy/sell/hold，
  再交給回測共用核心 `_simulate_from_signals` 跑同一套資金模擬與績效。
  指標都是「因果」的（rolling/ewm/Wilder 平滑只看過去與當下），所以
  「對整段算第 i 格」== 「對 df[:i+1] 算最後一格」== 事件式策略在第 i 根的判斷。
  → 結果與事件式引擎一致（用 tests/test_vectorized_engine.py 對拍驗證），但快一個量級。

安全網：
  只有列在 SIGNAL_BUILDERS 的策略走快路徑；沒列到的策略 optimizer 會自動退回
  事件式 `_run_on_df`，永不因為「某策略還沒向量化」而算錯或漏算。
"""

import numpy as np
import pandas as pd

from backend.strategies.base import Signal
from backend.strategies.indicators import adx_components
from backend.services.backtest_engine import _simulate_from_signals


def _hlc(df: pd.DataFrame):
    """high/low/close；缺 high/low 用 close 代替（與各事件式策略的退化規則一致）。"""
    close = df["close"]
    high = df["high"] if "high" in df.columns else close
    low = df["low"] if "low" in df.columns else close
    return high, low, close


# ---------- 各策略「整段訊號」向量化版本 ----------
# 每個函式回 (buy_mask, sell_mask)：長度同 df 的布林 ndarray。
# NaN 比較在 pandas 自然為 False（暖機期不出訊號），最後再依各策略的
# 「資料不足門檻」把前 guard_start 根強制設 False，與事件式 guard 對齊。

def _ma_crossover(df, p):
    short, long = p.get("short_window", 5), p.get("long_window", 20)
    close = df["close"]
    s = close.rolling(short).mean()
    l = close.rolling(long).mean()
    diff = s - l
    prev = diff.shift(1)
    buy = (prev <= 0) & (diff > 0)
    sell = (prev >= 0) & (diff < 0)
    return _finish(buy, sell, guard=long)


def _rsi(df, p):
    period = p.get("period", 14)
    overbought, oversold = p.get("overbought", 70), p.get("oversold", 30)
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    rsi = rsi.where(loss != 0, 100.0)  # 完全沒跌 → RSI=100（同事件式）
    buy = rsi < oversold
    sell = rsi > overbought
    return _finish(buy, sell, guard=period)


def _macd(df, p):
    fast, slow, sig = p.get("fast", 12), p.get("slow", 26), p.get("signal", 9)
    close = df["close"]
    macd = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    signal_line = macd.ewm(span=sig, adjust=False).mean()
    d = macd - signal_line
    prev = d.shift(1)
    buy = (prev <= 0) & (d > 0)
    sell = (prev >= 0) & (d < 0)
    # EMA 無 NaN 暖機，必須用 guard 蓋掉「資料還不夠」就亂叫的早期交叉
    return _finish(buy, sell, guard=slow + sig - 1)


def _bollinger(df, p):
    period, num_std = p.get("period", 20), p.get("num_std", 2)
    close = df["close"]
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    buy = close < (mid - num_std * std)
    sell = close > (mid + num_std * std)
    return _finish(buy, sell, guard=period - 1)


def _donchian(df, p):
    period = p.get("period", 20)
    high, low, close = _hlc(df)
    upper = high.rolling(period).max().shift(1)  # 不含今天的前 period 日高
    lower = low.rolling(period).min().shift(1)
    buy = close > upper
    sell = close < lower
    return _finish(buy, sell, guard=period)


def _stochastic(df, p):
    k_period, d_period = p.get("k_period", 14), p.get("d_period", 3)
    high, low, close = _hlc(df)
    low_min = low.rolling(k_period).min()
    high_max = high.rolling(k_period).max()
    rng = (high_max - low_min).replace(0, 1e-9)
    k = 100 * (close - low_min) / rng
    d = k.rolling(d_period).mean()
    prev_k, prev_d = k.shift(1), d.shift(1)
    buy = (prev_k <= prev_d) & (k > d)
    sell = (prev_k >= prev_d) & (k < d)
    return _finish(buy, sell, guard=k_period + d_period - 1)


def _momentum(df, p):
    period, threshold = p.get("period", 10), p.get("threshold", 5)
    close = df["close"]
    past = close.shift(period)
    roc = (close - past) / past * 100
    buy = roc > threshold
    sell = roc < -threshold
    return _finish(buy, sell, guard=period)


def _williams_r(df, p):
    period = p.get("period", 14)
    overbought, oversold = p.get("overbought", -20), p.get("oversold", -80)
    close = df["close"]
    highest = close.rolling(period).max()
    lowest = close.rolling(period).min()
    rng = highest - lowest
    percent_r = (highest - close) / rng.replace(0, np.nan) * -100
    buy = percent_r < oversold
    sell = percent_r > overbought
    # rng==0（價格無波動）→ 事件式回 HOLD；NaN 比較已是 False，這裡 guard 暖機
    return _finish(buy, sell, guard=period - 1)


def _adx_trend(df, p):
    period, thr = p.get("period", 14), p.get("adx_threshold", 25)
    adx, dip, dim = adx_components(df, length=period)
    buy = (adx > thr) & (dip > dim)
    sell = (adx > thr) & (dim > dip)
    return _finish(buy, sell, guard=period * 2 - 1)


def _finish(buy, sell, guard: int):
    """把 pandas 布林 Series 轉成 numpy、NaN→False、前 guard 根（資料不足）設 False。"""
    # 注意：pandas 3.0 copy-on-write 下 to_numpy() 可能回唯讀檢視，故 .copy() 取可寫陣列
    b = buy.fillna(False).to_numpy(dtype=bool).copy()
    s = sell.fillna(False).to_numpy(dtype=bool).copy()
    if guard > 0:
        g = min(guard, len(b))
        b[:g] = False
        s[:g] = False
    return b, s


# 策略代號 -> 向量化訊號產生器。沒列到的策略，optimizer 會退回事件式引擎。
SIGNAL_BUILDERS = {
    "ma_crossover": _ma_crossover,
    "rsi": _rsi,
    "macd": _macd,
    "bollinger": _bollinger,
    "donchian": _donchian,
    "stochastic": _stochastic,
    "momentum": _momentum,
    "williams_r": _williams_r,
    "adx_trend": _adx_trend,
}


def is_vectorized(strategy_key: str) -> bool:
    """這個策略有沒有向量化快路徑可用。"""
    return strategy_key in SIGNAL_BUILDERS


def run_vectorized(strategy_key: str, params: dict, df: pd.DataFrame, initial_cash: float) -> dict:
    """
    用向量化訊號跑回測，回傳與 _run_on_df 完全相同格式的績效 dict。
    呼叫前請先確認 is_vectorized(strategy_key) 為真。
    """
    builder = SIGNAL_BUILDERS[strategy_key]
    buy, sell = builder(df, params or {})
    # buy 優先（與事件式「先判斷買、再判斷賣」一致）
    signals = np.where(buy, Signal.BUY, np.where(sell, Signal.SELL, Signal.HOLD))
    return _simulate_from_signals(list(signals), df, initial_cash)
