"""
<中文策略名>策略（<English Name>，<縮寫>）
================================================
<一兩句白話：這指標在看什麼、為什麼能當買賣訊號>

概念：
- <條件A>（例如指標 < 下限）→ 超賣/低估 → 預期反彈 → 買進(buy)
- <條件B>（例如指標 > 上限）→ 超買/高估 → 預期回檔 → 賣出(sell)
- 中間 → 觀望(hold)

計算方式（白話）：
- <用 pandas 怎麼算，一步步講人話。不要 ta-lib。>
"""

import pandas as pd

from backend.strategies.base import BaseStrategy, Signal


class TemplateStrategy(BaseStrategy):  # <-- 改成 <PascalCase>Strategy
    name = "template"  # <-- 改成 snake_case 註冊鍵，必須與 __init__.py 的鍵一致

    def generate_signal(self, df: pd.DataFrame) -> tuple[str, str]:
        # 1) 取參數（沒給就用常見預設值，別寫死成過擬合的怪數字）
        period = self.params.get("period", 14)

        # 2) 資料不足先 HOLD（算指標前的安全檢查；有 diff 的要 +1）
        if len(df) < period + 1:
            return Signal.HOLD, f"資料不足（需要至少 {period + 1} 筆）"

        close = df["close"]

        # 3) 純 pandas 算指標（rolling / ewm / diff / clip ...）
        #    範例：算最近 period 的某種值，取最後一筆
        indicator = close.rolling(window=period).mean().iloc[-1]  # <-- 換成真正的指標算式

        # 4) 依指標判斷訊號（回中文原因，方便前端/通知顯示）
        #    把下面條件換成你的策略邏輯
        if indicator < close.iloc[-1]:
            return Signal.BUY, f"指標={indicator:.2f}，<觸發買進的白話原因>"
        if indicator > close.iloc[-1]:
            return Signal.SELL, f"指標={indicator:.2f}，<觸發賣出的白話原因>"
        return Signal.HOLD, f"指標={indicator:.2f}，無明確訊號，維持觀望"
