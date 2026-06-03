"""
歷史 K 線 API 測試
==================
兩部分：
1. _to_candles 純函式：DataFrame → lightweight-charts candle 陣列（含 NaN 跳過）
2. GET /bars/{symbol} 整合測試（用 TestClient，把 get_bars 換成假資料，免連網）

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe tests\\test_bars.py
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app
import backend.routers.bars as bars_router
from backend.routers.bars import _to_candles


def _fake_df():
    """造一份假的日 K DataFrame（含一根 NaN 缺值，預期會被跳過）。"""
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-06-01", "2026-06-02", "2026-06-03"]),
            "open": [100.0, 101.0, np.nan],  # 第三根缺值 → 應被跳過
            "high": [102.0, 103.0, 104.0],
            "low": [99.0, 100.5, 101.0],
            "close": [101.0, 102.5, 103.0],
            "volume": [1000, 2000, 3000],
        }
    )


# ---------- 1. 純函式 ----------
def test_to_candles_basic():
    """正常欄位應正確轉成 candle，time 為 YYYY-MM-DD 字串。"""
    candles = _to_candles(_fake_df())
    # 三根裡有一根 NaN，應只剩兩根
    assert len(candles) == 2, candles
    first = candles[0]
    assert first["time"] == "2026-06-01", first
    assert first["open"] == 100.0 and first["close"] == 101.0, first
    assert isinstance(first["volume"], int), first


def test_to_candles_empty():
    """空 DataFrame 應回空陣列，不報錯。"""
    assert _to_candles(pd.DataFrame()) == []
    print("✅ _to_candles 純函式通過")


# ---------- 2. API 整合 ----------
def test_bars_endpoint(monkeypatch):
    """GET /bars/{symbol} 應回 candles；把 get_bars 換成假資料免連網。"""
    monkeypatch.setattr(bars_router, "get_bars", lambda symbol, days=120, source="alpaca": _fake_df())
    with TestClient(app) as client:
        resp = client.get("/bars/aapl?days=30")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["symbol"] == "AAPL", body
        assert len(body["candles"]) == 2, body
    print("✅ GET /bars 整合通過")


if __name__ == "__main__":
    test_to_candles_basic()
    test_to_candles_empty()
    # __main__ 直跑時沒有 pytest monkeypatch，手動替換再還原
    _orig = bars_router.get_bars
    bars_router.get_bars = lambda symbol, days=120, source="alpaca": _fake_df()
    try:
        with TestClient(app) as client:
            resp = client.get("/bars/aapl?days=30")
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["symbol"] == "AAPL" and len(body["candles"]) == 2, body
        print("✅ GET /bars 整合通過")
    finally:
        bars_router.get_bars = _orig
    print("\n🎉 全部 K 線 API 測試通過！")
