"""
布林通道策略（Bollinger Bands）
==============================
布林通道是「一條中軌 + 上下兩條軌道」組成的價格通道。

三條線：
- 中軌 = N 日移動平均（預設 20 日）
- 上軌 = 中軌 + K 倍標準差（預設 K=2）
- 下軌 = 中軌 - K 倍標準差

「標準差」代表價格波動的大小：波動大，通道就寬；波動小，通道就窄。

概念（這裡用「均值回歸」的玩法）：
- 價格跌破「下軌」→ 偏離太多、可能超跌 → 買進(buy)，賭它回到中間
- 價格突破「上軌」→ 漲過頭、可能超漲 → 賣出(sell)
- 在通道內 → 觀望(hold)
"""

import pandas as pd

from backend.strategies.base import BaseStrategy, Signal


class BollingerStrategy(BaseStrategy):
    name = "bollinger"

    def generate_signal(self, df: pd.DataFrame) -> tuple[str, str]:
        # 參數：期數、標準差倍數
        period = self.params.get("period", 20)
        num_std = self.params.get("num_std", 2)

        if len(df) < period:
            return Signal.HOLD, f"資料不足（需要至少 {period} 筆）"

        close = df["close"]

        # 1) 中軌：N 日移動平均
        middle = close.rolling(window=period).mean()
        # 2) 標準差：N 日價格的波動程度
        std = close.rolling(window=period).std()

        # 3) 上下軌
        upper = middle + num_std * std
        lower = middle - num_std * std

        # 取最新一天的價格與上下軌來比較
        price = close.iloc[-1]
        last_upper = upper.iloc[-1]
        last_lower = lower.iloc[-1]

        if price < last_lower:
            return Signal.BUY, (
                f"價格 {price:.2f} 跌破下軌 {last_lower:.2f}，可能超跌"
            )
        if price > last_upper:
            return Signal.SELL, (
                f"價格 {price:.2f} 突破上軌 {last_upper:.2f}，可能超漲"
            )
        return Signal.HOLD, "價格在通道內，維持觀望"
