"""
MACD 策略（Moving Average Convergence Divergence）
=================================================
MACD 是用「兩條不同速度的指數移動平均線」來抓趨勢轉變。

三個東西：
- MACD 線    = 快線(12日EMA) - 慢線(26日EMA)
- 訊號線     = MACD 線再取 9 日 EMA（比較平滑）
- 兩者的交叉就是買賣訊號

概念：
- MACD 線「向上穿越」訊號線 → 動能轉強 → 買進(buy)
- MACD 線「向下穿越」訊號線 → 動能轉弱 → 賣出(sell)
- 沒交叉 → 觀望(hold)

EMA（指數移動平均）跟普通平均差別：EMA 給「越近期的價格越高的權重」，
所以對最新變化更敏感。pandas 用 .ewm(span=N).mean() 計算。
"""

import pandas as pd

from backend.strategies.base import BaseStrategy, Signal


class MACDStrategy(BaseStrategy):
    name = "macd"

    def generate_signal(self, df: pd.DataFrame) -> tuple[str, str]:
        # 參數：快線、慢線、訊號線的期數（用業界最常見的 12/26/9）
        fast = self.params.get("fast", 12)
        slow = self.params.get("slow", 26)
        signal_period = self.params.get("signal", 9)

        # 至少要有慢線 + 訊號線的長度才算得準
        if len(df) < slow + signal_period:
            return Signal.HOLD, f"資料不足（需要至少 {slow + signal_period} 筆）"

        close = df["close"]

        # 1) 算快線與慢線的 EMA
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()

        # 2) MACD 線 = 快線 - 慢線
        macd_line = ema_fast - ema_slow

        # 3) 訊號線 = MACD 線的 EMA
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()

        # 4) 取今天、昨天，判斷有沒有交叉
        macd_today, macd_yesterday = macd_line.iloc[-1], macd_line.iloc[-2]
        sig_today, sig_yesterday = signal_line.iloc[-1], signal_line.iloc[-2]

        # 黃金交叉：昨天 MACD 在訊號線下方，今天升到上方
        if macd_yesterday <= sig_yesterday and macd_today > sig_today:
            return Signal.BUY, "MACD 線向上穿越訊號線（黃金交叉）"
        # 死亡交叉：昨天在上方，今天跌到下方
        if macd_yesterday >= sig_yesterday and macd_today < sig_today:
            return Signal.SELL, "MACD 線向下穿越訊號線（死亡交叉）"

        return Signal.HOLD, "MACD 無交叉，維持觀望"
