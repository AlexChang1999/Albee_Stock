"""
市場狀態特徵工程（Regime Features）── Phase 7 step-01
======================================================
把「現在市場長什麼樣」量化成一組**數字特徵**，當作後續「狀態分類器」
（step-02）與「自適應選策略」（step-03）的輸入。

設計鐵則（對齊 Phase 6「回測 = 實盤」與護欄合約）：
- **純 pandas、無 ML**：每根 K 棒算得出來，看得懂、可除錯。
- **無未來函數（no look-ahead）**：只用到「截至最後一根」的資料，所以
  對 `df.iloc[:i+1]` 與完整 `df` 在第 i 根算出的特徵一致（與回測 walk-forward 同款紀律）。
- **特徵集中一處**：回測層與實盤層共用同一個 `compute_features`，避免雙份定義分岔。
- **重用既有**：`volume_ratio` 直接用 `screener` 的，不重造。

特徵不是越多越好——每多一個就給下游分類器多一個過擬合自由度。
這裡先放 6 個有直覺、可解釋的，別一次塞 30 個。
"""

import numpy as np
import pandas as pd

from backend.services.screener import volume_ratio
from backend.strategies.indicators import adx_components


# 一年的交易日數，用來把日報酬標準差年化
_TRADING_DAYS = 252


def _return_over(close: pd.Series, lookback: int) -> float | None:
    """近 lookback 日報酬率：close[-1] / close[-1-lookback] - 1。資料不足回 None。"""
    closes = close.dropna()
    if len(closes) < lookback + 1:
        return None
    past = float(closes.iloc[-1 - lookback])
    if past == 0:
        return None
    return float(closes.iloc[-1] / past - 1)


def _volatility(close: pd.Series, window: int = 20) -> float | None:
    """近 window 日「日報酬標準差」的年化值（高波動 / 低波動狀態）。資料不足回 None。"""
    closes = close.dropna()
    if len(closes) < window + 1:
        return None
    daily_ret = closes.pct_change().dropna().iloc[-window:]
    if len(daily_ret) < 2:
        return None
    return float(daily_ret.std(ddof=1) * np.sqrt(_TRADING_DAYS))


def _trend_strength(df: pd.DataFrame, length: int = 14) -> float | None:
    """
    趨勢「強度」= ADX 最新值（不分方向；越大代表趨勢越明確、盤整時低）。
    重用 indicators.adx_components，避免重造 ADX。資料不足 / 暖機期回 None。
    """
    if len(df) < length * 2:
        return None
    adx, _, _ = adx_components(df, length=length)
    if adx is None or adx.empty:
        return None
    last = adx.iloc[-1]
    return None if pd.isna(last) else float(last)


def _atr_pct(df: pd.DataFrame, window: int = 14) -> float | None:
    """
    ATR ÷ 價格（波動幅度，給止損 / 部位用）。
    ATR = 近 window 日 True Range 的均值；True Range = max(高低差, |高−昨收|, |低−昨收|)。
    缺 high/low 就退回用 close 當高低（防呆，與既有指標封裝同款）。
    """
    close = df["close"].dropna()
    if len(close) < window + 1:
        return None
    high = df["high"] if "high" in df.columns else df["close"]
    low = df["low"] if "low" in df.columns else df["close"]
    prev_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = true_range.dropna().iloc[-window:].mean()
    price = float(close.iloc[-1])
    if not atr or price <= 0:
        return None
    return float(atr / price)


def _range_position(df: pd.DataFrame, window: int = 20) -> float | None:
    """
    收盤在近 window 日高低區間的位置（唐奇安 %）：
    0 = 貼著區間低點（剛破底 / 回檔深），1 = 貼著高點（逼近突破）。
    缺 high/low 就用 close。資料不足或區間為 0（無波動）回 None。
    """
    close = df["close"].dropna()
    if len(close) < window:
        return None
    high = df["high"] if "high" in df.columns else df["close"]
    low = df["low"] if "low" in df.columns else df["close"]
    hi = float(high.iloc[-window:].max())
    lo = float(low.iloc[-window:].min())
    if hi <= lo:
        return None
    return float((float(close.iloc[-1]) - lo) / (hi - lo))


def compute_features(df: pd.DataFrame) -> dict:
    """
    吃一段 K 線 DataFrame（欄位小寫 open/high/low/close/volume），
    回「截至最後一根」的一組市場狀態特徵。

    任一特徵資料不足時，該鍵的值為 None（不崩、上層自行決定怎麼處理）。

    回傳鍵：
    - volume_ratio   ：最新量 ÷ 近 20 日均量（量能爆不爆）
    - return_5d      ：近 5 日報酬率
    - return_20d     ：近 20 日報酬率
    - volatility_20d ：近 20 日日報酬標準差（年化）
    - trend_strength ：ADX 最新值（趨勢強度，不分方向）
    - atr_pct        ：ATR ÷ 價格（波動幅度）
    - range_position ：收盤在近 20 日高低區間的位置（0~1）

    「量大滯漲」的日子：volume_ratio 高，且 return_5d ≈ 0（量價背離）。
    """
    empty = {
        "volume_ratio": None,
        "return_5d": None,
        "return_20d": None,
        "volatility_20d": None,
        "trend_strength": None,
        "atr_pct": None,
        "range_position": None,
    }
    if df is None or df.empty or "close" not in df:
        # 連收盤都沒有就回全 None，保證上層拿到一致格式
        return empty

    close = df["close"]
    return {
        "volume_ratio": volume_ratio(df),
        "return_5d": _return_over(close, 5),
        "return_20d": _return_over(close, 20),
        "volatility_20d": _volatility(close, 20),
        "trend_strength": _trend_strength(df, 14),
        "atr_pct": _atr_pct(df, 14),
        "range_position": _range_position(df, 20),
    }
