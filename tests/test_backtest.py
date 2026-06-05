"""
回測引擎單元測試
================
用「假策略」餵入預先設定好的訊號序列，驗證回測引擎的數學計算正確。
完全不需連線 Alpaca。

⚠️ Phase 6 step-03 後，回測採「隔日成交」語意：訊號在第 i 根收盤算出，成交在第 i+1 根的
   開盤價（無 open 欄退回 close）。所以下面的序列都比訊號多一根「給它成交的次根」，
   且最後一根的訊號不會成交（沒有次根）。零成本（不帶 bps）時驗純粹的成交時點數學。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_backtest.py -q
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
    """買訊@bar0 → 次根 open=10 成交買；賣訊@bar2 → 次根 open=30 成交賣 → 賺 200%。"""
    df = pd.DataFrame({"open": [10, 10, 30, 30], "close": [10, 10, 30, 30]})
    strat = FakeStrategy([Signal.BUY, Signal.HOLD, Signal.SELL, Signal.HOLD])
    r = _run_on_df(strat, df, initial_cash=1000)
    assert r["final_equity"] == 3000, r
    assert r["total_return_pct"] == 200.0, r
    assert r["num_round_trips"] == 1, r
    assert r["win_rate_pct"] == 100.0, r
    print(f"✅ 買低賣高獲利測試通過（隔日成交）：報酬 {r['total_return_pct']}%")


def test_no_trades_when_all_hold():
    """全程觀望 → 沒有交易、資產不變。"""
    df = pd.DataFrame({"open": [10, 11, 12], "close": [10, 11, 12]})
    strat = FakeStrategy([Signal.HOLD, Signal.HOLD, Signal.HOLD])
    r = _run_on_df(strat, df, initial_cash=1000)
    assert r["num_trades"] == 0, r
    assert r["final_equity"] == 1000, r
    assert r["total_return_pct"] == 0.0, r
    print("✅ 全程觀望無交易測試通過")


def test_max_drawdown():
    """買@10、漲到20、再跌回10才賣 → 最大回撤 50%、報酬 0%（隔日成交版）。"""
    df = pd.DataFrame({
        "open": [10, 10, 20, 10, 10],
        "close": [10, 10, 20, 10, 10],
    })
    strat = FakeStrategy([Signal.BUY, Signal.HOLD, Signal.HOLD, Signal.SELL, Signal.HOLD])
    r = _run_on_df(strat, df, initial_cash=1000)
    assert r["max_drawdown_pct"] == 50.0, r
    assert r["total_return_pct"] == 0.0, r
    print(f"✅ 最大回撤測試通過：回撤 {r['max_drawdown_pct']}%")


def test_fills_on_next_bar_open_not_signal_close():
    """關鍵語意：訊號當根收盤跳空，但成交價要用『次根 open』，不是當根 close。"""
    # bar0 close=10 出買訊；bar1 跳空 open=12（成交價應是 12，不是 10）
    df = pd.DataFrame({
        "open": [10, 12, 12, 20],
        "close": [10, 18, 18, 20],
    })
    strat = FakeStrategy([Signal.BUY, Signal.HOLD, Signal.SELL, Signal.HOLD])
    r = _run_on_df(strat, df, initial_cash=1200)
    buys = [t for t in r["trades"] if t["side"] == "buy"]
    assert buys and buys[0]["price"] == 12.0, r["trades"]  # 買在次根 open=12，非當根 close=10
    print("✅ 隔日成交『買在次根開盤』測試通過")


def test_last_bar_signal_does_not_fill():
    """最後一根的訊號沒有次根可成交 → 誠實地不成交（不無中生有一筆）。"""
    df = pd.DataFrame({"open": [10, 10, 10], "close": [10, 10, 10]})
    strat = FakeStrategy([Signal.HOLD, Signal.HOLD, Signal.BUY])  # 買訊在最後一根
    r = _run_on_df(strat, df, initial_cash=1000)
    assert r["num_trades"] == 0, r
    assert r["final_equity"] == 1000, r
    print("✅ 最後一根訊號不成交測試通過")


# ============================================================
# 期望值（EV）指標測試
# ============================================================
def test_expected_value_two_round_trips():
    """
    手算驗 EV（隔日成交、零成本）：兩輪完整買賣，一賺一賠。
    成交價都用次根 open：
      第1輪 買@10 賣@15 → 100 股 → profit = +500
      第2輪 買@15 賣@12 → 100 股 → profit = -300
    profits = [+500, -300] → EV/筆 = 100、expectancy 10%、profit_factor 1.67。
    """
    df = pd.DataFrame({
        "open":  [10, 10, 15, 15, 15, 12, 12],
        "close": [10, 10, 15, 15, 15, 12, 12],
    })
    strat = FakeStrategy([
        Signal.BUY, Signal.HOLD, Signal.SELL, Signal.BUY, Signal.HOLD, Signal.SELL, Signal.HOLD
    ])
    r = _run_on_df(strat, df, initial_cash=1000)

    assert r["num_round_trips"] == 2, r
    assert r["num_wins"] == 1, r
    assert r["num_losses"] == 1, r
    assert r["win_rate_pct"] == 50.0, r
    assert r["avg_win"] == 500.0, r
    assert r["avg_loss"] == 300.0, r
    assert r["expected_value"] == 100.0, r        # ★核心：EV/筆
    assert r["expectancy_pct"] == 10.0, r
    assert r["profit_factor"] == 1.67, r
    print(f"✅ EV 兩輪交易測試通過：EV/筆 = {r['expected_value']}（PF={r['profit_factor']}）")


def test_profit_factor_none_when_no_loss():
    """全程沒有任何虧損 → 總賠為 0 → profit_factor 應回 None（避免除以 0）。"""
    df = pd.DataFrame({"open": [10, 10, 20, 20], "close": [10, 10, 20, 20]})
    strat = FakeStrategy([Signal.BUY, Signal.SELL, Signal.HOLD, Signal.HOLD])
    r = _run_on_df(strat, df, initial_cash=1000)

    assert r["num_losses"] == 0, r
    assert r["avg_loss"] == 0.0, r
    assert r["profit_factor"] is None, r          # 無虧損 → None
    assert r["expected_value"] == 1000.0, r       # 單筆賺 1000
    assert r["expectancy_pct"] == 100.0, r
    print("✅ 無虧損 profit_factor=None 測試通過")


def test_zero_cost_total_cost_is_zero():
    """不帶成本參數（預設 0）時，total_cost 應為 0（與舊行為相容，只差成交時點）。"""
    df = pd.DataFrame({"open": [10, 10, 20, 20], "close": [10, 10, 20, 20]})
    strat = FakeStrategy([Signal.BUY, Signal.SELL, Signal.HOLD, Signal.HOLD])
    r = _run_on_df(strat, df, initial_cash=1000)
    assert r["total_cost"] == 0.0, r
    print("✅ 零成本 total_cost=0 測試通過")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
