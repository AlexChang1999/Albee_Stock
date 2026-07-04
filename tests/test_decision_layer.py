# -*- coding: utf-8 -*-
"""
AI Decision Layer（Phase 16 M10）測試
=====================================
- entry_score：分數界線 → enter / half_size / skip；資料不足誠實不干預
- apply_entry_gate：只否決 BUY、絕不碰 HOLD/SELL、絕不無中生有 BUY（單向約束）
- AdaptiveExitPolicy：波動升收緊 trailing、ADX 走強放寬 target（只一次）、
  動能衰竭 stop 上移（永不倒退）、調整記進 meta 可稽核
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.decision_layer import (
    DEFAULT_PARAMS,
    apply_entry_gate,
    entry_score,
)
from backend.services.exit_policies import (
    AdaptiveExitPolicy,
    EXIT_POLICY_REGISTRY,
    ExitPlan,
    get_exit_policy,
)
from backend.strategies import Signal


# ---------- 測試資料工具 ----------
def _df(n=60, close=None, high=None, low=None, volume=None):
    """合成 OHLCV；未給的欄位用合理預設（好控制單一特徵）。"""
    close = np.asarray(close if close is not None else [100.0] * n, dtype=float)
    return pd.DataFrame({
        "timestamp": pd.bdate_range("2024-01-02", periods=n).astype(str),
        "open": close,
        "high": np.asarray(high if high is not None else close * 1.01, dtype=float),
        "low": np.asarray(low if low is not None else close * 0.99, dtype=float),
        "close": close,
        "volume": np.asarray(volume if volume is not None else [1_000_000] * n, dtype=float),
    })


def _trending_df(n=60):
    """穩定上漲 + 放量：四特徵全該給高分。"""
    close = 100.0 * (1.02 ** np.arange(n))
    vol = np.linspace(1_000_000, 2_000_000, n)
    return _df(n, close=close, volume=vol)


def _chop_falling_df(n=60):
    """下跌 + 量縮 + 大波動：該被 skip。"""
    rng = np.random.default_rng(7)
    close = 100.0 * (0.97 ** np.arange(n)) * (1 + rng.normal(0, 0.03, n))
    vol = np.linspace(2_000_000, 200_000, n)
    return _df(n, close=close, high=close * 1.06, low=close * 0.94, volume=vol)


# ---------- entry_score ----------
def test_entry_score_enter_on_strong_trend():
    df = _trending_df()
    v = entry_score(df, len(df) - 1)
    assert v.action == "enter"
    assert v.score >= DEFAULT_PARAMS["enter_min"]
    assert v.reasons  # 有審計理由


def test_entry_score_skip_on_falling_chop():
    df = _chop_falling_df()
    v = entry_score(df, len(df) - 1)
    assert v.action == "skip"
    assert v.score < DEFAULT_PARAMS["half_min"]


def test_entry_score_insufficient_data_does_not_veto():
    # 3 根算不出任何 20 日級特徵 → 誠實「不干預」放行
    v = entry_score(_df(3), 2)
    assert v.action == "enter"
    assert "不干預" in v.reasons[0]


def test_entry_score_params_shift_threshold():
    # 同一份資料，把 enter_min 拉到 1.0 → 至多 half_size（參數化可掃描）
    df = _trending_df()
    v = entry_score(df, len(df) - 1, params={"enter_min": 1.01, "half_min": 0.0})
    assert v.action == "half_size"


# ---------- apply_entry_gate（單向約束）----------
def test_gate_only_vetoes_buy_never_creates():
    df = _chop_falling_df()
    n = len(df)
    signals = [Signal.HOLD] * n
    signals[n - 1] = Signal.BUY
    signals[10] = Signal.SELL
    gated, audit = apply_entry_gate(signals, df)
    assert gated[n - 1] == Signal.HOLD          # 爛環境的 BUY 被否決
    assert gated[10] == Signal.SELL             # SELL 原樣（不可反向/擋出場）
    assert gated.count(Signal.BUY) == 0
    assert len(audit) == 1 and audit[0]["action"] == "skip"


def test_gate_passes_buy_in_good_env():
    df = _trending_df()
    signals = [Signal.HOLD] * len(df)
    signals[len(df) - 1] = Signal.BUY
    gated, audit = apply_entry_gate(signals, df)
    assert gated[len(df) - 1] == Signal.BUY
    assert audit[0]["action"] in ("enter", "half_size")  # half_size 回測端視同 enter


# ---------- AdaptiveExitPolicy ----------
def _entry_plan(df, i=30, entry=100.0):
    policy = AdaptiveExitPolicy(atr_len=14, atr_mult=2.0, rr_multiple=2.0)
    return policy, policy.on_entry(df, i, entry)


def test_adaptive_registered_and_on_entry_math():
    assert "adaptive" in EXIT_POLICY_REGISTRY
    assert isinstance(get_exit_policy("adaptive"), AdaptiveExitPolicy)
    df = _df(40)  # high-low=2 → ATR≈2
    policy, plan = _entry_plan(df)
    assert plan.stop_price is not None
    # stop = 100 − 2×ATR(≈2) ≈ 96；target = entry + 2×(entry−stop) ≈ 108
    assert 95.0 < plan.stop_price < 97.0
    assert 106.0 < plan.target_price < 110.0
    assert plan.meta["adjustments"] == []


def test_adaptive_vol_rise_tightens_trailing():
    n = 60
    close = np.array([100.0] * n)
    high, low = close * 1.01, close * 0.99
    # 後 20 根波動放大 3 倍（high-low 從 2 → 6）→ ATR 比值升破 1.5
    high[40:], low[40:] = close[40:] * 1.03, close[40:] * 0.97
    df = _df(n, close=close, high=high, low=low)
    policy, plan = _entry_plan(df, i=30)
    assert plan.trailing_pct is None
    new = policy.on_bar(df, 58, plan, {"entry_price": 100.0, "peak_price": 101.0})
    assert new.trailing_pct == policy.tighten_trailing_pct
    assert any(a["rule"] == "vol_tighten" for a in new.meta["adjustments"])


def test_adaptive_exhaustion_raises_stop_never_lowers():
    n = 60
    # 前段平盤進場，尾段連跌 + 量縮 → 衰竭規則觸發，stop 上移到當根收盤
    close = np.array([100.0] * n)
    close[50:] = np.linspace(99.5, 97.0, 10)  # 跌但仍高於 ATR stop（≈96）→ 該被上移
    vol = np.array([1_000_000.0] * n)
    vol[50:] = 300_000.0
    df = _df(n, close=close, volume=vol)
    policy, plan = _entry_plan(df, i=30)
    old_stop = plan.stop_price
    new = policy.on_bar(df, 59, plan, {"entry_price": 100.0, "peak_price": 100.0})
    assert new.stop_price == float(close[59])   # 上移到當根收盤
    assert new.stop_price > old_stop
    assert any(a["rule"] == "exhaust_exit" for a in new.meta["adjustments"])
    # ADX 走強但方向是空頭（−DI > +DI）→ 不得放寬 target（做多不續抱空頭加速）
    assert not new.meta.get("target_widened")
    # 再跑一根「收盤更低」的情境：stop 不得往下退
    lower = new.stop_price - 5.0
    df2 = df.copy()
    df2.loc[len(df2)] = df2.iloc[-1]
    df2.loc[len(df2) - 1, "close"] = lower
    df2.loc[len(df2) - 1, "volume"] = 300_000.0
    newer = policy.on_bar(df2, len(df2) - 1, new, {"entry_price": 100.0, "peak_price": 100.0})
    assert newer.stop_price >= new.stop_price


def test_adaptive_adx_widen_only_in_bullish_direction():
    n = 70
    # 前 40 根平盤（進場時 ADX 低）、後 30 根強力上攻（ADX 走強且 +DI > −DI）
    close = np.array([100.0] * n)
    close[40:] = 100.0 * (1.03 ** np.arange(1, 31))
    df = _df(n, close=close)
    policy, plan = _entry_plan(df, i=35)
    assert plan.target_price is not None
    new = policy.on_bar(df, 65, plan, {"entry_price": 100.0, "peak_price": float(close[65])})
    assert new.meta.get("target_widened") is True
    assert new.target_price > plan.target_price  # rr 2 → 3（widen_rr=1）


def test_adaptive_no_stop_plan_is_left_alone():
    # 進場時資料不足（無 stop）→ on_bar 不動態調整（不無中生有）
    df = _df(5)
    policy = AdaptiveExitPolicy()
    plan = ExitPlan(meta={"policy": "adaptive", "reason": "資料不足"})
    assert policy.on_bar(df, 4, plan, {"entry_price": 100.0}) is plan
