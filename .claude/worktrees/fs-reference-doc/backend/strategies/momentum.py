"""
動量策略（Momentum / ROC, Rate of Change）
=========================================
最直覺的「順勢」策略：最近漲很多就追、跌很多就跑。

概念：
- ROC = (今天收盤 - N 天前收盤) / N 天前收盤 × 100%
- ROC 大於門檻（例如 +5%）→ 上漲動能強 → 買進(buy)
- ROC 小於負門檻（例如 -5%）→ 下跌動能強 → 賣出(sell)
- 在門檻之間 → 觀望(hold)
"""

import pandas as pd

from backend.strategies.base import BaseStrategy, Signal


class MomentumStrategy(BaseStrategy):
    name = "momentum"

    def generate_signal(self, df: pd.DataFrame) -> tuple[str, str]:
        period = self.params.get("period", 10)
        threshold = self.params.get("threshold", 5)  # 百分比門檻

        if len(df) < period + 1:
            return Signal.HOLD, f"資料不足（需要至少 {period + 1} 筆）"

        close = df["close"]
        past = float(close.iloc[-(period + 1)])
        now = float(close.iloc[-1])
        roc = (now - past) / past * 100 if past != 0 else 0.0

        if roc > threshold:
            return Signal.BUY, f"{period} 日動量 +{roc:.1f}%，追漲"
        if roc < -threshold:
            return Signal.SELL, f"{period} 日動量 {roc:.1f}%，殺跌"
        return Signal.HOLD, f"動量 {roc:.1f}% 在門檻內，維持觀望"
