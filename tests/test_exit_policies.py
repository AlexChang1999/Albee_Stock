# -*- coding: utf-8 -*-
"""
可插拔出場政策（Phase 16 M4）測試
================================
- 各政策的數學（fixed_pct / atr / swing / vwap）
- swing 偵測防未來函數（右邊沒確認根數的點不能用）
- 回測引擎：fixed_pct 與舊 % 參數路徑 bit-for-bit 全等、intrabar 觸發順序、r_multiple
- 實盤側：check_exit_plan 觸價判斷、protective_order_from_exit_plan 轉接
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.backtest_engine import _simulate_from_signals
from backend.services.exit_policies import (
    AtrStopPolicy,
    ExitPlan,
    FixedPctPolicy,
    SwingLowPolicy,
    VwapStopPolicy,
    get_exit_policy,
    session_vwap,
)
from backend.services.protective_orders import protective_order_from_exit_plan
from backend.services.risk_manager import check_exit_plan
from backend.strategies import Signal
from backend.strategies.indicators import swing_lows


# ---------- 測試資料工具 ----------
def _flat_df(n=60, price=100.0):
    """水平盤 OHLCV（好手算觸價）。"""
    return pd.DataFrame({
        "timestamp": pd.bdate_range("2024-01-02", periods=n).astype(str),
        "open": [price] * n, "high": [price * 1.01] * n,
        "low": [price * 0.99] * n, "close": [price] * n,
        "volume": [1_000_000] * n,
    })


# ---------- 政策數學 ----------
def test_fixed_pct_on_entry_math():
    plan = FixedPctPolicy(stop_loss_pct=0.05, take_profit_pct=0.10,
                          trailing_stop_pct=0.03).on_entry(_flat_df(), 30, 100.0)
    assert plan.stop_price == pytest.approx(95.0)
    assert plan.target_price == pytest.approx(110.0)
    assert plan.trailing_pct == 0.03


def test_atr_policy_math_and_rr_target():
    # 固定真實波幅：high-low = 2（前一收盤在區間內），ATR(14) ≈ 2
    n = 40
    df = pd.DataFrame({
        "open": [100.0] * n, "high": [101.0] * n, "low": [99.0] * n,
        "close": [100.0] * n, "volume": [1] * n,
    })
    plan = AtrStopPolicy(atr_len=14, atr_mult=2.0, rr_multiple=3.0).on_entry(df, n - 1, 100.0)
    assert plan.stop_price == pytest.approx(100.0 - 2 * 2.0, abs=0.01)   # entry − k×ATR
    risk = 100.0 - plan.stop_price
    assert plan.target_price == pytest.approx(100.0 + 3.0 * risk, abs=0.01)  # R:R
    assert plan.meta["atr"] == pytest.approx(2.0, abs=0.01)


def test_atr_policy_insufficient_data_returns_honest_empty_plan():
    df = _flat_df(5)  # 不夠算 ATR(14)
    plan = AtrStopPolicy(atr_len=14).on_entry(df, 4, 100.0)
    assert plan.stop_price is None and plan.target_price is None
    assert "資料不足" in plan.meta["reason"]


def test_swing_lows_detection_no_lookahead():
    # 第 10 根挖一個明顯低點；left=right=2
    n = 20
    low = [100.0] * n
    low[10] = 90.0
    df = pd.DataFrame({"close": [100.0] * n, "low": low, "high": [101.0] * n})
    mask = swing_lows(df, left=2, right=2)
    assert bool(mask.iloc[10]) is True          # 低點被偵測到
    assert int(mask.sum()) >= 1
    # 最後 right 根內的點「還沒被右邊確認」→ 不可能是 True（防未來）
    assert not mask.iloc[-2:].any()


def test_swing_policy_stop_below_entry_with_buffer():
    n = 30
    low = [100.0] * n
    low[20] = 92.0  # 進場前的 swing low
    df = pd.DataFrame({
        "close": [100.0] * n, "low": low, "high": [101.0] * n,
        "open": [100.0] * n, "volume": [1] * n,
    })
    plan = SwingLowPolicy(lookback=15, left=2, right=2,
                          buffer_pct=0.01, rr_multiple=2.0).on_entry(df, n - 1, 100.0)
    assert plan.stop_price == pytest.approx(92.0 * 0.99)
    risk = 100.0 - plan.stop_price
    assert plan.target_price == pytest.approx(100.0 + 2 * risk)
    assert plan.meta["swing_price"] == pytest.approx(92.0)


def test_swing_policy_no_swing_found_returns_empty_plan():
    plan = SwingLowPolicy(lookback=10, left=3, right=3).on_entry(_flat_df(30), 29, 100.0)
    # 水平盤到處等低 → rolling min 每根都相等，會找到 swing；改用嚴格遞增序列（無低點結構）
    inc = pd.DataFrame({
        "close": np.arange(100.0, 130.0), "low": np.arange(99.0, 129.0),
        "high": np.arange(101.0, 131.0),
    })
    plan = SwingLowPolicy(lookback=10, left=3, right=3).on_entry(inc, 29, 50.0)
    # 遞增序列的 swing low 只可能在最左端；若找到但高於進場價 50 → 誠實回無停損
    assert plan.stop_price is None


def test_vwap_session_math_and_on_bar_update():
    # 兩個 session：day1 三根、day2 兩根（分鐘 K 時戳）
    ts = ["2024-01-02 09:30", "2024-01-02 09:35", "2024-01-02 09:40",
          "2024-01-03 09:30", "2024-01-03 09:35"]
    df = pd.DataFrame({
        "timestamp": ts,
        "open": [100, 101, 102, 200, 201],
        "high": [101, 102, 103, 201, 202],
        "low": [99, 100, 101, 199, 200],
        "close": [100, 101, 102, 200, 201],
        "volume": [100, 100, 200, 100, 100],
    })
    # day1 前兩根 VWAP：典型價 (101+99+100)/3=100、(102+100+101)/3=101，等量 → 100.5
    assert session_vwap(df, 1) == pytest.approx(100.5)
    # 換日重置：day2 第一根 VWAP = 該根典型價 (201+199+200)/3 = 200
    assert session_vwap(df, 3) == pytest.approx(200.0)

    policy = VwapStopPolicy()
    plan = policy.on_entry(df, 1, 101.0)
    assert plan.stop_price == pytest.approx(100.5)
    # on_bar 動態更新：第 2 根 VWAP =(100×100+101×100+102×200)/400 = 101.25 → 但 stop 直接跟 VWAP
    new_plan = policy.on_bar(df, 2, plan, {})
    tp0 = (101 + 99 + 100) / 3
    tp1 = (102 + 100 + 101) / 3
    tp2 = (103 + 101 + 102) / 3
    expect = (tp0 * 100 + tp1 * 100 + tp2 * 200) / 400
    assert new_plan.stop_price == pytest.approx(expect)


def test_registry_get_and_unknown_key_raises():
    assert isinstance(get_exit_policy("atr", {"atr_len": 10}), AtrStopPolicy)
    with pytest.raises(ValueError):
        get_exit_policy("不存在的政策")


# ---------- 回測引擎整合 ----------
def _one_trade_signals(n, buy_at=5):
    """第 buy_at 根 BUY、其餘 HOLD（進場後靠出場政策離場）。"""
    sigs = [Signal.HOLD] * n
    sigs[buy_at] = Signal.BUY
    return sigs


def test_engine_fixed_pct_policy_equals_legacy_pct_path():
    """fixed_pct 政策與舊 % 參數路徑必須 bit-for-bit 全等（回歸基準）。"""
    rs = np.random.RandomState(7)
    n = 120
    close = 100 * np.cumprod(1 + rs.normal(0, 0.02, n))
    df = pd.DataFrame({
        "timestamp": pd.bdate_range("2024-01-02", periods=n).astype(str),
        "open": close * 0.999, "high": close * 1.01, "low": close * 0.99,
        "close": close, "volume": [1_000] * n,
    })
    sigs = [Signal.BUY if i % 15 == 0 else Signal.HOLD for i in range(n)]

    legacy = _simulate_from_signals(sigs, df, 10000.0,
                                    stop_loss_pct=0.05, take_profit_pct=0.08,
                                    trailing_stop_pct=0.04)
    policy = _simulate_from_signals(sigs, df, 10000.0,
                                    exit_policy=FixedPctPolicy(
                                        stop_loss_pct=0.05, take_profit_pct=0.08,
                                        trailing_stop_pct=0.04))
    # % 參數在引擎內部就是轉接成 FixedPctPolicy → 兩條路徑必須逐欄完全相同
    assert legacy == policy


def test_engine_intrabar_stop_beats_target_same_bar():
    """同一根同時破 stop 與 target → 保守先算 stop。"""
    n = 10
    df = pd.DataFrame({
        "timestamp": pd.bdate_range("2024-01-02", periods=n).astype(str),
        "open": [100.0] * n, "high": [100.0] * n, "low": [100.0] * n,
        "close": [100.0] * n, "volume": [1] * n,
    })
    # 第 7 根巨幅震盪：high 破 target、low 破 stop
    df.loc[7, "high"] = 130.0
    df.loc[7, "low"] = 80.0
    res = _simulate_from_signals(
        _one_trade_signals(n, buy_at=5), df, 10000.0,
        exit_policy=FixedPctPolicy(stop_loss_pct=0.05, take_profit_pct=0.10),
    )
    sells = [t for t in res["trades"] if t["side"] == "sell"]
    assert len(sells) == 1
    assert sells[0]["exit_reason"] == "stop_loss"
    assert res["num_stop_loss"] == 1 and res["num_take_profit"] == 0


def test_engine_gap_down_fills_at_worse_open():
    """跳空開低穿過 stop → 成交在更差的開盤價（不美化）。"""
    n = 10
    df = pd.DataFrame({
        "timestamp": pd.bdate_range("2024-01-02", periods=n).astype(str),
        "open": [100.0] * n, "high": [100.5] * n, "low": [99.5] * n,
        "close": [100.0] * n, "volume": [1] * n,
    })
    df.loc[8, ["open", "high", "low", "close"]] = [88.0, 89.0, 87.0, 88.0]  # 跳空開低
    res = _simulate_from_signals(
        _one_trade_signals(n, buy_at=5), df, 10000.0,
        exit_policy=FixedPctPolicy(stop_loss_pct=0.05),  # stop = 95
    )
    sells = [t for t in res["trades"] if t["side"] == "sell"]
    assert len(sells) == 1
    assert sells[0]["price"] == pytest.approx(88.0)  # 開盤價成交，不是 95


def test_engine_r_multiple_math():
    """r_multiple = 損益 /（qty × 初始風險 R）；停損出場應 ≈ −1R（含跳空/成本另計）。"""
    n = 12
    df = pd.DataFrame({
        "timestamp": pd.bdate_range("2024-01-02", periods=n).astype(str),
        "open": [100.0] * n, "high": [100.0] * n, "low": [100.0] * n,
        "close": [100.0] * n, "volume": [1] * n,
    })
    df.loc[9, "low"] = 94.0  # 盤中觸 stop=95（無跳空 → 成交在 95）
    res = _simulate_from_signals(
        _one_trade_signals(n, buy_at=5), df, 10000.0,
        exit_policy=FixedPctPolicy(stop_loss_pct=0.05),
    )
    sells = [t for t in res["trades"] if t["side"] == "sell"]
    assert len(sells) == 1
    # 零成本、進場 100、停損 95 → 每股虧 5 = 1R
    assert sells[0]["r_multiple"] == pytest.approx(-1.0, abs=0.01)
    assert res["avg_r_multiple"] == pytest.approx(-1.0, abs=0.01)


def test_engine_policy_and_pct_params_mutually_exclusive():
    df = _flat_df(10)
    with pytest.raises(ValueError):
        _simulate_from_signals([Signal.HOLD] * 10, df, 10000.0,
                               stop_loss_pct=0.05,
                               exit_policy=FixedPctPolicy(stop_loss_pct=0.05))


# ---------- 實盤側 ----------
def test_check_exit_plan_priority_and_levels():
    # 停損優先於停利
    hit, reason = check_exit_plan(100.0, 94.9, 100.0, stop_price=95.0, target_price=110.0)
    assert hit and "停損" in reason
    # 追蹤止損（peak 108、回檔 5% → 觸價 102.6）
    hit, reason = check_exit_plan(100.0, 102.0, 108.0, trailing_pct=0.05)
    assert hit and "追蹤止損" in reason
    # 停利
    hit, reason = check_exit_plan(100.0, 111.0, 111.0, target_price=110.0)
    assert hit and "停利" in reason
    # 都沒觸發 → 續抱
    hit, reason = check_exit_plan(100.0, 100.0, 100.0,
                                  stop_price=95.0, target_price=110.0)
    assert not hit and reason is None


def test_protective_order_from_exit_plan_mapping():
    # trailing 優先
    plan = ExitPlan(stop_price=95.0, trailing_pct=0.03).to_dict()
    assert protective_order_from_exit_plan(plan) == {"type": "trailing_stop", "trail_percent": 3.0}
    # 只有 stop
    plan = ExitPlan(stop_price=95.456).to_dict()
    assert protective_order_from_exit_plan(plan) == {"type": "stop", "stop_price": 95.46}
    # 空計畫（政策算不出 stop）→ 不掛
    assert protective_order_from_exit_plan(ExitPlan().to_dict()) is None
    assert protective_order_from_exit_plan(None) is None


def test_exit_plan_roundtrip_serialization():
    plan = ExitPlan(stop_price=95.0, target_price=110.0, trailing_pct=0.03, meta={"policy": "atr"})
    restored = ExitPlan.from_dict(plan.to_dict())
    assert restored == plan
    assert ExitPlan.from_dict(None) is None
    assert ExitPlan.from_dict({}) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
