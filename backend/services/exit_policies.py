"""
可插拔出場政策（ExitPolicy）── Phase 16 M4
==========================================
把「固定 % 止盈損」泛化成可插拔的出場政策，**回測與實盤共用同一份程式碼**
（回測=實盤鐵則在「出場端」的落實）：

- 回測：`backtest_engine._simulate_from_signals(exit_policy=...)` 進場時呼叫
  `on_entry` 拿 ExitPlan，逐 bar 呼叫 `on_bar`（動態政策用）再檢查觸價。
- 實盤：`bot_manager` 進場後同樣呼叫 `on_entry`，把 plan 持久化到 `bot.exit_plan`；
  券商端 GTC 保護單的 stop 價由 `ExitPlan.stop_price` 供給，
  每輪出場檢查走 `risk_manager.check_exit_plan`（吃同一份 plan）。

R:R 內建：`target = entry + rr_multiple × (entry − stop)`——
先定風險（stop 距離 = 1R），報酬照倍數推，M6 研究矩陣掃 rr 1.5~4。

政策全是純函式風格（只吃 df + 數字、不碰網路/DB），好測試。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict

import pandas as pd

from backend.strategies.indicators import atr, swing_lows


@dataclass
class ExitPlan:
    """一筆持倉的出場計畫（進場時算好；動態政策可逐 bar 更新）。

    - stop_price   ：停損觸價（None = 這個政策不設固定停損）
    - target_price ：停利觸價（None = 不設停利，讓策略訊號決定出場）
    - trailing_pct ：追蹤止損回檔比例（小數，0.03 = 3%；None = 不追蹤）
    - meta         ：計算依據（atr 值、swing low 位置…），供 DecisionLog 審計
    """
    stop_price: float | None = None
    target_price: float | None = None
    trailing_pct: float | None = None
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """轉 dict（存進 bot.exit_plan JSON 欄位用）。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "ExitPlan | None":
        """從 DB JSON 還原；None/空 dict 回 None（空手或沒用政策）。"""
        if not d:
            return None
        return cls(
            stop_price=d.get("stop_price"),
            target_price=d.get("target_price"),
            trailing_pct=d.get("trailing_pct"),
            meta=d.get("meta") or {},
        )


def _rr_target(entry_price: float, stop_price: float | None, rr_multiple: float | None) -> float | None:
    """R:R 停利價：target = entry + rr ×（entry − stop）。缺 stop 或 rr 就不設停利。"""
    if stop_price is None or rr_multiple is None:
        return None
    risk = entry_price - stop_price
    if risk <= 0:
        return None
    return entry_price + rr_multiple * risk


class ExitPolicy(ABC):
    """出場政策基底。子類別只要實作 on_entry；動態政策再覆寫 on_bar。"""

    key: str = ""
    # 僅日內框架可用的政策（如 vwap）設 True；run_backtest 會在日 K 誠實拋錯
    intraday_only: bool = False

    @abstractmethod
    def on_entry(self, df: pd.DataFrame, i: int, entry_price: float) -> ExitPlan:
        """進場成交當下（第 i 根，成交價 entry_price）算出出場計畫。
        只能看「到第 i 根為止」的資料（不偷看未來）。"""

    def on_bar(self, df: pd.DataFrame, i: int, plan: ExitPlan, state: dict) -> ExitPlan:
        """持倉中每根 bar 更新計畫（M10 動態出場掛點）。預設回原 plan（靜態政策）。
        state 帶 {"entry_price": ..., "peak_price": ...}，動態政策可參考。"""
        return plan


class FixedPctPolicy(ExitPolicy):
    """固定 % 止盈損——包既有行為（回歸基準）。

    與舊 `stop_loss_pct / take_profit_pct / trailing_stop_pct` 參數路徑**全等**：
    stop = entry×(1−sl)、target = entry×(1+tp)、trailing 透傳給引擎的 peak 邏輯。
    """

    key = "fixed_pct"

    def __init__(self, stop_loss_pct: float | None = None,
                 take_profit_pct: float | None = None,
                 trailing_stop_pct: float | None = None):
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct

    def on_entry(self, df: pd.DataFrame, i: int, entry_price: float) -> ExitPlan:
        return ExitPlan(
            stop_price=entry_price * (1 - self.stop_loss_pct) if self.stop_loss_pct else None,
            target_price=entry_price * (1 + self.take_profit_pct) if self.take_profit_pct else None,
            trailing_pct=self.trailing_stop_pct,
            meta={"policy": self.key},
        )


class AtrStopPolicy(ExitPolicy):
    """ATR 波動停損：stop = entry − k×ATR(n)；target 走 R:R。

    比固定 % 誠實的地方：停損距離跟著「這檔現在的波動」走——
    波動大時 stop 放遠（不被雜訊掃出場）、波動小時收緊（不多冒險）。
    ATR 算不出來（資料不足 NaN）→ 誠實回「無停損」的 plan（meta 記原因），不瞎掰數字。
    """

    key = "atr"

    def __init__(self, atr_len: int = 14, atr_mult: float = 2.0, rr_multiple: float | None = 2.0):
        self.atr_len = int(atr_len)
        self.atr_mult = float(atr_mult)
        self.rr_multiple = rr_multiple

    def on_entry(self, df: pd.DataFrame, i: int, entry_price: float) -> ExitPlan:
        # 只用到第 i 根為止的資料算 ATR（切片防未來）
        series = atr(df.iloc[: i + 1], length=self.atr_len)
        val = float(series.iloc[-1]) if len(series) else float("nan")
        if pd.isna(val) or val <= 0:
            return ExitPlan(meta={"policy": self.key, "reason": f"ATR({self.atr_len}) 資料不足，無停損"})
        stop = entry_price - self.atr_mult * val
        if stop <= 0:
            return ExitPlan(meta={"policy": self.key, "reason": "ATR 停損算出 ≤ 0，無停損"})
        return ExitPlan(
            stop_price=stop,
            target_price=_rr_target(entry_price, stop, self.rr_multiple),
            meta={"policy": self.key, "atr": round(val, 4),
                  "atr_len": self.atr_len, "atr_mult": self.atr_mult,
                  "rr_multiple": self.rr_multiple},
        )


class SwingLowPolicy(ExitPolicy):
    """結構停損：stop = 近 N 根內「已確認的 swing low」− buffer；target 走 R:R。

    swing 偵測復用 `strategies/indicators.swing_lows`（M5 BOS/HH-HL 同一份）。
    防未來：站在第 i 根只採 j ≤ i − right 的 swing（右邊需 right 根確認）。
    範圍內找不到 swing、或 swing 高於進場價（stop 無意義）→ 誠實回無停損 plan。
    """

    key = "swing"

    def __init__(self, lookback: int = 20, left: int = 3, right: int = 3,
                 buffer_pct: float = 0.005, rr_multiple: float | None = 2.0):
        self.lookback = int(lookback)
        self.left = int(left)
        self.right = int(right)
        self.buffer_pct = float(buffer_pct)
        self.rr_multiple = rr_multiple

    def on_entry(self, df: pd.DataFrame, i: int, entry_price: float) -> ExitPlan:
        # 已確認的 swing：只看到第 i 根為止的資料，且點位須 ≤ i − right
        sub = df.iloc[: i + 1]
        mask = swing_lows(sub, left=self.left, right=self.right)
        last_ok = i - self.right
        first_ok = max(0, i - self.lookback)
        candidates = mask.iloc[first_ok: last_ok + 1] if last_ok >= first_ok else mask.iloc[0:0]
        idx = candidates[candidates].index
        if len(idx) == 0:
            return ExitPlan(meta={"policy": self.key,
                                  "reason": f"近 {self.lookback} 根無已確認 swing low，無停損"})
        j = idx[-1]  # 最近的一個已確認 swing low
        low_col = sub["low"] if "low" in sub.columns else sub["close"]
        swing_price = float(low_col.loc[j])
        stop = swing_price * (1 - self.buffer_pct)
        if stop >= entry_price:
            return ExitPlan(meta={"policy": self.key,
                                  "reason": "swing low 高於進場價，stop 無意義，無停損",
                                  "swing_price": round(swing_price, 4)})
        return ExitPlan(
            stop_price=stop,
            target_price=_rr_target(entry_price, stop, self.rr_multiple),
            meta={"policy": self.key, "swing_price": round(swing_price, 4),
                  "swing_bar": int(j) if isinstance(j, (int, float)) else str(j),
                  "buffer_pct": self.buffer_pct, "rr_multiple": self.rr_multiple},
        )


def session_vwap(df: pd.DataFrame, i: int) -> float | None:
    """算「第 i 根所屬交易日（session）」到第 i 根為止的 VWAP。

    典型價 =(H+L+C)/3，VWAP = Σ(典型價×量)/Σ量，只累計同一天的 bar。
    缺 timestamp / volume 欄或全零量 → 回 None（呼叫端誠實跳過）。
    """
    if "timestamp" not in df.columns or "volume" not in df.columns:
        return None
    ts = pd.to_datetime(df["timestamp"], errors="coerce")
    day = ts.iloc[i]
    if pd.isna(day):
        return None
    # 同一 session ＝ 同一日曆日、且位置 ≤ i（不偷看未來）
    same_day = (ts.dt.date == day.date()) & (pd.RangeIndex(len(df)) <= i)
    sub = df[same_day.to_numpy()]
    high = sub["high"] if "high" in sub.columns else sub["close"]
    low = sub["low"] if "low" in sub.columns else sub["close"]
    typical = (high.astype(float) + low.astype(float) + sub["close"].astype(float)) / 3
    vol = sub["volume"].astype(float)
    total_vol = float(vol.sum())
    if total_vol <= 0:
        return None
    return float((typical * vol).sum() / total_vol)


class VwapStopPolicy(ExitPolicy):
    """日內 VWAP 停損：跌破「當日 session VWAP」出場（僅日內框架）。

    動態政策：VWAP 隨盤中逐 bar 更新，on_bar 每根重算並更新 stop。
    日 K 沒有 session 概念（一天一根，VWAP≈當根典型價，掛上去等於立刻出場），
    故 `intraday_only=True`，run_backtest 在日 K 誠實拋錯。
    target 預設不設（讓 VWAP 追蹤自然出場）；要 R:R 可帶 rr_multiple（用進場時的 stop 距離定 R）。
    """

    key = "vwap"
    intraday_only = True

    def __init__(self, rr_multiple: float | None = None):
        self.rr_multiple = rr_multiple

    def on_entry(self, df: pd.DataFrame, i: int, entry_price: float) -> ExitPlan:
        vwap = session_vwap(df, i)
        if vwap is None:
            return ExitPlan(meta={"policy": self.key, "reason": "算不出 session VWAP（缺欄/零量），無停損"})
        stop = min(vwap, entry_price)  # VWAP 高於進場價時退用進場價（stop 不可高於 entry）
        return ExitPlan(
            stop_price=stop,
            target_price=_rr_target(entry_price, stop, self.rr_multiple),
            meta={"policy": self.key, "vwap": round(vwap, 4), "rr_multiple": self.rr_multiple},
        )

    def on_bar(self, df: pd.DataFrame, i: int, plan: ExitPlan, state: dict) -> ExitPlan:
        vwap = session_vwap(df, i)
        if vwap is None:
            return plan  # 這根算不出來 → 沿用原 stop（不清掉既有保護）
        return ExitPlan(
            stop_price=vwap,
            target_price=plan.target_price,  # target 定錨在進場時的 R，不隨 VWAP 漂
            trailing_pct=plan.trailing_pct,
            meta={**plan.meta, "vwap": round(vwap, 4)},
        )


# 政策註冊表（key → 類別）。M6 研究矩陣、bots API、回測 API 都吃這份。
EXIT_POLICY_REGISTRY: dict[str, type[ExitPolicy]] = {
    FixedPctPolicy.key: FixedPctPolicy,
    AtrStopPolicy.key: AtrStopPolicy,
    SwingLowPolicy.key: SwingLowPolicy,
    VwapStopPolicy.key: VwapStopPolicy,
}


def get_exit_policy(key: str, params: dict | None = None) -> ExitPolicy:
    """依 key 建政策實例（params 直接餵建構子）。不認得的 key 誠實拋錯。"""
    cls = EXIT_POLICY_REGISTRY.get(key)
    if cls is None:
        raise ValueError(f"不支援的出場政策：{key}（可用：{'、'.join(EXIT_POLICY_REGISTRY)}）")
    return cls(**(params or {}))
