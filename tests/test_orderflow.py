"""
買賣壓代理單元測試（Phase 11 step-03）
======================================
純函式、不連網。重點驗：
- 恆等式 buy_vol_proxy + sell_vol_proxy == volume（含平盤 / 零量）。
- 上漲根 buy>0 且 sell==0；下跌根反之；平盤 / 首根對半。
- net_pressure / pressure_ratio 數值正確。
- 無未來函數：df.iloc[:i+1] 與完整 df 在第 i 根算出同值。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_orderflow.py -q
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

from backend.services.orderflow_proxy import compute_orderflow


def _df():
    """close 走勢含：首根 / 漲 / 跌 / 平盤 / 漲，量各不同。"""
    return pd.DataFrame(
        {
            "close": [10.0, 11.0, 10.0, 10.0, 12.0],
            "volume": [100.0, 200.0, 300.0, 400.0, 500.0],
        }
    )


def test_identity_buy_plus_sell_equals_volume():
    """恆等式：每一根 buy + sell == volume（代理把總量完整歸給買 / 賣）。"""
    out = compute_orderflow(_df())
    total = out["buy_vol_proxy"] + out["sell_vol_proxy"]
    assert (total == out["volume"]).all(), out[["volume", "buy_vol_proxy", "sell_vol_proxy"]]


def test_direction_rules():
    """漲根全買、跌根全賣、平盤 / 首根對半。"""
    out = compute_orderflow(_df())
    buy, sell = out["buy_vol_proxy"].tolist(), out["sell_vol_proxy"].tolist()
    # 首根（無前根）→ 對半 50/50
    assert buy[0] == 50.0 and sell[0] == 50.0
    # 漲根（11>10）→ 全買
    assert buy[1] == 200.0 and sell[1] == 0.0
    # 跌根（10<11）→ 全賣
    assert buy[2] == 0.0 and sell[2] == 300.0
    # 平盤（10==10）→ 對半
    assert buy[3] == 200.0 and sell[3] == 200.0
    # 漲根（12>10）→ 全買
    assert buy[4] == 500.0 and sell[4] == 0.0


def test_net_pressure_and_ratio():
    """net = buy − sell；ratio = buy / (buy+sell)。"""
    out = compute_orderflow(_df())
    assert out["net_pressure"].tolist() == [0.0, 200.0, -300.0, 0.0, 500.0]
    assert out["pressure_ratio"].tolist() == [0.5, 1.0, 0.0, 0.5, 1.0]


def test_zero_volume_ratio_is_neutral():
    """零量 → 恆等式仍成立（buy+sell==0），ratio 給中性 0.5（不除以 0）。"""
    out = compute_orderflow(pd.DataFrame({"close": [10.0, 11.0], "volume": [0.0, 0.0]}))
    assert (out["buy_vol_proxy"] + out["sell_vol_proxy"] == out["volume"]).all()
    assert out["pressure_ratio"].tolist() == [0.5, 0.5]


def test_no_look_ahead():
    """第 i 根只看自己 + 前一根 → 對切片與完整 df 算出同值（無未來函數）。"""
    full = compute_orderflow(_df())
    for i in range(len(full)):
        partial = compute_orderflow(_df().iloc[: i + 1])
        assert partial["buy_vol_proxy"].iloc[i] == full["buy_vol_proxy"].iloc[i], i
        assert partial["sell_vol_proxy"].iloc[i] == full["sell_vol_proxy"].iloc[i], i


def test_empty_returns_empty():
    """空 df → 回空，不崩。"""
    assert compute_orderflow(pd.DataFrame()).empty


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
