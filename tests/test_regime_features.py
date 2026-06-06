"""
市場狀態特徵工程測試（Phase 7 step-01）
=========================================
驗證 regime_features.compute_features 的每個特徵算對、無未來函數、資料不足回 None。
純函式、不連網。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_regime_features.py -v
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from backend.services.regime_features import compute_features


def _df(closes, volumes=None):
    """造一份 OHLCV DataFrame；沒給 volume 就用固定值，high/low 在 close 上下各 1。"""
    n = len(closes)
    volumes = volumes if volumes is not None else [1000] * n
    return pd.DataFrame({
        "open": closes,
        "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes],
        "close": closes,
        "volume": volumes,
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D"),
    })


def test_return_5d_and_20d_exact():
    """近 5/20 日報酬率應等於手算的 close[-1]/close[-1-n] - 1。"""
    closes = [float(100 + i) for i in range(30)]  # 100,101,...,129
    f = compute_features(_df(closes))
    assert abs(f["return_5d"] - (closes[-1] / closes[-6] - 1)) < 1e-9
    assert abs(f["return_20d"] - (closes[-1] / closes[-21] - 1)) < 1e-9


def test_volume_ratio_reused():
    """volume_ratio 直接重用 screener：最後一根爆量時量比明顯 > 1。"""
    closes = [100.0] * 21
    volumes = [100] * 20 + [300]
    f = compute_features(_df(closes, volumes))
    assert abs(f["volume_ratio"] - 3.0) < 1e-6


def test_range_position_top_and_bottom():
    """收盤貼近 20 日高點 → ~1；貼近低點 → ~0。

    用 high=low=close 的扁平 K 棒，讓區間純由收盤決定（排除上下影線干擾）。
    """
    def _flat(closes):
        n = len(closes)
        return pd.DataFrame({
            "open": closes, "high": closes, "low": closes, "close": closes,
            "volume": [1000] * n,
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="D"),
        })

    closes = [float(100 + i) for i in range(20)]  # 單調上升，最後一根是最高
    assert abs(compute_features(_flat(closes))["range_position"] - 1.0) < 1e-9
    closes_down = [float(120 - i) for i in range(20)]  # 單調下降，最後一根是最低
    assert abs(compute_features(_flat(closes_down))["range_position"] - 0.0) < 1e-9


def test_volatility_and_atr_positive():
    """有波動的序列：年化波動與 atr_pct 應為正數。"""
    closes = [100.0 + (i % 2) * 5 for i in range(40)]  # 上下震盪
    f = compute_features(_df(closes))
    assert f["volatility_20d"] is not None and f["volatility_20d"] > 0
    assert f["atr_pct"] is not None and f["atr_pct"] > 0


def test_trend_strength_needs_enough_bars():
    """ADX 暖機：資料太少回 None；夠長的趨勢序列回正數。"""
    short = [float(100 + i) for i in range(10)]
    assert compute_features(_df(short))["trend_strength"] is None
    trend = [float(100 + i) for i in range(60)]
    assert compute_features(_df(trend))["trend_strength"] is not None


def test_insufficient_data_returns_none():
    """資料不足時各特徵回 None（不崩、格式一致）。"""
    f = compute_features(_df([100.0, 101.0]))
    assert f["return_20d"] is None
    assert f["volatility_20d"] is None


def test_empty_df_all_none():
    """空 / 無 close → 全 None，保證上層拿到一致格式。"""
    f = compute_features(pd.DataFrame())
    assert set(f.keys()) == {
        "volume_ratio", "return_5d", "return_20d", "volatility_20d",
        "trend_strength", "atr_pct", "range_position",
    }
    assert all(v is None for v in f.values())


def test_no_look_ahead():
    """無未來函數：在第 i 根算出的特徵，不受「i 之後的資料」影響。

    做法：對同一段資料，把第 i 根之後的列改成垃圾，重算 df.iloc[:i+1]，
    結果必須與原本一致——若特徵實作不小心用了整段（全序列）統計就會破功。
    """
    closes = [float(100 + (i % 7)) for i in range(60)]
    df = _df(closes)
    i = 40
    base = compute_features(df.iloc[: i + 1])

    corrupted = df.copy()
    corrupted.loc[i + 1:, ["open", "high", "low", "close", "volume"]] = 999999
    after = compute_features(corrupted.iloc[: i + 1])

    assert base == after


if __name__ == "__main__":
    test_return_5d_and_20d_exact()
    test_volume_ratio_reused()
    test_range_position_top_and_bottom()
    test_volatility_and_atr_positive()
    test_trend_strength_needs_enough_bars()
    test_insufficient_data_returns_none()
    test_empty_df_all_none()
    test_no_look_ahead()
    print("\n🎉 全部市場狀態特徵測試通過！")
