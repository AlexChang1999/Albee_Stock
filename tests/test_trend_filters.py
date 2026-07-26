# -*- coding: utf-8 -*-
"""
進場趨勢過濾器框架（Phase 16 M5）測試
====================================
- 各過濾器的放行/否決邏輯（ema_stack / vwap_side / adx_min / hh_hl / bos / regime）
- apply_entry_filters：只否決 BUY、不碰 SELL/HOLD、理由寫回 reasons
- 引擎掛點：entry_filters=None 行為與現況 bit-for-bit 相同
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.backtest_engine import _run_on_df
from backend.services.trend_filters import (
    AdxMinFilter,
    BosFilter,
    EmaStackFilter,
    FILTER_REGISTRY,
    HhHlFilter,
    RegimeFilter,
    VwapSideFilter,
    apply_entry_filters,
    get_trend_filter,
)
from backend.strategies import Signal, get_strategy


def _daily_df(closes, volume=1_000_000):
    n = len(closes)
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "timestamp": pd.bdate_range("2023-01-02", periods=n).astype(str),
        "open": closes, "high": closes * 1.005, "low": closes * 0.995,
        "close": closes, "volume": [volume] * n,
    })


# ---------- 個別過濾器 ----------
def test_ema_stack_allows_uptrend_blocks_downtrend():
    up = _daily_df(np.linspace(50, 150, 260))     # 一路走高 → EMA 多頭排列
    down = _daily_df(np.linspace(150, 50, 260))   # 一路走低 → 空頭排列
    f = EmaStackFilter()
    ok, why = f.allow_entry(up, 259)
    assert ok, why
    ok, why = f.allow_entry(down, 259)
    assert not ok and "未多頭排列" in why


def test_ema_stack_insufficient_data_vetoes():
    ok, why = EmaStackFilter(slow=200).allow_entry(_daily_df([100.0] * 50), 49)
    assert not ok and "資料不足" in why


def test_vwap_side_daily_passes_as_not_applicable():
    ok, why = VwapSideFilter().allow_entry(_daily_df([100.0] * 30), 29)
    assert ok and "不適用" in why


def test_vwap_side_intraday_above_below():
    ts = pd.date_range("2024-01-02 09:30", periods=10, freq="5min").astype(str)
    base = pd.DataFrame({
        "timestamp": ts,
        "open": [100.0] * 10, "high": [101.0] * 10, "low": [99.0] * 10,
        "close": [100.0] * 10, "volume": [100] * 10,
    })
    f = VwapSideFilter()
    # 最後一根收在 VWAP（≈100）之上 → 放行
    above = base.copy()
    above.loc[9, "close"] = 105.0
    ok, why = f.allow_entry(above, 9)
    assert ok, why
    # 收在 VWAP 之下 → 否決
    below = base.copy()
    below.loc[9, "close"] = 95.0
    ok, why = f.allow_entry(below, 9)
    assert not ok and "VWAP 下" in why


def test_adx_min_blocks_flat_market_and_nan():
    rs = np.random.RandomState(3)
    flat = _daily_df(100 + rs.normal(0, 0.1, 80))   # 幾乎水平 → ADX 低
    trend = _daily_df(np.linspace(50, 200, 80))     # 強趨勢 → ADX 高
    f = AdxMinFilter(threshold=20)
    ok, why = f.allow_entry(flat, 79)
    assert not ok
    ok, why = f.allow_entry(trend, 79)
    assert ok, why
    # 資料不足 → NaN → 保守否決
    ok, why = f.allow_entry(_daily_df([100.0] * 5), 4)
    assert not ok and "資料不足" in why


def _structured_df(pattern, n_pad=10):
    """造有明確 swing 結構的 low/high 序列（pattern 是 (low, high) tuple 列表）。"""
    lows, highs = [], []
    for lo, hi in pattern:
        lows.append(lo)
        highs.append(hi)
    lows = [lows[0]] * n_pad + lows + [lows[-1]] * n_pad
    highs = [highs[0]] * n_pad + highs + [highs[-1]] * n_pad
    n = len(lows)
    close = [(l + h) / 2 for l, h in zip(lows, highs)]
    return pd.DataFrame({
        "timestamp": pd.bdate_range("2023-01-02", periods=n).astype(str),
        "open": close, "high": highs, "low": lows, "close": close,
        "volume": [1_000] * n,
    })


def test_hh_hl_uptrend_structure():
    # 兩個走高的 swing low（90 → 95）與兩個走高的 swing high（110 → 118）
    rs = np.random.RandomState(1)
    n = 60
    lows = 100 + rs.normal(0, 0.2, n)
    highs = lows + 2
    lows[20], highs[20] = 90, 92     # swing low 1
    lows[30], highs[30] = 108, 110   # swing high 1
    lows[40], highs[40] = 95, 97     # swing low 2（higher low）
    lows[50], highs[50] = 116, 118   # swing high 2（higher high）
    close = (lows + highs) / 2
    df = pd.DataFrame({
        "timestamp": pd.bdate_range("2023-01-02", periods=n).astype(str),
        "open": close, "high": highs, "low": lows, "close": close, "volume": [1] * n,
    })
    ok, why = HhHlFilter(lookback=45, left=3, right=3).allow_entry(df, n - 1)
    assert ok, why
    # 把「最近一個」swing low 改成破低（LL）→ 結構破壞 → 否決
    df2 = df.copy()
    df2.loc[52, "low"] = 85
    df2.loc[52, ["open", "close"]] = 86
    ok, why = HhHlFilter(lookback=45, left=3, right=3).allow_entry(df2, n - 1)
    assert not ok, why


def test_bos_breakout_vs_below_structure():
    rs = np.random.RandomState(2)
    n = 40
    lows = 100 + rs.normal(0, 0.2, n)
    highs = lows + 2
    highs[25] = 115  # 已確認 swing high
    close = (lows + highs) / 2
    df = pd.DataFrame({
        "timestamp": pd.bdate_range("2023-01-02", periods=n).astype(str),
        "open": close, "high": highs, "low": lows, "close": close, "volume": [1] * n,
    })
    f = BosFilter(lookback=30, left=3, right=3)
    # 收盤沒過 115 → 否決
    ok, why = f.allow_entry(df, n - 1)
    assert not ok and "未突破" in why
    # 最後一根收破 115 → 放行
    df.loc[n - 1, "close"] = 116.0
    ok, why = f.allow_entry(df, n - 1)
    assert ok, why


def test_regime_filter_trending_only(monkeypatch):
    import backend.services.trend_filters as tf
    monkeypatch.setattr(tf, "classify_regime", lambda feats: "trending")
    ok, why = RegimeFilter().allow_entry(_daily_df([100.0] * 30), 29)
    assert ok and "trending" in why
    monkeypatch.setattr(tf, "classify_regime", lambda feats: "ranging")
    ok, why = RegimeFilter().allow_entry(_daily_df([100.0] * 30), 29)
    assert not ok and "ranging" in why


def test_registry_and_unknown_key():
    assert set(FILTER_REGISTRY) == {"ema_stack", "vwap_side", "adx_min", "hh_hl", "bos", "regime"}
    assert isinstance(get_trend_filter("adx_min", {"threshold": 25}), AdxMinFilter)
    with pytest.raises(ValueError):
        get_trend_filter("nope")


# ---------- apply_entry_filters ----------
class _AlwaysVeto(HhHlFilter):
    key = "veto"

    def allow_entry(self, df, i):
        return False, "測試用一律否決"


class _AlwaysPass(HhHlFilter):
    key = "pass"

    def allow_entry(self, df, i):
        return True, "ok"


def test_apply_entry_filters_only_touches_buy():
    df = _daily_df([100.0] * 5)
    sigs = [Signal.BUY, Signal.SELL, Signal.HOLD, Signal.BUY, Signal.SELL]
    reasons = ["b", "s", "h", "b2", "s2"]
    out_sigs, out_reasons = apply_entry_filters(sigs, reasons, df, [_AlwaysVeto()])
    assert out_sigs == [Signal.HOLD, Signal.SELL, Signal.HOLD, Signal.HOLD, Signal.SELL]
    assert "進場過濾否決（veto）" in out_reasons[0]
    assert out_reasons[1] == "s" and out_reasons[2] == "h"  # SELL/HOLD 原封不動
    # 全放行 → 原樣
    out_sigs, out_reasons = apply_entry_filters(sigs, reasons, df, [_AlwaysPass()])
    assert out_sigs == sigs and out_reasons == reasons


def test_engine_hook_none_filters_identical_and_veto_blocks_trades():
    """entry_filters=None 與不帶參數 bit-for-bit 相同；一律否決 → 一筆買進都沒有。"""
    rs = np.random.RandomState(9)
    df = _daily_df(100 * np.cumprod(1 + rs.normal(0.001, 0.02, 200)))
    strategy = get_strategy("ma_crossover", {"short_window": 5, "long_window": 20})
    base = _run_on_df(strategy, df, 10000.0)
    with_none = _run_on_df(strategy, df, 10000.0, entry_filters=None)
    assert base == with_none
    vetoed = _run_on_df(strategy, df, 10000.0, entry_filters=[_AlwaysVeto()])
    assert not any(t["side"] == "buy" for t in vetoed["trades"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
