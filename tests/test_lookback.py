"""
回看長度推算測試（Phase 6 step-01）
====================================
驗證 `required_lookback_days` 替每個策略算出來的「往前抓幾天」，
換算回交易日後一定 ≥ 該策略所需的最小 K 棒數（min_bars_required），
不會發生「抓太少 → 指標算不出來 → 靜默失準」。

純函式測試，不連網、不碰資料庫。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_lookback.py
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from backend.strategies import STRATEGY_REGISTRY
from backend.strategies.lookback import min_bars_required, required_lookback_days


def _trading_bars_in(days: int) -> float:
    """把日曆天數換算回「大約有幾個交易日」（一週 7 天約 5 個交易日）。"""
    return days * 5 / 7


# 各策略一組「非預設」參數，確保推算有跟著參數走（不是寫死常數）
_CUSTOM_PARAMS = {
    "ma_crossover": {"short_window": 10, "long_window": 120},
    "rsi": {"period": 21},
    "macd": {"fast": 12, "slow": 52, "signal": 18},
    "bollinger": {"period": 40},
    "donchian": {"period": 55},
    "stochastic": {"k_period": 21, "d_period": 5},
    "momentum": {"period": 30},
    "williams_r": {"period": 28},
    "adx_trend": {"period": 30},
}


@pytest.mark.parametrize("strategy_key", list(STRATEGY_REGISTRY.keys()))
def test_default_params_enough_bars(strategy_key):
    """每個策略用「預設參數」時，推算的回看天數要足夠算出最小 K 棒數。"""
    days = required_lookback_days(strategy_key, {})
    min_bars = min_bars_required(strategy_key, {})
    assert _trading_bars_in(days) >= min_bars, (
        f"{strategy_key}: {days} 天 ≈ {_trading_bars_in(days):.1f} 根 < 需要 {min_bars} 根"
    )


@pytest.mark.parametrize("strategy_key,params", list(_CUSTOM_PARAMS.items()))
def test_custom_params_enough_bars(strategy_key, params):
    """換成較大的參數時，回看天數仍要 ≥ 所需 K 棒（證明有跟參數走）。"""
    days = required_lookback_days(strategy_key, params)
    min_bars = min_bars_required(strategy_key, params)
    assert _trading_bars_in(days) >= min_bars, (
        f"{strategy_key}{params}: {days} 天 ≈ {_trading_bars_in(days):.1f} 根 < 需要 {min_bars} 根"
    )


def test_longer_window_needs_more_days():
    """長均線需要的回看天數，必須比短均線多（推算確實隨參數遞增）。"""
    short = required_lookback_days("ma_crossover", {"long_window": 20})
    long = required_lookback_days("ma_crossover", {"long_window": 120})
    assert long > short, (short, long)


def test_old_hardcoded_60_was_insufficient():
    """證明舊版寫死 days=60 對 long_window=120 根本不夠（這正是本步驟要修的 bug）。
    新推算則必須抓得夠多。"""
    params = {"long_window": 120}
    assert _trading_bars_in(60) < min_bars_required("ma_crossover", params)  # 舊版不夠
    assert _trading_bars_in(required_lookback_days("ma_crossover", params)) >= min_bars_required(
        "ma_crossover", params
    )  # 新版夠


def test_unknown_strategy_gets_safe_default():
    """未知策略不該爆掉，給保守的非零回看天數。"""
    assert required_lookback_days("not_a_real_strategy", {}) > 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
