"""
威廉指標策略（Williams %R）
================================================
Williams %R 是一個 -100~0 的數字，用來看股票是「超買」還是「超賣」，
概念跟 RSI 很像，只是數值範圍不同。

概念：
- %R 很低（例如 < -80）→ 收盤貼近近期最低 → 超賣 → 預期反彈 → 買進(buy)
- %R 很高（例如 > -20）→ 收盤貼近近期最高 → 超買 → 預期回檔 → 賣出(sell)
- 中間 → 觀望(hold)

計算方式（白話）：
- 看最近 N 天的「最高」和「最低」（本專案只有 close 欄，用 close 的
  rolling 高低點近似）。
- %R = (最高 - 今收) / (最高 - 最低) × -100
- 今收貼近最高 → %R 接近 0（超買）；貼近最低 → %R 接近 -100（超賣）。
"""

import pandas as pd

from backend.strategies.base import BaseStrategy, Signal


class WilliamsRStrategy(BaseStrategy):
    name = "williams_r"

    def generate_signal(self, df: pd.DataFrame) -> tuple[str, str]:
        # 參數：回看期數、超買線、超賣線（沒給就用常見預設值）
        period = self.params.get("period", 14)
        overbought = self.params.get("overbought", -20)
        oversold = self.params.get("oversold", -80)

        # 算 %R 至少需要 period 筆資料
        if len(df) < period:
            return Signal.HOLD, f"資料不足（需要至少 {period} 筆）"

        close = df["close"]

        # 1) 近 period 天的最高、最低（用 close 近似高低點）
        highest = close.rolling(window=period).max().iloc[-1]
        lowest = close.rolling(window=period).min().iloc[-1]
        last_close = close.iloc[-1]

        # 2) 防呆：區間完全沒波動（最高==最低）→ 無從判斷，觀望
        if highest == lowest:
            return Signal.HOLD, "近期價格無波動，維持觀望"

        # 3) 算 Williams %R
        percent_r = (highest - last_close) / (highest - lowest) * -100

        # 4) 依 %R 判斷訊號
        if percent_r < oversold:
            return Signal.BUY, f"%R={percent_r:.1f} 低於 {oversold}，超賣，預期反彈"
        if percent_r > overbought:
            return Signal.SELL, f"%R={percent_r:.1f} 高於 {overbought}，超買，預期回檔"
        return Signal.HOLD, f"%R={percent_r:.1f} 在區間內，維持觀望"
