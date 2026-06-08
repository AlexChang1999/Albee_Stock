"""
策略組合引擎（CompositeStrategy）── Phase 8 step-03
====================================================
把多個**已驗證**子策略的訊號，聚合成一個複合策略，形成新的、可回測的單一策略。
這是使用者願景「蒐集很多策略 → 整合 / 結合」的程式落地。

複合策略就是一個普通的 BaseStrategy：照走既有 _run_on_df / Bot 流程，零特例。
子策略一律透過 get_strategy 取既有 8 種，不重寫任何指標；所有子策略吃**同一份** df
（呼應「回測 = 實盤、資料只抓一次」），不各自抓資料。

三種聚合方式（先簡單，證明有效再說，不上機器學習 stacking）：
- vote        ：多數同向才出手（少數服從多數，平手觀望）。
- weighted    ：依各子策略 OOS EV 給權重，加權多數決。
- regime_switch：依 Phase 7 當下市場狀態，選用對應的子策略（與 step-03 Phase 7 銜接）。

params 結構（存進 StrategyKnowledge.params）：
{
  "members": [{"strategy_key": "rsi", "params": {...}, "weight": 1.0}, ...],
  "method": "vote" | "weighted" | "regime_switch",
  "regime_strategies": {"trending": "donchian", "ranging": "rsi"}   # 只有 regime_switch 用
}
"""

from backend.strategies.base import BaseStrategy, Signal

# 允許的聚合方式（驗證用單一來源）
_METHODS = {"vote", "weighted", "regime_switch"}


def validate_composite_params(params: dict) -> None:
    """
    驗證組合策略參數結構（給「寫入知識庫前」的把關用；不合法就拋 ValueError、訊息白話）。

    為何要在「存進去前」驗，而不是等執行時：爛組合若被存進庫，等到實盤 Bot 跑才爆，
    難追、又會弄崩整個 Bot。在 API 寫入閘擋下，爛組合根本進不了庫。

    規則：
    - method 必須是 vote / weighted / regime_switch。
    - members 必須是非空清單，每筆是 dict 且 strategy_key 為既有策略；
      子策略不可又是 composite（禁巢狀，避免無限遞迴）。
    - regime_switch 時，regime_strategies 必須是非空 dict，且值都是既有策略代號。

    :raises ValueError: 任何一條不符
    """
    # 延遲匯入避免循環依賴（strategies/__init__ 會匯入本模組）
    from backend.strategies import STRATEGY_REGISTRY

    if not isinstance(params, dict):
        raise ValueError("組合策略參數必須是物件（dict）")

    method = params.get("method", "vote")
    if method not in _METHODS:
        raise ValueError(f"method 必須是 {sorted(_METHODS)}，收到：{method!r}")

    members = params.get("members")
    if not isinstance(members, list) or not members:
        raise ValueError("members 必須是非空清單，至少要有一個子策略")

    for i, m in enumerate(members):
        if not isinstance(m, dict):
            raise ValueError(f"members[{i}] 必須是物件（dict）")
        key = m.get("strategy_key")
        if key not in STRATEGY_REGISTRY:
            raise ValueError(
                f"members[{i}] 的 strategy_key 無效：{key!r}，"
                f"只能用既有策略：{list(STRATEGY_REGISTRY.keys())}"
            )
        if key == "composite":
            raise ValueError(f"members[{i}] 不可巢狀使用 composite（避免無限遞迴）")

    if method == "regime_switch":
        rs = params.get("regime_strategies")
        if not isinstance(rs, dict) or not rs:
            raise ValueError("method=regime_switch 時，regime_strategies 必須是非空對照表")
        for regime, key in rs.items():
            if key not in STRATEGY_REGISTRY:
                raise ValueError(
                    f"regime_strategies[{regime!r}] 的策略代號無效：{key!r}"
                )


def aggregate_signals(signals: list, method: str = "vote", weights: list | None = None) -> str:
    """
    把多個子策略訊號聚合成一個（純函式，好單測）。

    vote     ：每票等重，BUY / SELL 各計票，多者勝；平手或都為 0 → HOLD。
    weighted ：用對應 weights 當票重（缺權重視為 1），其餘同 vote。
    （HOLD 不投任何一邊；全 HOLD → HOLD。）

    :param signals: 子策略訊號清單，每格是 Signal.BUY / SELL / HOLD
    :param method:  "vote" 或 "weighted"
    :param weights: 與 signals 對齊的權重清單（method="weighted" 時用；None 視為全 1）
    :return: 聚合後的單一 Signal
    """
    if not signals:
        return Signal.HOLD

    buy_w = 0.0
    sell_w = 0.0
    for i, sig in enumerate(signals):
        if method == "weighted" and weights is not None and i < len(weights):
            w = float(weights[i])
        else:
            w = 1.0
        if sig == Signal.BUY:
            buy_w += w
        elif sig == Signal.SELL:
            sell_w += w

    if buy_w > sell_w:
        return Signal.BUY
    if sell_w > buy_w:
        return Signal.SELL
    return Signal.HOLD  # 平手（含全 HOLD）→ 保守觀望


class CompositeStrategy(BaseStrategy):
    """複合策略：吃子策略清單 + 聚合方式，generate_signal 內部呼叫各子策略再聚合。"""

    name = "composite"

    def __init__(self, params: dict | None = None) -> None:
        super().__init__(params)
        p = self.params or {}
        self.members = p.get("members", []) or []
        self.method = p.get("method", "vote")
        # regime_switch 用：狀態 → 子策略代號
        self.regime_strategies = p.get("regime_strategies", {}) or {}

    def _sub_signal(self, strategy_key: str, sub_params: dict, df) -> tuple[str, str]:
        """取某個子策略對同一份 df 的訊號（透過既有 get_strategy，不重寫指標）。

        子策略代號非法或內部出錯時，回保守 HOLD 而非往上拋例外——避免一個壞子策略
        把整個 Bot（bot_manager 實盤迴圈）弄崩。寫入前已有 validate_composite_params 把關，
        這層只是執行期的安全網。
        """
        # 延遲匯入避免循環依賴（__init__ 會匯入本模組）
        from backend.strategies import get_strategy

        try:
            sub = get_strategy(strategy_key, sub_params or {})
            return sub.generate_signal(df)
        except Exception as e:  # noqa: BLE001 — 任何子策略錯誤都降級為觀望，不拖垮整組
            return Signal.HOLD, f"子策略 {strategy_key} 失效：{e}"

    def generate_signal(self, df) -> tuple[str, str]:
        """聚合子策略訊號；無子策略時保守觀望。"""
        if not self.members:
            return Signal.HOLD, "組合無子策略"

        # --- 狀態切換：依當下市場狀態挑一個子策略來用 ---
        if self.method == "regime_switch":
            from backend.services.regime import classify_regime
            from backend.services.regime_features import compute_features

            regime = classify_regime(compute_features(df))
            key = self.regime_strategies.get(regime)
            if not key:
                return Signal.HOLD, f"狀態 {regime} 無對應子策略，觀望"
            # 沿用該子策略在 members 裡登記的參數（找不到就空參數）
            sub_params = next(
                (m.get("params", {}) for m in self.members if m.get("strategy_key") == key),
                {},
            )
            sig, reason = self._sub_signal(key, sub_params, df)
            return sig, f"[regime={regime}] {key}: {reason}"

        # --- 投票 / 加權：各子策略各出一票再聚合 ---
        signals = []
        weights = []
        details = []
        for m in self.members:
            sig, _ = self._sub_signal(m.get("strategy_key"), m.get("params", {}), df)
            signals.append(sig)
            weights.append(m.get("weight", 1.0))
            details.append(f"{m.get('strategy_key')}={sig}")

        final = aggregate_signals(signals, self.method, weights)
        return final, f"[{self.method}] " + ", ".join(details)
