"""
KD 隨機指標策略（Stochastic Oscillator）
=======================================
KD 用「收盤價在最近高低區間的相對位置」判斷強弱。

兩條線：
- %K（快線）= 100 × (收盤 - N日最低) / (N日最高 - N日最低)
- %D（慢線）= %K 的 M 日平均（較平滑）

概念（用交叉）：
- %K 由下「向上穿越」%D → 轉強 → 買進(buy)
- %K 由上「向下穿越」%D → 轉弱 → 賣出(sell)
"""

import pandas as pd

from backend.strategies.base import BaseStrategy, Signal


class StochasticStrategy(BaseStrategy):
    name = "stochastic"

    def generate_signal(self, df: pd.DataFrame) -> tuple[str, str]:
        k_period = self.params.get("k_period", 14)
        d_period = self.params.get("d_period", 3)

        if len(df) < k_period + d_period:
            return Signal.HOLD, f"資料不足（需要至少 {k_period + d_period} 筆）"

        high = df["high"] if "high" in df.columns else df["close"]
        low = df["low"] if "low" in df.columns else df["close"]
        close = df["close"]

        low_min = low.rolling(window=k_period).min()
        high_max = high.rolling(window=k_period).max()

        # 區間為 0（價格沒動）時，避免除以零
        rng = (high_max - low_min).replace(0, 1e-9)
        k = 100 * (close - low_min) / rng
        d = k.rolling(window=d_period).mean()

        k_today, k_yest = k.iloc[-1], k.iloc[-2]
        d_today, d_yest = d.iloc[-1], d.iloc[-2]

        if k_yest <= d_yest and k_today > d_today:
            return Signal.BUY, f"KD 黃金交叉（K={k_today:.1f}）"
        if k_yest >= d_yest and k_today < d_today:
            return Signal.SELL, f"KD 死亡交叉（K={k_today:.1f}）"
        return Signal.HOLD, "KD 無交叉，維持觀望"
