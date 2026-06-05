"""
回測成本模型測試（Phase 6 step-02）
====================================
驗證手續費 / 滑價有正確吃進回測，讓 EV 變誠實：
- 滑價：買在較高價、賣在較低價，EV 下降，total_cost 反映摩擦。
- 手續費：買賣各扣一次，金額正確。
- 高頻（交易筆數多）→ total_cost 明顯較高、EV 被侵蝕較多。

純函式手算驗證，不連網。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_cost_model.py -q
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

from backend.services.backtest_engine import _run_on_df
from backend.strategies.base import BaseStrategy, Signal


class FakeStrategy(BaseStrategy):
    def __init__(self, signals):
        super().__init__({})
        self.signals = signals

    def generate_signal(self, df):
        return self.signals[len(df) - 1], "測試訊號"


# 一輪買賣：買訊@bar0→次根 open=10 成交；賣訊@bar2→次根 open=20 成交
_ONE_RT_DF = pd.DataFrame({"open": [10, 10, 20, 20], "close": [10, 10, 20, 20]})
_ONE_RT_SIGNALS = [Signal.BUY, Signal.HOLD, Signal.SELL, Signal.HOLD]


def test_slippage_lowers_ev_and_records_cost():
    """滑價 1%（100 bps）：買在 10.1、賣在 19.8，EV 應低於零成本，total_cost 手算對得上。"""
    strat = lambda: FakeStrategy(_ONE_RT_SIGNALS)
    zero = _run_on_df(strat(), _ONE_RT_DF, 1000)
    cost = _run_on_df(strat(), _ONE_RT_DF, 1000, slippage_bps=100)

    assert zero["total_cost"] == 0.0, zero
    assert cost["expected_value"] < zero["expected_value"], (cost["expected_value"], zero["expected_value"])
    # 滑價成本 = 買 qty×(10.1−10) + 賣 qty×(20−19.8)；qty = 1000/10.1 ≈ 99.0099
    #          = 99.0099×0.1 + 99.0099×0.2 = 9.901 + 19.802 = 29.70
    assert cost["total_cost"] == 29.7, cost["total_cost"]
    print(f"✅ 滑價侵蝕 EV 測試通過：零成本 EV={zero['expected_value']} → 含滑價 EV={cost['expected_value']}")


def test_commission_charged_both_sides():
    """手續費 1%（100 bps）、無滑價：買賣各扣一次，total_cost 手算對得上。"""
    cost = _run_on_df(FakeStrategy(_ONE_RT_SIGNALS), _ONE_RT_DF, 1000, commission_bps=100)
    # 買：notional=1000/1.01=990.099，手續費=9.901；qty=99.0099
    # 賣：gross=99.0099×20=1980.198，手續費=19.802
    # total_cost = 9.901 + 19.802 = 29.70
    assert cost["total_cost"] == 29.7, cost["total_cost"]
    # 賣出淨利 = 1960.396 − 990.099 = 970.30
    assert cost["expected_value"] == 970.3, cost["expected_value"]
    print("✅ 手續費買賣各扣一次測試通過")


def test_high_frequency_pays_more_cost():
    """同滑價下，交易筆數多（兩輪）的 total_cost 要明顯高於只交易一輪。"""
    one = _run_on_df(FakeStrategy(_ONE_RT_SIGNALS), _ONE_RT_DF, 1000, slippage_bps=50)

    two_df = pd.DataFrame({
        "open":  [10, 10, 15, 15, 15, 12, 12],
        "close": [10, 10, 15, 15, 15, 12, 12],
    })
    two_signals = [
        Signal.BUY, Signal.HOLD, Signal.SELL, Signal.BUY, Signal.HOLD, Signal.SELL, Signal.HOLD
    ]
    two = _run_on_df(FakeStrategy(two_signals), two_df, 1000, slippage_bps=50)

    assert two["num_round_trips"] == 2 and one["num_round_trips"] == 1
    assert two["total_cost"] > one["total_cost"], (two["total_cost"], one["total_cost"])
    print(f"✅ 高頻成本較高測試通過：一輪 {one['total_cost']} < 兩輪 {two['total_cost']}")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
