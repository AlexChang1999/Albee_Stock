"""
策略組合引擎測試（Phase 8 step-03）
=====================================
驗證：
1. aggregate_signals 純函式：投票 / 加權 / 平手 / 全 HOLD。
2. CompositeStrategy 能被 get_strategy 實例化並對同一份 df 產生訊號。
3. 複合策略能直接丟進 _run_on_df 跑出 metrics（零特例，走既有回測路徑）。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_composite.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import math

import pandas as pd

from backend.strategies import get_strategy
from backend.strategies.base import Signal
from backend.strategies.composite import aggregate_signals
from backend.services.backtest_engine import _run_on_df


def _osc_df(n=160):
    """震盪向上的合成日 K 線（足以觸發部分子策略交易），含 OHLCV + timestamp。"""
    closes = [100 + 10 * math.sin(i / 5) + i * 0.1 for i in range(n)]
    return pd.DataFrame({
        "open": closes,
        "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes],
        "close": closes,
        "volume": [1000 + (i % 10) * 50 for i in range(n)],
        "timestamp": pd.date_range("2023-01-01", periods=n, freq="D"),
    })


def test_aggregate_vote_majority():
    """投票：多數同向 → 該方向。"""
    assert aggregate_signals([Signal.BUY, Signal.BUY, Signal.SELL], "vote") == Signal.BUY
    assert aggregate_signals([Signal.SELL, Signal.SELL, Signal.HOLD], "vote") == Signal.SELL


def test_aggregate_tie_and_all_hold():
    """平手 → HOLD；全 HOLD / 空清單 → HOLD。"""
    assert aggregate_signals([Signal.BUY, Signal.SELL], "vote") == Signal.HOLD
    assert aggregate_signals([Signal.HOLD, Signal.HOLD], "vote") == Signal.HOLD
    assert aggregate_signals([], "vote") == Signal.HOLD


def test_aggregate_weighted():
    """加權：少數但權重大的一方可勝過多數小權重。"""
    # 2 票 SELL（各 1）對 1 票 BUY（權重 5）→ BUY 勝
    sigs = [Signal.BUY, Signal.SELL, Signal.SELL]
    weights = [5.0, 1.0, 1.0]
    assert aggregate_signals(sigs, "weighted", weights) == Signal.BUY
    # 權重相等則退回多數決
    assert aggregate_signals(sigs, "weighted", [1.0, 1.0, 1.0]) == Signal.SELL


def test_composite_instantiable_and_signals():
    """get_strategy('composite', ...) 可實例化並產出 (signal, reason)。"""
    params = {
        "method": "vote",
        "members": [
            {"strategy_key": "rsi", "params": {}},
            {"strategy_key": "donchian", "params": {}},
            {"strategy_key": "ma_crossover", "params": {}},
        ],
    }
    strat = get_strategy("composite", params)
    sig, reason = strat.generate_signal(_osc_df())
    assert sig in (Signal.BUY, Signal.SELL, Signal.HOLD)
    assert isinstance(reason, str) and reason


def test_composite_empty_members_holds():
    """無子策略 → 保守 HOLD。"""
    strat = get_strategy("composite", {"members": [], "method": "vote"})
    sig, _ = strat.generate_signal(_osc_df())
    assert sig == Signal.HOLD


def test_composite_runs_in_backtest():
    """複合策略直接走 _run_on_df 跑出含 EV 的 metrics。"""
    params = {
        "method": "weighted",
        "members": [
            {"strategy_key": "rsi", "params": {}, "weight": 1.0},
            {"strategy_key": "donchian", "params": {}, "weight": 2.0},
        ],
    }
    result = _run_on_df(get_strategy("composite", params), _osc_df(), 10000.0)
    assert "expected_value" in result and "num_round_trips" in result
    assert isinstance(result["equity_curve"], list) and len(result["equity_curve"]) > 0


def test_composite_regime_switch():
    """狀態切換：依當下狀態挑對應子策略；表內無對應狀態 → HOLD。"""
    params = {
        "method": "regime_switch",
        "members": [
            {"strategy_key": "donchian", "params": {}},
            {"strategy_key": "rsi", "params": {}},
        ],
        "regime_strategies": {"trending": "donchian", "ranging": "rsi"},
    }
    strat = get_strategy("composite", params)
    sig, reason = strat.generate_signal(_osc_df())
    assert sig in (Signal.BUY, Signal.SELL, Signal.HOLD)
    assert "regime=" in reason


if __name__ == "__main__":
    test_aggregate_vote_majority()
    test_aggregate_tie_and_all_hold()
    test_aggregate_weighted()
    test_composite_instantiable_and_signals()
    test_composite_empty_members_holds()
    test_composite_runs_in_backtest()
    test_composite_regime_switch()
    print("\n🎉 全部 composite 測試通過！")
