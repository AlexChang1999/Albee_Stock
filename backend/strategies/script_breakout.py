"""
範例事件驅動策略：突破進場 + 有狀態續抱（ScriptStrategy 示範）
================================================================
這支策略示範「事件驅動 ScriptStrategy」怎麼寫——重點是 on_bar 裡讀得到 ctx 的狀態
（in_position / bars_held / history），像真的在盤中逐根做決策。

策略邏輯（全進全出）：
- 空手時：今天收盤 > 前 lookback 根的最高收盤 → 突破，買進。
- 持倉時（任一觸發就賣）：
  1. 今天收盤 < 前 exit_lookback 根的最低收盤 → 跌破，出場；
  2. hold_bars > 0 且已抱滿 hold_bars 根 → 時間到，出場。

對比向量化策略：同樣的邏輯用 generate_signal 寫會比較彆扭（要自己從 df 回推「現在是不是
持倉中、抱了幾根」）；ScriptStrategy 直接讀 ctx.in_position / ctx.bars_held 就好。
成交仍走回測引擎那唯一的成交核心（次根開盤 + 含成本），與其他策略零分岔。
"""

from backend.strategies.base import ScriptStrategy


class ScriptBreakoutStrategy(ScriptStrategy):
    name = "script_breakout"

    def on_bar(self, ctx, bar) -> None:
        lookback = int(self.params.get("lookback", 20))
        exit_lookback = int(self.params.get("exit_lookback", 10))
        hold_bars = int(self.params.get("hold_bars", 0))  # 0 = 不靠時間出場

        closes = ctx.history["close"]
        # 資料不足以判斷突破：什麼都不做（預設 hold）
        if len(closes) < lookback + 1:
            return

        today = float(closes.iloc[-1])

        if not ctx.in_position:
            # 前 lookback 根（不含今天）的最高收盤
            prior_high = float(closes.iloc[-(lookback + 1):-1].max())
            if today > prior_high:
                ctx.buy(f"突破前 {lookback} 根高點 {prior_high:.2f}")
            return

        # --- 持倉中：跌破出場 或 抱滿出場 ---
        if len(closes) >= exit_lookback + 1:
            prior_low = float(closes.iloc[-(exit_lookback + 1):-1].min())
            if today < prior_low:
                ctx.sell(f"跌破前 {exit_lookback} 根低點 {prior_low:.2f}")
                return

        if hold_bars > 0 and ctx.bars_held >= hold_bars:
            ctx.sell(f"已抱滿 {hold_bars} 根，時間出場")
