"""
唐奇安通道突破策略（Donchian Channel Breakout）
==============================================
著名的「海龜交易法」核心，屬於「順勢」策略。

概念：
- 上軌 = 過去 N 天的最高價
- 下軌 = 過去 N 天的最低價
- 價格「突破上軌」（創 N 日新高）→ 趨勢向上 → 買進(buy)
- 價格「跌破下軌」（創 N 日新低）→ 趨勢向下 → 賣出(sell)

注意：計算上下軌時「不含今天」，才能判斷今天是不是突破。
"""

import pandas as pd

from backend.strategies.base import BaseStrategy, Signal


class DonchianStrategy(BaseStrategy):
    name = "donchian"

    def generate_signal(self, df: pd.DataFrame) -> tuple[str, str]:
        period = self.params.get("period", 20)

        if len(df) < period + 1:
            return Signal.HOLD, f"資料不足（需要至少 {period + 1} 筆）"

        # 有 high/low 就用，沒有（例如測試資料）就退而用 close
        high = df["high"] if "high" in df.columns else df["close"]
        low = df["low"] if "low" in df.columns else df["close"]
        close = df["close"]

        # 不含今天的前 period 日最高 / 最低
        upper = high.iloc[-(period + 1):-1].max()
        lower = low.iloc[-(period + 1):-1].min()
        price = float(close.iloc[-1])

        if price > upper:
            return Signal.BUY, f"突破 {period} 日高點 {upper:.2f}"
        if price < lower:
            return Signal.SELL, f"跌破 {period} 日低點 {lower:.2f}"
        return Signal.HOLD, "價格在通道內，維持觀望"
