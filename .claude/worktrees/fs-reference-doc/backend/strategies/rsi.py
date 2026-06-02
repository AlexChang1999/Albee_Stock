"""
RSI 策略（Relative Strength Index，相對強弱指標）
================================================
RSI 是一個 0~100 的數字，用來看股票是「超買」還是「超賣」。

概念：
- RSI 很低（例如 < 30）→ 代表近期跌太多、可能「超賣」→ 預期反彈 → 買進(buy)
- RSI 很高（例如 > 70）→ 代表近期漲太多、可能「超買」→ 預期回檔 → 賣出(sell)
- 中間 → 觀望(hold)

計算方式（白話）：
- 看最近 N 天，把「上漲的幅度」和「下跌的幅度」分別平均。
- 漲得多、跌得少 → RSI 高；反之 → RSI 低。
"""

import pandas as pd

from backend.strategies.base import BaseStrategy, Signal


class RSIStrategy(BaseStrategy):
    name = "rsi"

    def generate_signal(self, df: pd.DataFrame) -> tuple[str, str]:
        # 參數：RSI 期數、超買線、超賣線（沒給就用常見預設值）
        period = self.params.get("period", 14)
        overbought = self.params.get("overbought", 70)
        oversold = self.params.get("oversold", 30)

        # 計算 RSI 至少需要 period + 1 筆資料
        if len(df) < period + 1:
            return Signal.HOLD, f"資料不足（需要至少 {period + 1} 筆）"

        close = df["close"]

        # 1) 算每天相對前一天的漲跌幅
        delta = close.diff()

        # 2) 把「上漲」和「下跌」分開
        #    clip(lower=0)：負的變 0，只留上漲；下跌同理取絕對值
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        # 3) 分別取最近 period 天的平均
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()

        # 4) RS = 平均漲幅 / 平均跌幅；RSI = 100 - 100/(1+RS)
        #    avg_loss 為 0 時（完全沒跌）直接視為 RSI=100
        last_gain = avg_gain.iloc[-1]
        last_loss = avg_loss.iloc[-1]
        if last_loss == 0:
            rsi = 100.0
        else:
            rs = last_gain / last_loss
            rsi = 100 - (100 / (1 + rs))

        # 5) 依 RSI 判斷訊號
        if rsi < oversold:
            return Signal.BUY, f"RSI={rsi:.1f} 低於 {oversold}，超賣，預期反彈"
        if rsi > overbought:
            return Signal.SELL, f"RSI={rsi:.1f} 高於 {overbought}，超買，預期回檔"
        return Signal.HOLD, f"RSI={rsi:.1f} 在區間內，維持觀望"
