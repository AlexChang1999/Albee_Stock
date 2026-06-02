"""
均線交叉策略（Moving Average Crossover）
========================================
最經典、最好懂的入門策略。

概念：
- 算兩條移動平均線：一條「短期」(例如 5 日)，一條「長期」(例如 20 日)。
- 短均線「向上穿越」長均線 → 視為上漲動能轉強 → 買進(buy)。
- 短均線「向下穿越」長均線 → 視為下跌動能轉強 → 賣出(sell)。
- 其他情況 → 觀望(hold)。

「移動平均」就是「最近 N 天收盤價的平均」，用來把雜訊抹平、看趨勢。
我們用 pandas 的 rolling().mean() 計算，不需要額外的指標套件。
"""

import pandas as pd

from backend.strategies.base import BaseStrategy, Signal


class MACrossoverStrategy(BaseStrategy):
    name = "ma_crossover"

    def generate_signal(self, df: pd.DataFrame) -> tuple[str, str]:
        # 從參數讀取短/長均線天數，沒給就用預設值 5 和 20
        short_window = self.params.get("short_window", 5)
        long_window = self.params.get("long_window", 20)

        # 資料筆數不足以計算長均線時，先觀望
        if len(df) < long_window + 1:
            return Signal.HOLD, f"資料不足（需要至少 {long_window + 1} 筆）"

        # 計算短均線與長均線
        df = df.copy()
        df["ma_short"] = df["close"].rolling(window=short_window).mean()
        df["ma_long"] = df["close"].rolling(window=long_window).mean()

        # 取「今天」和「昨天」兩根，用來判斷有沒有發生交叉
        today = df.iloc[-1]
        yesterday = df.iloc[-2]

        # 黃金交叉：昨天短均線還在長均線下方，今天升到上方 → 買進
        golden_cross = (
            yesterday["ma_short"] <= yesterday["ma_long"]
            and today["ma_short"] > today["ma_long"]
        )
        # 死亡交叉：昨天短均線還在長均線上方，今天跌到下方 → 賣出
        death_cross = (
            yesterday["ma_short"] >= yesterday["ma_long"]
            and today["ma_short"] < today["ma_long"]
        )

        if golden_cross:
            return Signal.BUY, (
                f"黃金交叉：{short_window}日均線向上穿越{long_window}日均線"
            )
        if death_cross:
            return Signal.SELL, (
                f"死亡交叉：{short_window}日均線向下穿越{long_window}日均線"
            )

        return Signal.HOLD, "無交叉訊號，維持觀望"
