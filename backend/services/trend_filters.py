"""
進場趨勢過濾器框架（TrendFilter）── Phase 16 M5
================================================
在「策略訊號層」之上加一道進場守門：BUY 訊號要先過所有過濾器，
被否決就改記 HOLD + 否決理由（回測記進 reasons、實盤進 DecisionLog，
語意同 meta_label 的二級否決）。目的：避免下跌抄底、盤整被洗、空頭做多。

★M5 只建框架 + 單元測試；哪個 filter 真的上線由 M6 研究矩陣的
`layer_validation.is_layer_worth_it` 樣本外判定——加不了分就砍
（比照 Phase 11 macro 層誠實砍除前例）。

設計鐵則：
- **只准看「到第 i 根為止」的資料**（不偷看未來）。swing 相關過濾器
  復用 `strategies/indicators.swing_lows/swing_highs`，只採 j ≤ i − right 的已確認點。
- 純函式風格（吃 df + 數字，不碰網路/DB），好測試。
- 過濾器只會「否決 BUY」，不產生訊號、不碰 SELL/HOLD（只煞車，不猜方向）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from backend.services.exit_policies import session_vwap
from backend.services.regime import classify_regime
from backend.services.regime_features import compute_features
from backend.strategies import Signal
from backend.strategies.indicators import adx_components, swing_highs, swing_lows


class TrendFilter(ABC):
    """進場過濾器基底：allow_entry 回 (放行與否, 理由)。"""

    key: str = ""

    @abstractmethod
    def allow_entry(self, df: pd.DataFrame, i: int) -> tuple[bool, str]:
        """站在第 i 根（訊號產生的那根）判斷這筆 BUY 該不該放行。
        只能看「到第 i 根為止」的資料。回 (True, 理由) 或 (False, 否決理由)。"""


class EmaStackFilter(TrendFilter):
    """EMA 多頭排列：EMA(fast) > EMA(mid) > EMA(slow) 才放行（預設 20>50>200）。"""

    key = "ema_stack"

    def __init__(self, fast: int = 20, mid: int = 50, slow: int = 200):
        self.fast, self.mid, self.slow = int(fast), int(mid), int(slow)

    def allow_entry(self, df: pd.DataFrame, i: int) -> tuple[bool, str]:
        if i + 1 < self.slow:
            return False, f"資料不足 {self.slow} 根，EMA 排列不可信，保守否決"
        # ewm 是因果濾波（每點只用過去），整段算完讀第 i 點 == 切片重算，不偷看
        close = df["close"].astype(float)
        f = close.ewm(span=self.fast, adjust=False).mean().iloc[i]
        m = close.ewm(span=self.mid, adjust=False).mean().iloc[i]
        s = close.ewm(span=self.slow, adjust=False).mean().iloc[i]
        if f > m > s:
            return True, f"EMA 多頭排列（{self.fast}>{self.mid}>{self.slow}）"
        return False, (f"EMA 未多頭排列（EMA{self.fast}={f:.2f}, "
                       f"EMA{self.mid}={m:.2f}, EMA{self.slow}={s:.2f}）")


class VwapSideFilter(TrendFilter):
    """價在 session VWAP 之上才放行（日內框架專用）。

    日 K 沒有 session 概念（時戳無盤中時間）→ 放行 + 理由註明不適用
    （不因掛錯框架而把整條訊號流全否決）。
    """

    key = "vwap_side"

    def allow_entry(self, df: pd.DataFrame, i: int) -> tuple[bool, str]:
        if "timestamp" not in df.columns:
            return True, "無時戳欄，vwap_side 不適用（放行）"
        ts = pd.to_datetime(df["timestamp"], errors="coerce")
        # 全部時戳都在午夜整點 = 日 K → 不適用
        if bool((ts.dropna() == ts.dropna().dt.normalize()).all()):
            return True, "日 K 無 session VWAP，vwap_side 不適用（放行）"
        vwap = session_vwap(df, i)
        if vwap is None:
            return False, "算不出 session VWAP（缺欄/零量），保守否決"
        price = float(df["close"].iloc[i])
        if price > vwap:
            return True, f"價在 VWAP 上（{price:.2f} > {vwap:.2f}）"
        return False, f"價在 VWAP 下（{price:.2f} ≤ {vwap:.2f}），弱勢不進"


class AdxMinFilter(TrendFilter):
    """ADX ≥ 門檻才放行（趨勢要夠強；復用 indicators.adx_components）。"""

    key = "adx_min"

    def __init__(self, threshold: float = 20.0, length: int = 14):
        self.threshold = float(threshold)
        self.length = int(length)

    def allow_entry(self, df: pd.DataFrame, i: int) -> tuple[bool, str]:
        adx, _, _ = adx_components(df.iloc[: i + 1], length=self.length)
        val = float(adx.iloc[-1]) if len(adx) else float("nan")
        if pd.isna(val):
            return False, f"ADX({self.length}) 資料不足，保守否決"
        if val >= self.threshold:
            return True, f"ADX {val:.1f} ≥ {self.threshold:g}"
        return False, f"ADX {val:.1f} < {self.threshold:g}，趨勢不夠強"


class HhHlFilter(TrendFilter):
    """HH-HL 結構：近 lookback 根內「最後兩個 swing high 走高 且 最後兩個 swing low 走高」
    才放行（上升結構完整；復用 M4 swing 偵測，只採已確認點）。"""

    key = "hh_hl"

    def __init__(self, lookback: int = 40, left: int = 3, right: int = 3):
        self.lookback = int(lookback)
        self.left = int(left)
        self.right = int(right)

    def _confirmed_points(self, df: pd.DataFrame, i: int, mask: pd.Series, col: str) -> list[float]:
        """取「站在第 i 根已確認」且落在 lookback 內的 swing 點價位（由舊到新）。"""
        last_ok = i - self.right           # 右邊需 right 根確認
        first_ok = max(0, i - self.lookback)
        if last_ok < first_ok:
            return []
        window = mask.iloc[first_ok: last_ok + 1]
        series = df[col] if col in df.columns else df["close"]
        return [float(series.loc[j]) for j in window[window].index]

    def allow_entry(self, df: pd.DataFrame, i: int) -> tuple[bool, str]:
        sub = df.iloc[: i + 1]
        highs = self._confirmed_points(sub, i, swing_highs(sub, self.left, self.right), "high")
        lows = self._confirmed_points(sub, i, swing_lows(sub, self.left, self.right), "low")
        if len(highs) < 2 or len(lows) < 2:
            return False, f"近 {self.lookback} 根 swing 點不足（HH-HL 結構不可判），保守否決"
        if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
            return True, "HH-HL 上升結構成立"
        return False, (f"非 HH-HL（highs {highs[-2]:.2f}→{highs[-1]:.2f}, "
                       f"lows {lows[-2]:.2f}→{lows[-1]:.2f}）")


class BosFilter(TrendFilter):
    """Break of Structure：收盤突破「最近一個已確認 swing high」才放行。"""

    key = "bos"

    def __init__(self, lookback: int = 40, left: int = 3, right: int = 3):
        self.lookback = int(lookback)
        self.left = int(left)
        self.right = int(right)

    def allow_entry(self, df: pd.DataFrame, i: int) -> tuple[bool, str]:
        sub = df.iloc[: i + 1]
        mask = swing_highs(sub, self.left, self.right)
        last_ok = i - self.right
        first_ok = max(0, i - self.lookback)
        window = mask.iloc[first_ok: last_ok + 1] if last_ok >= first_ok else mask.iloc[0:0]
        idx = window[window].index
        if len(idx) == 0:
            return False, f"近 {self.lookback} 根無已確認 swing high（BOS 不可判），保守否決"
        high_col = sub["high"] if "high" in sub.columns else sub["close"]
        level = float(high_col.loc[idx[-1]])
        price = float(df["close"].iloc[i])
        if price > level:
            return True, f"BOS 成立（收盤 {price:.2f} > 前 swing high {level:.2f}）"
        return False, f"未突破結構（收盤 {price:.2f} ≤ 前 swing high {level:.2f}）"


class RegimeFilter(TrendFilter):
    """市場狀態 == trending 才放行（復用 Phase 7 regime 分類，只煞車不猜方向）。"""

    key = "regime"

    def allow_entry(self, df: pd.DataFrame, i: int) -> tuple[bool, str]:
        regime = classify_regime(compute_features(df.iloc[: i + 1]))
        if regime == "trending":
            return True, "市場狀態 trending"
        return False, f"市場狀態 {regime}（非 trending），不進場"


# 過濾器註冊表（key → 類別）。M6 Round 3 逐個過 is_layer_worth_it 判去留。
FILTER_REGISTRY: dict[str, type[TrendFilter]] = {
    EmaStackFilter.key: EmaStackFilter,
    VwapSideFilter.key: VwapSideFilter,
    AdxMinFilter.key: AdxMinFilter,
    HhHlFilter.key: HhHlFilter,
    BosFilter.key: BosFilter,
    RegimeFilter.key: RegimeFilter,
}


def get_trend_filter(key: str, params: dict | None = None) -> TrendFilter:
    """依 key 建過濾器實例。不認得的 key 誠實拋錯。"""
    cls = FILTER_REGISTRY.get(key)
    if cls is None:
        raise ValueError(f"不支援的進場過濾器：{key}（可用：{'、'.join(FILTER_REGISTRY)}）")
    return cls(**(params or {}))


def apply_entry_filters(
    signals: list, reasons: list | None, df: pd.DataFrame,
    entry_filters: list[TrendFilter],
) -> tuple[list, list | None]:
    """把 BUY 訊號逐一過過濾器；任一否決 → 改 HOLD + 否決理由（其餘訊號原樣）。

    回測掛點：`backtest_engine._run_on_df` 在 produce_signals 之後、成交模擬之前呼叫。
    只改「訊號層」——成交層（次根開盤含成本）完全不動（回測=實盤鐵則）。
    """
    if not entry_filters:
        return signals, reasons
    out_signals = list(signals)
    out_reasons = list(reasons) if reasons is not None else [""] * len(signals)
    for i, sig in enumerate(out_signals):
        if sig != Signal.BUY:
            continue
        for f in entry_filters:
            ok, why = f.allow_entry(df, i)
            if not ok:
                out_signals[i] = Signal.HOLD
                out_reasons[i] = f"進場過濾否決（{f.key}）：{why}"
                break  # 一個否決就夠，不用再問其他過濾器
    return out_signals, out_reasons
