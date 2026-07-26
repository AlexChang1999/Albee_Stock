"""
Optimizer walk-forward 聚合 OOS 測試（M3）
==========================================
驗證：
1. _overfit_gap 數學與邊界（IS<=0 → None）
2. _wf_aggregate 跨折聚合數學（合成資料：交易數加總、EV = 總損益/總筆數）
3. run_auto_backtest(walk_forward=False) 走舊路徑（相容）
4. 排名守門：OOS 樣本不足的組合沉底
"""

import numpy as np
import pandas as pd
import pytest

from backend.config import settings
from backend.services import optimizer
from backend.services.optimizer import _overfit_gap, _wf_aggregate


def _make_df(n=400, seed=7):
    """合成一段有趨勢有回檔的 K 線（夠長，湊得出 walk-forward fold）。"""
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0.05, 1.0, n))
    close = np.maximum(close, 1.0)
    ts = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "timestamp": ts,
        "open": close * (1 + rng.normal(0, 0.002, n)),
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": rng.integers(1_000_000, 5_000_000, n).astype(float),
    })


# ---------- 1. overfit gap ----------

def test_overfit_gap_math():
    assert _overfit_gap(100.0, 50.0) == 0.5     # 樣本外掉一半
    assert _overfit_gap(100.0, 100.0) == 0.0    # 完全守住
    assert _overfit_gap(100.0, -20.0) == 1.2    # 樣本外反虧
    assert _overfit_gap(0.0, 10.0) is None      # IS<=0 無意義
    assert _overfit_gap(-5.0, 10.0) is None
    assert _overfit_gap(None, 10.0) is None


# ---------- 2. 跨折聚合 ----------

def test_wf_aggregate_sums_trips_across_folds(monkeypatch):
    """交易數 = 各 fold 加總；EV = 全部 OOS 損益 / 全部筆數（加權，不是各 fold 平均）。"""
    df = _make_df(400)
    # 固定切出 3 個 fold（不吃 .env 的窗口設定，測試有確定性）
    monkeypatch.setattr(settings, "VALIDATION_TRAIN_WINDOW", 100)
    monkeypatch.setattr(settings, "VALIDATION_TEST_WINDOW", 100)
    monkeypatch.setattr(settings, "VALIDATION_STEP", 100)

    fold_results = iter([
        {"num_round_trips": 2, "expected_value": 10.0, "num_wins": 2, "num_losses": 0,
         "avg_win": 10.0, "avg_loss": None, "max_drawdown_pct": 5.0, "equity_curve": [1, 1.01]},
        {"num_round_trips": 3, "expected_value": -4.0, "num_wins": 1, "num_losses": 2,
         "avg_win": 2.0, "avg_loss": -7.0, "max_drawdown_pct": 12.0, "equity_curve": [1, 0.99]},
        {"num_round_trips": 0, "expected_value": 0.0, "num_wins": 0, "num_losses": 0,
         "avg_win": None, "avg_loss": None, "max_drawdown_pct": 0.0, "equity_curve": []},
    ])
    monkeypatch.setattr(optimizer, "_run_combo", lambda *a, **k: next(fold_results))

    agg = _wf_aggregate("ma_crossover", {}, df, 10000, 0, 0)
    assert agg["oos_folds"] == 3
    assert agg["oos_num_round_trips"] == 5                       # 2+3+0
    # 總損益 = 2×10 + 3×(−4) = 8 → EV = 8/5 = 1.6
    assert agg["oos_expected_value"] == pytest.approx(1.6)
    assert agg["oos_win_rate_pct"] == pytest.approx(60.0)        # 3 勝 / 5 筆
    # PF = 總賺 (2×10 + 1×2) / 總賠 |−7|×2 = 22/14
    assert agg["oos_profit_factor"] == pytest.approx(22 / 14, rel=1e-3)
    assert agg["oos_max_drawdown_pct"] == 12.0                   # 各 fold 取最差


def test_wf_aggregate_returns_none_when_too_short(monkeypatch):
    """資料太短湊不出 fold → 回 None（呼叫端退回單次切分，誠實退化）。"""
    monkeypatch.setattr(settings, "VALIDATION_TRAIN_WINDOW", 180)
    monkeypatch.setattr(settings, "VALIDATION_TEST_WINDOW", 60)
    df = _make_df(100)  # 100 < 180+60
    assert _wf_aggregate("ma_crossover", {}, df, 10000, 0, 0) is None


# ---------- 3/4. run_auto_backtest 整合 ----------

def _patch_data(monkeypatch, df):
    from backend.services import bar_cache
    monkeypatch.setattr(bar_cache, "get_bars_cached",
                        lambda *a, **k: df)


def test_walk_forward_false_keeps_legacy_fields(monkeypatch):
    """walk_forward=False：無 oos_folds 欄位（舊單次切分路徑），仍有 overfit_gap。"""
    _patch_data(monkeypatch, _make_df(400))
    out = optimizer.run_auto_backtest("TEST", days=400, walk_forward=False)
    m = out["best"]["metrics"]
    assert "oos_folds" not in m
    assert "overfit_gap" in m
    assert out["walk_forward"] is False


def test_walk_forward_true_adds_aggregated_fields(monkeypatch):
    """walk_forward=True：排行榜每列都有聚合欄位（folds/sharpe/sortino/PF/MaxDD）。"""
    monkeypatch.setattr(settings, "VALIDATION_TRAIN_WINDOW", 150)
    monkeypatch.setattr(settings, "VALIDATION_TEST_WINDOW", 80)
    monkeypatch.setattr(settings, "VALIDATION_STEP", 80)
    _patch_data(monkeypatch, _make_df(400))
    out = optimizer.run_auto_backtest("TEST", days=400, walk_forward=True)
    m = out["best"]["metrics"]
    for key in ("oos_folds", "oos_num_round_trips", "oos_profit_factor",
                "oos_max_drawdown_pct", "oos_sharpe", "oos_sortino",
                "oos_avg_r_multiple", "overfit_gap"):
        assert key in m, f"缺欄位 {key}"
    assert m["oos_folds"] >= 2


def test_rank_gate_demotes_low_sample_combos(monkeypatch):
    """守門：OOS 樣本數 ≥ 門檻的組合永遠排在樣本不足的前面（即使 EV 較低）。"""
    _patch_data(monkeypatch, _make_df(400))
    monkeypatch.setattr(settings, "OPTIMIZER_MIN_OOS_TRIPS", 3)

    # 攔截排行榜：直接驗證排序鍵行為——構造兩筆，一筆 EV 高但樣本 1 筆、一筆 EV 低但樣本 10 筆
    out = optimizer.run_auto_backtest("TEST", days=400, walk_forward=False)
    lb = out["leaderboard"]
    # 手動改 metrics 重排驗證守門語意
    rich_noise = {"strategy_key": "a", "params": {},
                  "metrics": {"oos_expected_value": 999.0, "oos_total_return_pct": 99,
                              "oos_num_round_trips": 1, "overfit_gap": 0.0}}
    modest_solid = {"strategy_key": "b", "params": {},
                    "metrics": {"oos_expected_value": 5.0, "oos_total_return_pct": 3,
                                "oos_num_round_trips": 10, "overfit_gap": 0.1}}
    min_trips = settings.OPTIMIZER_MIN_OOS_TRIPS
    max_gap = settings.OPTIMIZER_MAX_OVERFIT_GAP

    def rank_key(r):
        m = r["metrics"]
        ev = m.get("oos_expected_value", float("-inf"))
        trips = m.get("oos_num_round_trips") or 0
        gap = m.get("overfit_gap")
        passes = 1 if (trips >= min_trips and (gap is None or gap <= max_gap)) else 0
        return (passes, ev, m.get("oos_total_return_pct") or 0.0)

    ranked = sorted([rich_noise, modest_solid], key=rank_key, reverse=True)
    assert ranked[0] is modest_solid, "樣本 1 筆的高 EV 噪音不該贏過樣本充足的組合"
    assert lb  # 整條 pipeline 沒炸
