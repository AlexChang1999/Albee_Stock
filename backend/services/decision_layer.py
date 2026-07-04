"""
AI Decision Layer（Phase 16 M10）—— 規則式進場評分閘
=====================================================
站在「策略已喊 BUY」之後的第二層守門：用既有市場特徵給這筆進場打分，
決定 enter（放行）/ half_size（縮量）/ skip（否決）。

鐵則（與 meta_label 同約束）：
  - **只能否決 / 縮量 / 調出場，不可反向、不可覆蓋核心策略訊號**——
    HOLD/SELL 永遠原樣通過，本層只碰 BUY。
  - **規則式、可回測、不用 LLM 即時喊單**：特徵全部復用既有
    `regime_features.compute_features`（ADX、ATR%、量比、動能……），
    參數化成 dict、可進 PARAM_GRIDS 掃描。
  - **上線判準**：`validation.is_layer_worth_it` OOS 過了才掛實盤
    （research_matrix --round 4 驗證；加不了分就不上，比照 macro 層誠實砍除）。

評分邏輯（透明、可調）：
  每個特徵給 0~1 的子分數，取「有資料的特徵」平均為總分：
  - trend_strength（ADX）：≥ adx_strong 滿分、≤ adx_weak 零分、中間線性
  - volume_ratio：量比 ≥ vol_confirm 滿分、≤ vol_dry 零分（進場要量能配合）
  - return_5d（動能）：> 0 滿分、< momentum_floor 零分、中間線性
  - atr_pct（波動）：≤ atr_calm 滿分、≥ atr_wild 零分（波動失控不追）
  分數 ≥ enter_min → enter；≥ half_min → half_size；其餘 skip。
  特徵覆蓋率 < 一半（資料太短算不出）→ 誠實回 enter「特徵不足，不干預」——
  本層要靠證據否決，沒證據就不干預（干預砍掉的每筆都是放棄的利潤）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from backend.services.regime_features import compute_features
from backend.strategies.base import Signal

# 預設參數（可整包餵 entry_score(params=...)，之後可進 optimizer PARAM_GRIDS 掃描）
DEFAULT_PARAMS: dict = {
    "adx_weak": 15.0,       # ADX ≤ 此值 → 趨勢子分 0
    "adx_strong": 25.0,     # ADX ≥ 此值 → 趨勢子分 1
    "vol_dry": 0.5,         # 量比 ≤ 此值 → 量能子分 0（量枯）
    "vol_confirm": 1.0,     # 量比 ≥ 此值 → 量能子分 1（有量配合）
    "momentum_floor": -0.03,  # 近 5 日報酬 ≤ 此值 → 動能子分 0
    "atr_calm": 0.02,       # ATR% ≤ 此值 → 波動子分 1（平靜）
    "atr_wild": 0.08,       # ATR% ≥ 此值 → 波動子分 0（失控）
    "enter_min": 0.60,      # 總分 ≥ 此值 → enter
    "half_min": 0.40,       # 總分 ≥ 此值 → half_size；再低 → skip
}


@dataclass
class DecisionVerdict:
    """一筆 BUY 的裁決：action ∈ enter / half_size / skip，score 0~1，reasons 供審計。"""
    action: str
    score: float
    reasons: list[str] = field(default_factory=list)


def _linear(value: float, lo: float, hi: float) -> float:
    """線性打分：value ≤ lo → 0、≥ hi → 1、中間內插（lo/hi 反向時自動翻轉語意）。"""
    if hi == lo:
        return 1.0 if value >= hi else 0.0
    x = (value - lo) / (hi - lo)
    return max(0.0, min(1.0, x))


def entry_score(df: pd.DataFrame, i: int, params: dict | None = None) -> DecisionVerdict:
    """
    站在第 i 根（策略喊 BUY 的那根）評分。只看 df.iloc[:i+1]（不偷看未來）。

    :return: DecisionVerdict（分數 = 有資料特徵的子分數平均；覆蓋率不足 → enter 不干預）
    """
    p = {**DEFAULT_PARAMS, **(params or {})}
    feats = compute_features(df.iloc[: i + 1])

    subs: list[tuple[str, float]] = []  # (說明, 子分數)——只收有資料的特徵
    adx = feats.get("trend_strength")
    if adx is not None:
        subs.append((f"ADX {adx:.1f}", _linear(adx, p["adx_weak"], p["adx_strong"])))
    vol = feats.get("volume_ratio")
    if vol is not None:
        subs.append((f"量比 {vol:.2f}", _linear(vol, p["vol_dry"], p["vol_confirm"])))
    mom = feats.get("return_5d")
    if mom is not None:
        subs.append((f"5日動能 {mom:+.2%}", _linear(mom, p["momentum_floor"], 0.0)))
    atr_pct = feats.get("atr_pct")
    if atr_pct is not None:
        # 波動反向：越平靜分越高
        subs.append((f"ATR% {atr_pct:.2%}", 1.0 - _linear(atr_pct, p["atr_calm"], p["atr_wild"])))

    if len(subs) < 2:  # 4 個特徵連一半都算不出 → 沒證據，不干預
        return DecisionVerdict("enter", 0.5, ["特徵不足（資料太短），不干預放行"])

    score = sum(s for _, s in subs) / len(subs)
    reasons = [f"{name} → {s:.2f}" for name, s in subs]
    if score >= p["enter_min"]:
        action = "enter"
    elif score >= p["half_min"]:
        action = "half_size"
    else:
        action = "skip"
    reasons.append(f"總分 {score:.2f} → {action}")
    return DecisionVerdict(action, round(score, 4), reasons)


def apply_entry_gate(signals: list, df: pd.DataFrame,
                     params: dict | None = None) -> tuple[list, list[dict]]:
    """
    回測掛點：把 BUY 訊號逐一過 entry_score，skip → 改 HOLD；其餘訊號原樣。

    half_size 在全進全出引擎裡無法半倉 → 回測端視同 enter（誠實保守：
    回測不高估縮量的好處；實盤端 bot 可依 verdict 縮量）。
    :return: (過閘後的訊號序列, 審計清單 [{i, action, score, reasons}, ...]）
    """
    out = list(signals)
    audit: list[dict] = []
    for i, sig in enumerate(out):
        if sig != Signal.BUY:
            continue
        v = entry_score(df, i, params)
        audit.append({"i": i, "action": v.action, "score": v.score, "reasons": v.reasons})
        if v.action == "skip":
            out[i] = Signal.HOLD
    return out, audit
