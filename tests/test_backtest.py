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

from backend.services.backtest_engine import _run_on_df, _resolve_source
from backend.services.analytics import returns_from_equity
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


# ============================================================
# 環境特徵管線測試（Phase 11 step-04）
# ============================================================
class FeatureReadingStrategy(BaseStrategy):
    """測試用：讀 features 欄 macro_flag——為 1 時 BUY、否則 HOLD。

    若 df 沒有 macro_flag 欄（沒傳 features）→ 一律 HOLD。用來驗「features 確實到得了策略」。
    """

    def __init__(self):
        super().__init__({})

    def generate_signal(self, df):
        row = df.iloc[-1]
        if "macro_flag" in df.columns and row["macro_flag"] == 1:
            return Signal.BUY, "macro_flag=1"
        return Signal.HOLD, "無旗標"


def test_features_reach_strategy():
    """傳合成 features 給 _run_on_df，策略讀得到 → 訊號確實受其影響而進場。"""
    df = pd.DataFrame({"open": [10, 10, 20, 20], "close": [10, 10, 20, 20]})
    # macro_flag 在 bar0=1（觸發買，次根 open=10 成交），bar2=0（不賣，無 sell）
    feats = pd.DataFrame({"macro_flag": [1, 0, 0, 0]})
    r = _run_on_df(FeatureReadingStrategy(), df, initial_cash=1000, features=feats)
    buys = [t for t in r["trades"] if t["side"] == "buy"]
    assert buys and buys[0]["price"] == 10.0, r["trades"]  # features 驅動的進場
    # 對照：不傳 features → 同策略讀不到旗標 → 全程 HOLD、無交易
    r0 = _run_on_df(FeatureReadingStrategy(), df, initial_cash=1000)
    assert r0["num_trades"] == 0, r0
    print("✅ features 到得了策略測試通過（訊號受 features 影響）")


def test_features_do_not_touch_fill_price():
    """features 只進訊號層，不得碰成交價：成交價仍 = 次根開盤（與不帶 features 一致）。"""
    # 訊號當根 close 跳空，成交應走次根 open=12（不因 features 改變）
    df = pd.DataFrame({"open": [10, 12, 12, 20], "close": [10, 18, 18, 20]})
    feats = pd.DataFrame({"macro_flag": [1, 0, 0, 0]})
    r = _run_on_df(FeatureReadingStrategy(), df, initial_cash=1200, features=feats)
    buys = [t for t in r["trades"] if t["side"] == "buy"]
    assert buys and buys[0]["price"] == 12.0, r["trades"]  # 次根 open，非當根 close=18
    print("✅ features 不碰成交價測試通過（成交仍走次根開盤）")


def test_backward_compat_strategy_ignoring_features():
    """向後相容硬斷言：忽略 features 的舊策略，帶 / 不帶 features 跑出完全相同結果。"""
    df = pd.DataFrame({"open": [10, 10, 20, 20], "close": [10, 10, 20, 20]})
    strat_signals = [Signal.BUY, Signal.SELL, Signal.HOLD, Signal.HOLD]
    feats = pd.DataFrame({"vix_level": [12.0, 35.0, 20.0, 18.0]})  # 舊策略根本不看
    r_with = _run_on_df(FakeStrategy(list(strat_signals)), df, initial_cash=1000, features=feats)
    r_without = _run_on_df(FakeStrategy(list(strat_signals)), df, initial_cash=1000)
    assert r_with["final_equity"] == r_without["final_equity"], (r_with, r_without)
    assert r_with["trades"] == r_without["trades"], (r_with, r_without)
    assert r_with["equity_curve"] == r_without["equity_curve"], (r_with, r_without)
    print("✅ 向後相容測試通過（舊策略帶/不帶 features 結果完全相同）")


# ============================================================
# 報表真實日期：equity_dates + returns_from_equity dates 參數
# ============================================================
def test_equity_dates_align_with_curve_and_use_real_dates():
    """equity_dates 與 equity_curve 等長；有 timestamp 欄時帶的是真實日期（非 str index）。"""
    df = pd.DataFrame({
        "timestamp": ["2000-01-03", "2000-01-04", "2000-01-05", "2000-01-06"],
        "open":  [10, 10, 30, 30],
        "close": [10, 10, 30, 30],
    })
    strat = FakeStrategy([Signal.BUY, Signal.HOLD, Signal.SELL, Signal.HOLD])
    r = _run_on_df(strat, df, initial_cash=1000)
    assert "equity_dates" in r, r
    assert len(r["equity_dates"]) == len(r["equity_curve"]), r
    assert r["equity_dates"][0] == "2000-01-03", r["equity_dates"]
    assert r["equity_dates"][-1] == "2000-01-06", r["equity_dates"]
    print("✅ equity_dates 對齊且為真實日期測試通過")


def test_equity_dates_fallback_to_index_without_timestamp():
    """沒有 timestamp 欄時 date 退回字串化的索引（不爆，下游解析失敗會退回假 2000）。"""
    df = pd.DataFrame({"open": [10, 10, 20], "close": [10, 10, 20]})
    strat = FakeStrategy([Signal.BUY, Signal.HOLD, Signal.HOLD])
    r = _run_on_df(strat, df, initial_cash=1000)
    assert r["equity_dates"] == ["0", "1", "2"], r["equity_dates"]
    print("✅ 無 timestamp 退回索引測試通過")


def test_returns_from_equity_real_vs_fake_dates():
    """傳合法 dates → 索引變真實年份；不傳 → 退回假 2000（向後相容、可重現）。"""
    equity = [1000, 1010, 1025, 1005]
    dates = ["2024-03-01", "2024-03-04", "2024-03-05", "2024-03-06"]
    rets_real = returns_from_equity(equity, dates=dates)
    # pct_change drop 第一筆，故索引對齊 dates[1:]
    assert str(rets_real.index[0].date()) == "2024-03-04", rets_real.index
    assert rets_real.index[0].year == 2024, rets_real.index

    rets_fake = returns_from_equity(equity)  # 不傳 → 假 2000
    assert rets_fake.index[0].year == 2000, rets_fake.index
    print("✅ returns_from_equity 真/假日期測試通過")


def test_returns_from_equity_bad_dates_fallback():
    """dates 含無法解析的值 → 整串退回假 2000（不讓報表爆）。"""
    equity = [1000, 1010, 1020]
    rets = returns_from_equity(equity, dates=["x", "y", "z"])
    assert rets.index[0].year == 2000, rets.index
    print("✅ 壞日期退回假 2000 測試通過")


# ============================================================
# 長區間自動選資料源（_resolve_source）
# ============================================================
def test_resolve_source_switches_to_yfinance_on_long_range():
    """alpaca + days 超過上限 → 自動改 yfinance；短區間不變；顯式 yfinance 不變。"""
    from backend.services.backtest_engine import ALPACA_MAX_DAYS
    assert _resolve_source("alpaca", ALPACA_MAX_DAYS + 1) == "yfinance"
    assert _resolve_source("alpaca", 365) == "alpaca"
    assert _resolve_source("yfinance", 9500) == "yfinance"  # 顯式不覆寫
    print("✅ 長區間自動選 yfinance 測試通過")


from backend.strategies.base import ScriptStrategy


class _ThreshVec(BaseStrategy):
    """向量化版：今天收盤 > 昨天 → buy，否則 sell（無狀態，每根都表態）。"""

    def generate_signal(self, df):
        if len(df) < 2:
            return Signal.HOLD, "資料不足"
        if float(df["close"].iloc[-1]) > float(df["close"].iloc[-2]):
            return Signal.BUY, "漲"
        return Signal.SELL, "跌"


class _ThreshScript(ScriptStrategy):
    """事件式版：邏輯與 _ThreshVec 完全相同，但用 on_bar + ctx 寫。"""

    def on_bar(self, ctx, bar):
        closes = ctx.history["close"]
        if len(closes) < 2:
            return
        if float(closes.iloc[-1]) > float(closes.iloc[-2]):
            ctx.buy("漲")
        else:
            ctx.sell("跌")


def test_script_strategy_equivalent_to_vectorized():
    """
    等價性鐵則：同一條決策規則，向量化 vs 事件式 ScriptStrategy 走同一成交核心，
    回測結果（EV / 報酬 / 交易筆數 / 資金曲線）必須完全一致 → 證明無第二條成交路徑分岔。
    """
    import numpy as np
    rng = np.random.default_rng(42)
    prices = (100 + np.cumsum(rng.standard_normal(200))).round(2)
    df = pd.DataFrame({
        "open": prices, "high": prices + 0.5, "low": prices - 0.5,
        "close": prices, "volume": 1000,
        "timestamp": pd.date_range("2020-01-01", periods=200),
    })

    vec = _run_on_df(_ThreshVec({}), df, 10000.0, commission_bps=2, slippage_bps=5)
    scr = _run_on_df(_ThreshScript({}), df, 10000.0, commission_bps=2, slippage_bps=5)

    assert vec["expected_value"] == scr["expected_value"], (vec["expected_value"], scr["expected_value"])
    assert vec["total_return_pct"] == scr["total_return_pct"]
    assert vec["num_trades"] == scr["num_trades"]
    assert vec["equity_curve"] == scr["equity_curve"]
    assert vec["trades"] == scr["trades"]
    print(f"✅ ScriptStrategy 等價性測試通過：兩路徑 EV={scr['expected_value']}、{scr['num_trades']} 筆交易完全一致")


# ============================================================
# 風控出場模擬（opt-in 停損 / 停利 / 追蹤止損）
# ============================================================

def test_stop_loss_triggers_intrabar():
    """進場 10，停損 10%（觸價 9）：當根 low 跌到 8 → 以 9 出場，資產 900。"""
    df = pd.DataFrame({
        "open":  [10, 10, 10, 10],
        "high":  [10, 10, 10, 10],
        "low":   [10, 10, 8, 10],
        "close": [10, 10, 9.5, 10],
    })
    strat = FakeStrategy([Signal.BUY, Signal.HOLD, Signal.HOLD, Signal.HOLD])
    r = _run_on_df(strat, df, initial_cash=1000, stop_loss_pct=0.10)
    assert r["num_stop_loss"] == 1, r
    sells = [t for t in r["trades"] if t["side"] == "sell"]
    assert sells[0]["exit_reason"] == "stop_loss", sells
    assert sells[0]["price"] == 9.0, sells
    assert r["final_equity"] == 900.0, r


def test_stop_loss_gap_down_fills_at_open():
    """跳空開低穿過停損（觸價 9、開盤 7）→ 只能成交在更差的開盤價 7（保守不美化）。"""
    df = pd.DataFrame({
        "open":  [10, 10, 7],
        "high":  [10, 10, 7.5],
        "low":   [10, 10, 6.5],
        "close": [10, 10, 7],
    })
    strat = FakeStrategy([Signal.BUY, Signal.HOLD, Signal.HOLD])
    r = _run_on_df(strat, df, initial_cash=1000, stop_loss_pct=0.10)
    assert r["num_stop_loss"] == 1, r
    sells = [t for t in r["trades"] if t["side"] == "sell"]
    assert sells[0]["price"] == 7.0, sells
    assert r["final_equity"] == 700.0, r


def test_take_profit_triggers_intrabar():
    """進場 10，停利 20%（觸價 12）：當根 high 衝到 13 → 以 12 出場，資產 1200。"""
    df = pd.DataFrame({
        "open":  [10, 10, 10, 10],
        "high":  [10, 10, 13, 10],
        "low":   [10, 10, 10, 10],
        "close": [10, 10, 11, 10],
    })
    strat = FakeStrategy([Signal.BUY, Signal.HOLD, Signal.HOLD, Signal.HOLD])
    r = _run_on_df(strat, df, initial_cash=1000, take_profit_pct=0.20)
    assert r["num_take_profit"] == 1, r
    sells = [t for t in r["trades"] if t["side"] == "sell"]
    assert sells[0]["exit_reason"] == "take_profit", sells
    assert sells[0]["price"] == 12.0, sells
    assert r["final_equity"] == 1200.0, r


def test_trailing_stop_uses_prior_peak():
    """
    進場 10 → 漲到 20（peak）→ 回落跌破 20×(1−10%)=18 → 以 18 出場。
    驗證 peak 用「前面 bar 為止」的最高價：漲到 20 那根自己不會被 9（舊 peak 10 的觸價）觸發。
    """
    df = pd.DataFrame({
        "open":  [10, 10, 19, 19, 19],
        "high":  [10, 10, 20, 19, 19],
        "low":   [10, 10, 19, 17, 19],
        "close": [10, 10, 20, 18, 19],
    })
    strat = FakeStrategy([Signal.BUY] + [Signal.HOLD] * 4)
    r = _run_on_df(strat, df, initial_cash=1000, trailing_stop_pct=0.10)
    assert r["num_trailing_stop"] == 1, r
    sells = [t for t in r["trades"] if t["side"] == "sell"]
    assert sells[0]["exit_reason"] == "trailing_stop", sells
    assert sells[0]["price"] == 18.0, sells
    assert r["final_equity"] == 1800.0, r


def test_risk_params_off_behavior_unchanged():
    """不帶風控參數（預設 None）→ 即使日內大跌也不觸發，行為與舊版完全相同。"""
    df = pd.DataFrame({
        "open":  [10, 10, 10, 30],
        "high":  [10, 10, 10, 30],
        "low":   [10, 10, 5, 30],   # 日內曾腰斬，但沒開停損就不該出場
        "close": [10, 10, 10, 30],
    })
    strat = FakeStrategy([Signal.BUY, Signal.HOLD, Signal.SELL, Signal.HOLD])
    r = _run_on_df(strat, df, initial_cash=1000)
    assert r["num_stop_loss"] == 0 and r["num_take_profit"] == 0 and r["num_trailing_stop"] == 0, r
    sells = [t for t in r["trades"] if t["side"] == "sell"]
    assert sells[0]["exit_reason"] == "signal", sells
    assert r["final_equity"] == 3000.0, r


def test_reentry_after_risk_exit():
    """風控出場後空手，策略再給 BUY → 次根照常再進場（風控不會把 Bot 卡死）。"""
    df = pd.DataFrame({
        "open":  [10, 10, 10, 10, 10],
        "high":  [10, 10, 10, 10, 10],
        "low":   [10, 10, 8, 10, 10],
        "close": [10, 10, 9, 10, 10],
    })
    strat = FakeStrategy([Signal.BUY, Signal.HOLD, Signal.HOLD, Signal.BUY, Signal.HOLD])
    r = _run_on_df(strat, df, initial_cash=1000, stop_loss_pct=0.10)
    buys = [t for t in r["trades"] if t["side"] == "buy"]
    assert len(buys) == 2, r["trades"]  # 停損出場後有再進場
    assert r["num_stop_loss"] == 1, r


# ============================================================
# 做空支援（allow_short；預設 False = 舊行為零改變）
# ============================================================

def test_short_profit_on_decline():
    """開空賺跌：SELL@bar0 → 次根 open=10 開空（100 股）；BUY@bar2 → 次根 open=5 回補 → 賺 500。"""
    df = pd.DataFrame({"open": [10, 10, 5, 5], "close": [10, 10, 5, 5]})
    strat = FakeStrategy([Signal.SELL, Signal.HOLD, Signal.BUY, Signal.HOLD])
    r = _run_on_df(strat, df, initial_cash=1000, allow_short=True)
    shorts = [t for t in r["trades"] if t["side"] == "short"]
    covers = [t for t in r["trades"] if t["side"] == "cover"]
    assert shorts and shorts[0]["price"] == 10.0, r["trades"]
    assert covers and covers[0]["profit"] == 500.0, r["trades"]
    assert r["final_equity"] == 1500.0, r
    assert r["num_round_trips"] == 1 and r["win_rate_pct"] == 100.0, r
    print("✅ 開空賺跌測試通過（+500）")


def test_allow_short_false_unchanged():
    """向後相容硬斷言：預設 allow_short=False，空手 SELL 被忽略 → 0 交易、資產不變。"""
    df = pd.DataFrame({"open": [10, 10, 5, 5], "close": [10, 10, 5, 5]})
    signals = [Signal.SELL, Signal.HOLD, Signal.BUY, Signal.HOLD]
    r = _run_on_df(FakeStrategy(list(signals)), df, initial_cash=1000)
    # 注意：bar2 的 BUY 空手會照常做多（舊行為），所以驗「無 short/cover」而非 0 交易
    assert all(t["side"] in ("buy", "sell") for t in r["trades"]), r["trades"]
    # 純多訊號下 allow_short=True 與 False 結果完全相同（開關不影響純多路徑）
    long_signals = [Signal.BUY, Signal.HOLD, Signal.SELL, Signal.HOLD]
    r_off = _run_on_df(FakeStrategy(list(long_signals)), df, initial_cash=1000)
    r_on = _run_on_df(FakeStrategy(list(long_signals)), df, initial_cash=1000, allow_short=True)
    assert r_off["trades"] == r_on["trades"], (r_off["trades"], r_on["trades"])
    assert r_off["equity_curve"] == r_on["equity_curve"], (r_off, r_on)
    print("✅ allow_short=False 向後相容測試通過")


def test_short_stop_loss_on_rise():
    """空單停損＝價格上漲：進空 10、停損 10%（觸價 11）、當根 high=12 → 以 11 回補、資產 900。"""
    df = pd.DataFrame({
        "open":  [10, 10, 10, 10],
        "high":  [10, 10, 12, 10],
        "low":   [10, 10, 10, 10],
        "close": [10, 10, 11.5, 10],
    })
    strat = FakeStrategy([Signal.SELL, Signal.HOLD, Signal.HOLD, Signal.HOLD])
    r = _run_on_df(strat, df, initial_cash=1000, allow_short=True, stop_loss_pct=0.10)
    assert r["num_stop_loss"] == 1, r
    covers = [t for t in r["trades"] if t["side"] == "cover"]
    assert covers[0]["exit_reason"] == "stop_loss", covers
    assert covers[0]["price"] == 11.0, covers
    assert r["final_equity"] == 900.0, r
    print("✅ 空單停損（價漲）測試通過")


def test_short_gap_up_fills_at_open():
    """跳空開高穿過空單停損（觸價 11、開盤 13）→ 只能回補在更差的開盤價 13（保守不美化）。"""
    df = pd.DataFrame({
        "open":  [10, 10, 13],
        "high":  [10, 10, 13.5],
        "low":   [10, 10, 12.5],
        "close": [10, 10, 13],
    })
    strat = FakeStrategy([Signal.SELL, Signal.HOLD, Signal.HOLD])
    r = _run_on_df(strat, df, initial_cash=1000, allow_short=True, stop_loss_pct=0.10)
    assert r["num_stop_loss"] == 1, r
    covers = [t for t in r["trades"] if t["side"] == "cover"]
    assert covers[0]["price"] == 13.0, covers
    assert r["final_equity"] == 700.0, r  # 100 股 × (10-13) = -300
    print("✅ 空單跳空開高成交在開盤價測試通過")


def test_short_trailing_uses_prior_trough():
    """
    空單追蹤止損用「前面 bar 為止」的最低價：進空 10 → 跌到 6（trough）→
    反彈破 6×(1+10%)=6.6 → 以 6.6 回補。跌到 6 那根自己不會被舊 trough 觸發。
    """
    df = pd.DataFrame({
        "open":  [10, 10, 6.5, 6.5, 6.5],
        "high":  [10, 10, 6.5, 7, 6.5],
        "low":   [10, 10, 6, 6.4, 6.5],
        "close": [10, 10, 6, 6.8, 6.5],
    })
    strat = FakeStrategy([Signal.SELL] + [Signal.HOLD] * 4)
    r = _run_on_df(strat, df, initial_cash=1000, allow_short=True, trailing_stop_pct=0.10)
    assert r["num_trailing_stop"] == 1, r
    covers = [t for t in r["trades"] if t["side"] == "cover"]
    assert covers[0]["exit_reason"] == "trailing_stop", covers
    assert covers[0]["price"] == 6.6, covers
    print("✅ 空單追蹤止損用 prior trough 測試通過")


def test_no_direct_flip():
    """持多遇 SELL 只平多（不直接翻倉）；平倉後下一次 SELL 才開空——兩段式。"""
    df = pd.DataFrame({"open": [10] * 6, "close": [10] * 6})
    strat = FakeStrategy([
        Signal.BUY, Signal.HOLD, Signal.SELL, Signal.SELL, Signal.HOLD, Signal.HOLD
    ])
    r = _run_on_df(strat, df, initial_cash=1000, allow_short=True)
    sides = [t["side"] for t in r["trades"]]
    assert sides == ["buy", "sell", "short"], r["trades"]  # SELL@bar2 平多、SELL@bar3 才開空
    print("✅ 不直接翻倉（兩段式）測試通過")


def test_short_slippage_direction():
    """空單滑價方向必須對自己不利：開空成交 < raw、回補成交 > raw。"""
    df = pd.DataFrame({"open": [10, 10, 5, 5], "close": [10, 10, 5, 5]})
    strat = FakeStrategy([Signal.SELL, Signal.HOLD, Signal.BUY, Signal.HOLD])
    r = _run_on_df(strat, df, initial_cash=1000, allow_short=True, slippage_bps=100)  # 1%
    shorts = [t for t in r["trades"] if t["side"] == "short"]
    covers = [t for t in r["trades"] if t["side"] == "cover"]
    assert shorts[0]["price"] == 9.9, shorts    # 開空 10 × (1−1%) = 9.9（賣得更低，不利）
    assert covers[0]["price"] == 5.05, covers   # 回補 5 × (1+1%) = 5.05（買得更高，不利）
    print("✅ 空單滑價方向（對己不利）測試通過")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
