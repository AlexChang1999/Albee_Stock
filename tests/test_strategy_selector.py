"""
狀態 → 策略自適應選擇測試（Phase 7 step-03）
=============================================
驗證：
1. _profits_by_regime 把每筆 round-trip 盈虧歸到「進場當時的狀態」。
2. select_strategy 查表挑策略；無可信策略 / 未知狀態 → 保守退回觀望。
3. build_regime_strategy_map 端到端能跑（用合成 K 線，monkeypatch 掉抓資料，不連網）。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_strategy_selector.py -v
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

from backend.services import market_data
from backend.services import strategy_selector
from backend.services.strategy_selector import (
    _profits_by_regime,
    _bar_index_resolver,
    build_regime_strategy_map,
    select_strategy,
)
from backend.services.regime import REGIME_TRENDING, REGIME_RANGING


def _osc_df(n=160):
    """造一份震盪向上的合成日 K 線（足以觸發部分策略交易），含 OHLCV + timestamp。"""
    closes = [100 + 10 * math.sin(i / 5) + i * 0.1 for i in range(n)]
    return pd.DataFrame({
        "open": closes,
        "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes],
        "close": closes,
        "volume": [1000 + (i % 10) * 50 for i in range(n)],
        "timestamp": pd.date_range("2023-01-01", periods=n, freq="D"),
    })


def test_profits_by_regime_attribution():
    """round-trip 盈虧歸到買進當時的狀態（用日期對應 bar，再查該 bar 的狀態）。"""
    df = pd.DataFrame({"timestamp": pd.date_range("2024-01-01", periods=4, freq="D")})
    resolve = _bar_index_resolver(df)
    # bar0=trending, bar1=ranging, bar2=trending, bar3=ranging
    regimes = [REGIME_TRENDING, REGIME_RANGING, REGIME_TRENDING, REGIME_RANGING]
    trades = [
        {"date": "2024-01-01", "side": "buy"},
        {"date": "2024-01-02", "side": "sell", "profit": 30.0},   # 進場在 bar0=trending
        {"date": "2024-01-03", "side": "buy"},
        {"date": "2024-01-04", "side": "sell", "profit": -10.0},  # 進場在 bar2=trending
    ]
    by = _profits_by_regime(trades, regimes, resolve)
    assert by == {REGIME_TRENDING: [30.0, -10.0]}


def test_select_strategy_picks_from_map():
    """該狀態有可信策略 → 回該策略，fallback=False。"""
    regime_map = {
        "regimes": {
            REGIME_TRENDING: {
                "strategy": "donchian", "params": {},
                "expected_value": 50.0, "win_rate_pct": 60.0, "num_round_trips": 15,
            },
        }
    }
    features = {"trend_strength": 99, "volatility_20d": 0.1, "volume_ratio": 1.0, "return_5d": 0.05}
    pick = select_strategy(features, regime_map)
    assert pick["regime"] == REGIME_TRENDING
    assert pick["strategy"] == "donchian"
    assert pick["fallback"] is False


def test_select_strategy_fallback_when_no_trusted():
    """該狀態為 None（無可信策略）或不在表內 → 保守退回（strategy=None, fallback=True）。"""
    regime_map = {"regimes": {REGIME_TRENDING: None}}
    # 命中 trending 但該狀態 None
    f_trend = {"trend_strength": 99, "volatility_20d": 0.1, "volume_ratio": 1.0, "return_5d": 0.05}
    pick = select_strategy(f_trend, regime_map)
    assert pick["strategy"] is None and pick["fallback"] is True
    # 命中 ranging（表內根本沒這個鍵）→ 一樣保守
    f_range = {"trend_strength": 1, "volatility_20d": 0.1, "volume_ratio": 1.0, "return_5d": 0.05}
    pick2 = select_strategy(f_range, regime_map)
    assert pick2["regime"] == REGIME_RANGING
    assert pick2["strategy"] is None and pick2["fallback"] is True


def test_build_regime_strategy_map_smoke(monkeypatch):
    """端到端：合成 K 線跑得通，回傳結構正確，每個狀態冠軍為 None 或附完整統計。"""
    monkeypatch.setattr(market_data, "get_bars", lambda symbol, days, source: _osc_df())

    result = build_regime_strategy_map("FAKE", days=160)
    assert result["symbol"] == "FAKE"
    assert result["oos_bars"] > 0
    assert isinstance(result["regimes"], dict)
    assert isinstance(result["stats"], dict)
    for entry in result["regimes"].values():
        assert entry is None or {"strategy", "expected_value", "num_round_trips"} <= set(entry)


def test_build_map_raises_on_empty(monkeypatch):
    """抓不到資料應明確報錯，而不是默默回空表。"""
    monkeypatch.setattr(market_data, "get_bars", lambda symbol, days, source: pd.DataFrame())
    try:
        build_regime_strategy_map("FAKE", days=160)
        assert False, "空資料應 raise ValueError"
    except ValueError:
        pass


if __name__ == "__main__":
    test_profits_by_regime_attribution()
    test_select_strategy_picks_from_map()
    test_select_strategy_fallback_when_no_trusted()
    print("（build map 測試需 pytest 的 monkeypatch，請用 pytest 執行）")
    print("\n🎉 自適應選策略純函式測試通過！")
