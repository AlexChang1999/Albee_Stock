"""
AI 海選（漏斗式篩選）單元測試
================================
驗證 services/screener.py 的兩件事，完全不連網路（monkeypatch 掉資料源）：
1. 量比計算（_volume_ratio）正確、資料不足時回 None。
2. screen() 的漏斗：量比過關才進第二層、第二層 EV 門檻、依 EV 排序、跳過抓不到資料的標的。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_screener.py
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

from backend.services import screener


def _make_df(n=60, last_volume=1000, base_volume=1000, seed=0):
    """造一份 n 根的 K 線；最後一根成交量可獨立指定（模擬爆量）。"""
    close = pd.Series(100 + np.cumsum(np.random.RandomState(seed).randn(n)))
    vol = pd.Series([float(base_volume)] * n)
    vol.iloc[-1] = float(last_volume)
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n),
        "open": close, "high": close + 1, "low": close - 1,
        "close": close, "volume": vol,
    })


def test_volume_ratio_basic():
    """最後一根 5000、其餘 1000 → 量比約 5000/1000ish（含最後一根進均值，略小於5）。"""
    df = _make_df(last_volume=5000, base_volume=1000)
    ratio = screener._volume_ratio(df, ma_window=20)
    assert ratio is not None
    assert ratio > 3  # 明顯爆量


def test_volume_ratio_insufficient_data():
    """資料不足 ma_window 根 → 回 None（無法判斷、淘汰）。"""
    df = _make_df(n=10)
    assert screener._volume_ratio(df, ma_window=20) is None


def test_screen_funnel(monkeypatch):
    """
    三檔股票：
      HOT  爆量 → 第一層過關
      CALM 平量 → 第一層淘汰
      DEAD 抓不到資料 → skipped
    驗證只有 HOT 進到推薦（或至少 CALM/DEAD 不進）、結果依 EV 排序。
    """
    def fake_get_bars(symbol, days=60, source="alpaca"):
        if symbol == "HOT":
            return _make_df(last_volume=8000, base_volume=1000, seed=1)
        if symbol == "CALM":
            return _make_df(last_volume=1000, base_volume=1000, seed=2)
        return pd.DataFrame()  # DEAD：空資料

    monkeypatch.setattr(screener.market_data, "get_bars", fake_get_bars)

    result = screener.screen(
        symbols=["HOT", "CALM", "DEAD"],
        days=60,
        volume_multiplier=2.5,
        min_ev=float("-inf"),  # 不卡 EV，專測量能漏斗
        source="yfinance",
    )

    assert result["universe_size"] == 3
    assert "HOT" in result["layer1_passed"]
    assert "CALM" not in result["layer1_passed"]
    assert "DEAD" in result["skipped"]

    # 推薦只可能來自過關的 HOT
    rec_symbols = {r["symbol"] for r in result["recommendations"]}
    assert rec_symbols <= {"HOT"}

    # 若有推薦，須依 EV 由高到低排序
    evs = [r["metrics"]["expected_value"] for r in result["recommendations"]]
    assert evs == sorted(evs, reverse=True)


def test_screen_min_ev_filter(monkeypatch):
    """min_ev 設超高 → 沒有任何推薦能過關。"""
    monkeypatch.setattr(
        screener.market_data, "get_bars",
        lambda symbol, days=60, source="alpaca": _make_df(last_volume=8000, seed=3),
    )
    result = screener.screen(
        symbols=["HOT"], volume_multiplier=2.5, min_ev=1e9, source="yfinance"
    )
    assert result["recommendations"] == []
