"""
事件驅動策略的執行脈絡（BacktestContext）── 採納自 QuantDinger 的 ScriptStrategy
=============================================================================
ScriptStrategy 的 on_bar(ctx, bar) 透過這個 ctx 物件「登記買賣意圖」並讀目前狀態。

刻意設計成「只記意圖、不自己成交」：on_bar 呼叫 ctx.buy()/sell()/close() 只是標記
這一根想做什麼，真正的成交（次根開盤價 + 含成本）仍交給回測引擎那唯一的成交核心
_simulate_from_signals 處理——這樣 ScriptStrategy 與既有向量化策略走「同一條成交路徑」，
不分岔，誠實守住「回測=實盤」鐵則。

全進全出語意（第一版）：
- ctx.buy() 只在「目前空手」時有意義（已持倉再 buy 會被引擎忽略）。
- ctx.sell() / ctx.close() 只在「目前持倉」時有意義。
- 同一根多次呼叫，以最後一次為準。
- ctx 自己也用同一套全進全出規則推進 in_position / bars_held，讓 on_bar 裡讀得到正確狀態
  （例如「if not ctx.in_position: ctx.buy()」）。
"""

import pandas as pd

from backend.strategies.base import Signal


class BacktestContext:
    """一次回測 / 重播期間，逐根餵給 ScriptStrategy.on_bar 的狀態與動作介面。"""

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df.reset_index(drop=True)
        # --- 對外可讀狀態 ---
        self.index: int = 0          # 目前在第幾根（0-based）
        self.bar: pd.Series | None = None  # 目前這根 K 線（含 open/high/low/close/volume...）
        self.in_position: bool = False     # 目前是否持倉（全進全出，布林即足夠）
        self.bars_held: int = 0            # 持倉已經幾根（進場當根算 0）
        # --- 內部：這一根登記的意圖 ---
        self._pending_action: str = "hold"
        self._pending_reason: str = ""

    # ---------- 給引擎用的逐根驅動（前綴底線＝內部 API，策略別碰）----------
    def _begin_bar(self, i: int) -> None:
        """引擎在呼叫 on_bar 前，先把 ctx 切到第 i 根並清空上一根的意圖。"""
        self.index = i
        self.bar = self._df.iloc[i]
        self._pending_action = "hold"
        self._pending_reason = ""

    def _commit_bar(self) -> tuple[str, str]:
        """
        引擎在 on_bar 後呼叫：依全進全出規則決定這一根「實際生效」的訊號，
        同步推進 in_position / bars_held，回 (Signal 值, 理由) 給引擎收進訊號序列。
        """
        action = self._pending_action
        reason = self._pending_reason

        if action == "buy" and not self.in_position:
            self.in_position = True
            self.bars_held = 0
            return Signal.BUY, reason
        if action in ("sell", "close") and self.in_position:
            self.in_position = False
            self.bars_held = 0
            return Signal.SELL, reason

        # 沒有有效換手：若持倉中，這一根多抱了一根
        if self.in_position:
            self.bars_held += 1
        return Signal.HOLD, reason

    # ---------- 給策略 on_bar 用的動作 API ----------
    def buy(self, reason: str = "") -> None:
        """登記「這一根想買進」（空手時才會真的成交）。"""
        self._pending_action = "buy"
        self._pending_reason = reason or "ScriptStrategy 買進訊號"

    def sell(self, reason: str = "") -> None:
        """登記「這一根想賣出 / 平倉」（持倉時才會真的成交）。"""
        self._pending_action = "sell"
        self._pending_reason = reason or "ScriptStrategy 賣出訊號"

    def close(self, reason: str = "") -> None:
        """平倉（語意同 sell，全進全出版兩者等價；保留以對齊 QuantDinger 的 ctx.close_position）。"""
        self.sell(reason or "ScriptStrategy 平倉")

    def hold(self, reason: str = "") -> None:
        """明確表示這一根不動作（不呼叫也預設 hold，提供只為可讀性）。"""
        self._pending_action = "hold"
        self._pending_reason = reason

    # ---------- 給策略讀的便利屬性 ----------
    @property
    def history(self) -> pd.DataFrame:
        """到目前這根為止（含本根）的 K 線切片，給策略自己算指標用（不偷看未來）。"""
        return self._df.iloc[: self.index + 1]
