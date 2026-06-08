"""
自動驗證管線測試（Phase 8 step-04）
=====================================
驗證最關鍵的守門邏輯：判定鍵讀的是**樣本外（walk-forward）**，不是 in-sample。
- monkeypatch 一個「OOS 加分」的候選 → validated。
- monkeypatch 一個「OOS 不加分」的候選 → rejected。

不連網：monkeypatch market_data.get_bars 給合成 K 線、validation.walk_forward 給可控 fold。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_evolution.py -q
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

from backend.services import market_data, validation, evolution
from backend.services.evolution import validate_candidate


class _FakeKnowledge:
    """模擬 StrategyKnowledge ORM 物件（只用到的屬性）。"""
    def __init__(self, strategy_key="rsi", params=None):
        self.id = 1
        self.strategy_key = strategy_key
        self.params = params or {}
        self.status = "candidate"
        self.oos_metrics = None


def _osc_df(n=160):
    closes = [100 + 10 * math.sin(i / 5) + i * 0.1 for i in range(n)]
    return pd.DataFrame({
        "open": closes,
        "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes],
        "close": closes,
        "volume": [1000 + (i % 10) * 50 for i in range(n)],
        "timestamp": pd.date_range("2023-01-01", periods=n, freq="D"),
    })


def _folds(ev_each):
    """造 walk_forward 回傳格式的 fold 清單（只填判定會讀的鍵）。"""
    return [
        {"fold": i, "test_start": 0, "test_end": 1, "expected_value": ev,
         "win_rate_pct": 0.0, "total_return_pct": 0.0, "num_round_trips": 1}
        for i, ev in enumerate(ev_each)
    ]


def test_validate_oos_positive_validated(monkeypatch):
    """OOS（walk-forward）每 fold 都正 EV → validated。"""
    monkeypatch.setattr(market_data, "get_bars", lambda symbol, days, source: _osc_df())
    monkeypatch.setattr(validation, "walk_forward",
                        lambda *a, **k: _folds([10.0, 12.0, 8.0]))
    row = _FakeKnowledge()
    out = validate_candidate(row, "FAKE", days=160)
    assert out["status"] == "validated"
    assert row.status == "validated"
    assert row.oos_metrics["verdict"]["worth"] is True
    assert row.oos_metrics["expected_value"] == 10.0  # (10+12+8)/3


def test_validate_oos_negative_rejected(monkeypatch):
    """OOS 平均為負（輸給不交易）→ rejected。"""
    monkeypatch.setattr(market_data, "get_bars", lambda symbol, days, source: _osc_df())
    monkeypatch.setattr(validation, "walk_forward",
                        lambda *a, **k: _folds([-5.0, -3.0, -8.0]))
    row = _FakeKnowledge()
    out = validate_candidate(row, "FAKE", days=160)
    assert out["status"] == "rejected"
    assert row.status == "rejected"
    assert row.oos_metrics["verdict"]["worth"] is False


def test_validate_too_few_folds_rejected(monkeypatch):
    """fold 數不足（< VALIDATION_MIN_FOLDS）→ 不採信 → rejected（即使 EV 為正）。"""
    monkeypatch.setattr(market_data, "get_bars", lambda symbol, days, source: _osc_df())
    monkeypatch.setattr(validation, "walk_forward", lambda *a, **k: _folds([99.0]))
    row = _FakeKnowledge()
    out = validate_candidate(row, "FAKE", days=160)
    assert out["status"] == "rejected"


def test_validate_empty_data_raises(monkeypatch):
    """抓不到資料 → 明確報錯，不默默通過。"""
    monkeypatch.setattr(market_data, "get_bars", lambda symbol, days, source: pd.DataFrame())
    try:
        validate_candidate(_FakeKnowledge(), "FAKE", days=160)
        assert False, "空資料應 raise ValueError"
    except ValueError:
        pass


if __name__ == "__main__":
    print("（evolution 測試需 pytest 的 monkeypatch，請用 pytest 執行）")
