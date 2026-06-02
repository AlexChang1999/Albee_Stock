"""
回測引擎單元測試
================
用「假策略」餵入預先設定好的訊號序列，驗證回測引擎的數學計算正確。
完全不需連線 Alpaca。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe tests\\test_backtest.py
"""

import sys
from pathlib import Path

# Windows 主控台 cp950 印 emoji 會崩潰，強制改 UTF-8
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
    """測試用假策略：依照預先設定的訊號序列，第 N 天就回傳第 N 個訊號。"""

    def __init__(self, signals):
        super().__init__({})
        self.signals = signals

    def generate_signal(self, df):
        idx = len(df) - 1  # 目前走到第幾天（從 0 算）
        return self.signals[idx], "測試訊號"


def test_buy_low_sell_high_profit():
    """價格 10→20→30，第一天買、最後一天賣 → 賺 200%。"""
    df = pd.DataFrame({"close": [10, 20, 30]})
    strat = FakeStrategy([Signal.BUY, Signal.HOLD, Signal.SELL])
    r = _run_on_df(strat, df, initial_cash=1000)
    assert r["final_equity"] == 3000, r
    assert r["total_return_pct"] == 200.0, r
    assert r["num_round_trips"] == 1, r
    assert r["win_rate_pct"] == 100.0, r
    assert r["buy_and_hold_pct"] == 200.0, r
    print(f"✅ 買低賣高獲利測試通過：報酬 {r['total_return_pct']}%")


def test_no_trades_when_all_hold():
    """全程觀望 → 沒有交易、資產不變。"""
    df = pd.DataFrame({"close": [10, 11, 12]})
    strat = FakeStrategy([Signal.HOLD, Signal.HOLD, Signal.HOLD])
    r = _run_on_df(strat, df, initial_cash=1000)
    assert r["num_trades"] == 0, r
    assert r["final_equity"] == 1000, r
    assert r["total_return_pct"] == 0.0, r
    print("✅ 全程觀望無交易測試通過")


def test_max_drawdown():
    """買在10、漲到20、再跌回10才賣 → 最大回撤 50%、報酬 0%。"""
    df = pd.DataFrame({"close": [10, 20, 10]})
    strat = FakeStrategy([Signal.BUY, Signal.HOLD, Signal.SELL])
    r = _run_on_df(strat, df, initial_cash=1000)
    assert r["max_drawdown_pct"] == 50.0, r
    assert r["total_return_pct"] == 0.0, r
    print(f"✅ 最大回撤測試通過：回撤 {r['max_drawdown_pct']}%")


# ============================================================
# 期望值（EV）指標測試 ── Phase 5 新增
# ============================================================
def test_expected_value_two_round_trips():
    """
    手算驗 EV：兩輪完整買賣，一賺一賠。
    本金 1000：
      第1輪 買@10 賣@15 → 100 股 → profit = +500，現金變 1500
      第2輪 買@15 賣@12 → 100 股 → profit = -300，現金變 1200
    profits = [+500, -300]
      勝率 50% / 敗率 50%；avg_win=500 / avg_loss=300
      EV/筆 = (500 - 300) / 2 = 100
      expectancy = 100 / 1000 = 10%
      profit_factor = 500 / 300 = 1.67
    """
    df = pd.DataFrame({"close": [10, 15, 15, 12]})
    strat = FakeStrategy([Signal.BUY, Signal.SELL, Signal.BUY, Signal.SELL])
    r = _run_on_df(strat, df, initial_cash=1000)

    assert r["num_round_trips"] == 2, r
    assert r["num_wins"] == 1, r
    assert r["num_losses"] == 1, r
    assert r["win_rate_pct"] == 50.0, r
    assert r["loss_rate_pct"] == 50.0, r
    assert r["avg_win"] == 500.0, r
    assert r["avg_loss"] == 300.0, r
    assert r["expected_value"] == 100.0, r        # ★核心：EV/筆
    assert r["expectancy_pct"] == 10.0, r
    assert r["profit_factor"] == 1.67, r
    print(f"✅ EV 兩輪交易測試通過：EV/筆 = {r['expected_value']}（PF={r['profit_factor']}）")


def test_profit_factor_none_when_no_loss():
    """全程沒有任何虧損 → 總賠為 0 → profit_factor 應回 None（避免除以 0）。"""
    df = pd.DataFrame({"close": [10, 20]})
    strat = FakeStrategy([Signal.BUY, Signal.SELL])
    r = _run_on_df(strat, df, initial_cash=1000)

    assert r["num_losses"] == 0, r
    assert r["avg_loss"] == 0.0, r
    assert r["profit_factor"] is None, r          # 無虧損 → None
    assert r["expected_value"] == 1000.0, r       # 單筆賺 1000
    assert r["expectancy_pct"] == 100.0, r
    print("✅ 無虧損 profit_factor=None 測試通過")


if __name__ == "__main__":
    test_buy_low_sell_high_profit()
    test_no_trades_when_all_hold()
    test_max_drawdown()
    test_expected_value_two_round_trips()
    test_profit_factor_none_when_no_loss()
    print("\n🎉 全部回測引擎測試通過！")
