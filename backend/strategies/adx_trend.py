"""
ADX 趨勢策略（Average Directional Index）── 用 pandas-ta-classic 示範
======================================================================
ADX 是經典的「趨勢強度」指標，搭配 +DI / −DI 判斷方向：

概念：
- ADX 衡量「趨勢有多強」（不分漲跌）。ADX 低＝盤整、別追；ADX 高＝趨勢明確、可順勢。
- +DI（上升動向）在 −DI 之上 → 多方佔優；反之空方佔優。
- 規則：
  - ADX > 門檻 且 +DI 在 −DI 之上 → 上升趨勢成形 → 買進(buy)
  - ADX > 門檻 且 −DI 在 +DI 之上 → 下降趨勢成形 → 賣出(sell)
  - ADX ≤ 門檻（盤整、方向不明） → 觀望(hold)

這支是「導入 pandas-ta-classic」的示範策略：指標計算交給 indicators.adx_components，
策略本身只負責「拿到指標後怎麼下決定」，與其他策略同一個 generate_signal 介面（鬆耦合）。
"""

import pandas as pd

from backend.strategies.base import BaseStrategy, Signal
from backend.strategies.indicators import adx_components


class ADXTrendStrategy(BaseStrategy):
    name = "adx_trend"

    def generate_signal(self, df: pd.DataFrame) -> tuple[str, str]:
        # 參數：ADX 回看期數、判定「有趨勢」的門檻（沒給用常見預設）
        period = self.params.get("period", 14)
        adx_threshold = self.params.get("adx_threshold", 25)

        # ADX 需要約 2×period 筆資料才穩定
        if len(df) < period * 2:
            return Signal.HOLD, f"資料不足（建議至少 {period * 2} 筆）"

        adx, di_plus, di_minus = adx_components(df, length=period)
        if adx.empty or adx.isna().all():
            return Signal.HOLD, "ADX 尚無有效值，維持觀望"

        last_adx = adx.iloc[-1]
        last_dip = di_plus.iloc[-1]
        last_dim = di_minus.iloc[-1]

        # 任一為 NaN（暖機期）→ 觀望
        if pd.isna(last_adx) or pd.isna(last_dip) or pd.isna(last_dim):
            return Signal.HOLD, "指標暖機中，維持觀望"

        # 趨勢不夠強 → 不追
        if last_adx <= adx_threshold:
            return Signal.HOLD, f"ADX={last_adx:.1f} ≤ {adx_threshold}，盤整不追"

        # 趨勢夠強，看方向
        if last_dip > last_dim:
            return Signal.BUY, f"ADX={last_adx:.1f} 強勢且 +DI>−DI，上升趨勢，買進"
        if last_dim > last_dip:
            return Signal.SELL, f"ADX={last_adx:.1f} 強勢且 −DI>+DI，下降趨勢，賣出"
        return Signal.HOLD, f"ADX={last_adx:.1f} 強，但 +DI≈−DI 方向不明，觀望"
