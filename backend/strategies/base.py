"""
策略基底類別
============
所有交易策略的共同父類別。

設計概念：
- 每個策略都要實作 generate_signal()，吃一份 K 線資料(DataFrame)，
  吐出一個「訊號」：買(buy) / 賣(sell) / 觀望(hold)。
- Bot 不需要知道策略內部怎麼算，只要拿到訊號就好（這就是「鬆耦合」）。
"""

from abc import ABC, abstractmethod

import pandas as pd


class Signal:
    """交易訊號的三種值，用常數避免打錯字。"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class BaseStrategy(ABC):
    """向量化策略基底。新策略請繼承這個類別並實作 generate_signal()。"""

    # 策略名稱（子類別覆寫）
    name: str = "base"

    def __init__(self, params: dict | None = None) -> None:
        # params 是策略參數，例如均線交叉的 {"short_window": 5, "long_window": 20}
        self.params = params or {}

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame) -> tuple[str, str]:
        """
        根據 K 線資料產生交易訊號。
        :param df: 含 close 欄位的 K 線資料（時間由舊到新）
        :return: (訊號, 原因說明)
                 訊號為 Signal.BUY / Signal.SELL / Signal.HOLD
        """
        raise NotImplementedError

    # ---------- 統一介面（讓回測 / 實盤對兩種策略基底一視同仁）----------
    def produce_signals(self, df: pd.DataFrame) -> tuple[list[str], list[str]]:
        """
        在整段 df 上逐根產生訊號序列（回測引擎用）。

        向量化策略的預設實作＝逐根呼叫 generate_signal、只餵「到第 i 根為止」的資料
        （不偷看未來）。這段邏輯原本寫在 backtest_engine._run_on_df，收進這裡當預設，
        讓 ScriptStrategy 能用同一個入口覆寫成事件式（見 ScriptStrategy.produce_signals）。

        :return: (signals, reasons)，兩串等長、與 df 對齊。
        """
        signals: list[str] = []
        reasons: list[str] = []
        for i in range(len(df)):
            sig, reason = self.generate_signal(df.iloc[: i + 1])
            signals.append(sig)
            reasons.append(reason)
        return signals, reasons

    def evaluate_last(self, df: pd.DataFrame) -> tuple[str, str]:
        """
        只取「最新一根」的訊號（實盤 Bot 每輪用這個）。

        向量化策略預設＝直接 generate_signal(df)（只看最後一根，最省）。
        ScriptStrategy 覆寫成「重播到最後一根、回該根動作」。
        """
        return self.generate_signal(df)


class ScriptStrategy(BaseStrategy):
    """
    事件驅動策略基底（採納自 QuantDinger 的 ScriptStrategy）。
    繼承它、實作 on_bar(ctx, bar)，用 ctx.buy()/sell()/close() 登記買賣意圖。

    與向量化 BaseStrategy 的差別：
    - 向量化：每根回一個訊號字串（無狀態，純函式）。
    - 事件式：on_bar 可讀 ctx 的狀態（in_position / bars_held / history）再決定動作，
      寫起來像「真的在盤中逐根做決策」，適合有狀態的進出場邏輯。
    - 成交仍走同一個 _simulate_from_signals 核心（次根開盤 + 含成本），不分岔。

    為相容既有「策略都有 generate_signal」的呼叫端（如圖表指標 / 單點查詢），
    這裡用 produce_signals 重播後取最後一根，提供 generate_signal 的預設實作。
    """

    name = "script_base"

    def on_init(self, ctx) -> None:  # noqa: ANN001 — ctx 是 BacktestContext，避免循環匯入不標型別
        """回測 / 重播開始時呼叫一次（選填覆寫，例如初始化內部狀態）。預設不做事。"""
        return None

    @abstractmethod
    def on_bar(self, ctx, bar) -> None:  # noqa: ANN001
        """
        每根 K 線呼叫一次。讀 ctx 狀態 + bar（這根 K 線），用 ctx.buy()/sell()/close() 登記意圖。
        不回傳值——動作透過 ctx 登記。
        """
        raise NotImplementedError

    def produce_signals(self, df: pd.DataFrame) -> tuple[list[str], list[str]]:
        """逐根驅動 on_bar，把 ctx 登記的意圖壓成全進全出訊號序列（交給共用成交核心）。"""
        # 延遲匯入避免 base ←→ context 循環匯入
        from backend.strategies.context import BacktestContext

        ctx = BacktestContext(df)
        self.on_init(ctx)
        signals: list[str] = []
        reasons: list[str] = []
        for i in range(len(df)):
            ctx._begin_bar(i)
            self.on_bar(ctx, ctx.bar)
            sig, reason = ctx._commit_bar()
            signals.append(sig)
            reasons.append(reason)
        return signals, reasons

    def evaluate_last(self, df: pd.DataFrame) -> tuple[str, str]:
        """實盤每輪：重播整段 df、回最後一根的動作（冷啟重播，不依賴跨輪記憶體狀態）。"""
        signals, reasons = self.produce_signals(df)
        if not signals:
            return Signal.HOLD, "資料不足"
        return signals[-1], reasons[-1]

    def generate_signal(self, df: pd.DataFrame) -> tuple[str, str]:
        """相容用：等同 evaluate_last（重播取最後一根）。"""
        return self.evaluate_last(df)
