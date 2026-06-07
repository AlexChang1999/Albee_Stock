"""
層驗證 harness 測試（Phase 7 收尾）
=====================================
驗證：
1. 包裝策略行為：MetaFilteredStrategy（BUY 被二級否決→HOLD、放行則原樣）、
   AdaptiveMappedStrategy（fallback→HOLD、有可信策略則委派）。
2. validate_*_layer 回正確結構（baseline_oos/candidate_oos 等長 + verdict）。
3. validate_layers 跨檔池化、太短資料 best-effort 跳過。

純函式 / 合成 K 線 / monkeypatch，不連網。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_layer_validation.py -v
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

from backend.services import layer_validation as lv
from backend.services.layer_validation import (
    MetaFilteredStrategy,
    AdaptiveMappedStrategy,
    validate_meta_layer,
    validate_adaptive_layer,
    validate_kelly_layer,
    validate_layers,
)
from backend.strategies import Signal


def _osc_df(n=600):
    closes = [100 + 10 * math.sin(i / 5) + i * 0.1 for i in range(n)]
    return pd.DataFrame({
        "open": closes,
        "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes],
        "close": closes,
        "volume": [1000] * n,
        "timestamp": pd.date_range("2022-01-01", periods=n, freq="D"),
    })


class _StubBase:
    """固定回某訊號的假一級策略。"""
    def __init__(self, sig):
        self.sig = sig

    def generate_signal(self, df):
        return self.sig, "stub"


# ---------- 1. 包裝策略 ----------
def test_meta_wrapper_vetoes_buy(monkeypatch):
    """二級否決時，BUY → HOLD。"""
    monkeypatch.setattr(lv, "should_take", lambda *a, **k: (False, 0.1))
    sig, _ = MetaFilteredStrategy(_StubBase(Signal.BUY)).generate_signal(_osc_df(60))
    assert sig == Signal.HOLD


def test_meta_wrapper_passes_buy(monkeypatch):
    """二級放行時，BUY 原樣通過。"""
    monkeypatch.setattr(lv, "should_take", lambda *a, **k: (True, 0.9))
    sig, _ = MetaFilteredStrategy(_StubBase(Signal.BUY)).generate_signal(_osc_df(60))
    assert sig == Signal.BUY


def test_meta_wrapper_ignores_non_buy(monkeypatch):
    """非 BUY（SELL）不經二級，原樣通過。"""
    monkeypatch.setattr(lv, "should_take", lambda *a, **k: (False, 0.0))
    sig, _ = MetaFilteredStrategy(_StubBase(Signal.SELL)).generate_signal(_osc_df(60))
    assert sig == Signal.SELL


def test_adaptive_wrapper_fallback(monkeypatch):
    """對照表無可信策略（fallback）→ HOLD。"""
    monkeypatch.setattr(lv, "select_strategy",
                        lambda f, m: {"regime": "ranging", "strategy": None, "params": {}, "fallback": True})
    sig, _ = AdaptiveMappedStrategy({}).generate_signal(_osc_df(60))
    assert sig == Signal.HOLD


def test_adaptive_wrapper_delegates(monkeypatch):
    """有可信策略 → 委派該策略產訊號（回合法訊號）。"""
    monkeypatch.setattr(lv, "select_strategy",
                        lambda f, m: {"regime": "trending", "strategy": "rsi", "params": {}, "fallback": False})
    sig, _ = AdaptiveMappedStrategy({}).generate_signal(_osc_df(60))
    assert sig in (Signal.BUY, Signal.SELL, Signal.HOLD)


# ---------- 2. 各層結構 ----------
def test_validate_meta_structure():
    """meta 層回 baseline/candidate 等長 + verdict 帶 worth。"""
    r = validate_meta_layer(_osc_df(420))
    assert len(r["baseline_oos"]) == len(r["candidate_oos"])
    assert "worth" in r["verdict"]


def test_validate_adaptive_structure():
    """adaptive 層回等長兩串 + verdict。"""
    r = validate_adaptive_layer(_osc_df(420))
    assert len(r["baseline_oos"]) == len(r["candidate_oos"])
    assert "worth" in r["verdict"]


def test_validate_kelly_structure():
    """kelly 層回等長兩串 + 標明指標為終值報酬。"""
    r = validate_kelly_layer(_osc_df(420))
    assert len(r["baseline_oos"]) == len(r["candidate_oos"])
    assert r["metric"] == "terminal_return"


# ---------- 3. 跨檔池化 + 跳過 ----------
def test_validate_layers_pools_and_skips(monkeypatch):
    """兩檔合成資料 → 池化（≥單檔長度）；太短的檔被跳過。"""
    def fake_get_bars(symbol, days=60, source="yfinance"):
        if symbol == "SHORT":
            return _osc_df(50)  # 湊不出 fold
        return _osc_df(420)

    monkeypatch.setattr(lv.market_data, "get_bars", fake_get_bars)
    out = validate_layers(symbols=["AAA", "BBB", "SHORT"], source="yfinance", days=420)

    assert out["symbols"] == ["AAA", "BBB"]
    assert any(s["symbol"] == "SHORT" for s in out["skipped"])
    # 池化：兩檔的 meta baseline 應 >= 單檔
    single = validate_meta_layer(_osc_df(420))
    assert len(out["meta"]["baseline_oos"]) >= len(single["baseline_oos"])
    # step-06 誠實標記不可驗證
    assert out["event"]["verdict"]["worth"] is None


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
