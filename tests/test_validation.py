"""
防過擬合驗證框架測試（Phase 7 step-07）
=========================================
驗證：
1. walk_forward_splits / walk_forward：滾動前進切分正確、回多個 fold 的 OOS 績效。
2. purged_kfold_splits：折數正確、訓練段已清掉測試段前後 embargo（不洩漏）。
3. is_layer_worth_it：能把「in-sample 漂亮、OOS 崩」的假層判為不值得上線。

純函式（walk_forward 用合成 K 線，不連網）。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_validation.py -v
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

from backend.services.validation import (
    walk_forward_splits,
    walk_forward,
    purged_kfold_splits,
    is_layer_worth_it,
)


def _osc_df(n=300):
    """震盪向上的合成日 K 線，足以觸發部分策略交易。"""
    closes = [100 + 10 * math.sin(i / 5) + i * 0.1 for i in range(n)]
    return pd.DataFrame({
        "open": closes,
        "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes],
        "close": closes,
        "volume": [1000] * n,
        "timestamp": pd.date_range("2023-01-01", periods=n, freq="D"),
    })


def test_walk_forward_splits_rolls_forward():
    """切分：第一個測試段從 train_window 起，之後每次往前滾 step；不重疊時 step=test_window。"""
    folds = walk_forward_splits(n=300, train_window=100, test_window=50, step=50)
    assert len(folds) == 4  # 測試段起點 100,150,200,250；300 不夠再放一段
    assert folds[0] == {"train_start": 0, "train_end": 100, "test_start": 100, "test_end": 150}
    # 每段測試都接在前段之後（不重疊）
    for a, b in zip(folds, folds[1:]):
        assert b["test_start"] == a["test_end"]


def test_walk_forward_splits_too_short():
    """資料太短湊不出完整測試段 → 空 list。"""
    assert walk_forward_splits(n=50, train_window=100, test_window=50, step=50) == []


def test_walk_forward_returns_per_fold_oos():
    """walk_forward 對一個策略回出多個 fold 的 OOS 績效，每筆帶 expected_value。"""
    df = _osc_df(300)
    folds = walk_forward(df, "rsi", train_window=100, test_window=50, step=50)
    assert len(folds) >= 2
    for f in folds:
        assert "expected_value" in f and "num_round_trips" in f
        assert f["test_end"] - f["test_start"] == 50


def test_purged_kfold_no_leakage():
    """清洗式 K-Fold：k 折、測試塊涵蓋全集、訓練段已清掉測試段前後 embargo。"""
    folds = purged_kfold_splits(n=20, k=5, embargo=2)
    assert len(folds) == 5
    # 所有測試塊聯集 = 0..19（不重不漏）
    all_test = sorted(j for f in folds for j in f["test_idx"])
    assert all_test == list(range(20))
    # 取中間一折檢查清洗：訓練段不得含「測試塊 ± embargo」範圍內任何點
    mid = folds[2]
    ts, te = mid["test_idx"][0], mid["test_idx"][-1] + 1
    forbidden = set(range(max(0, ts - 2), min(20, te + 2)))
    assert forbidden.isdisjoint(set(mid["train_idx"]))
    # 訓練段與測試段不重疊
    assert set(mid["train_idx"]).isdisjoint(set(mid["test_idx"]))


def test_purged_kfold_too_few():
    """資料比折數還少 → 空 list。"""
    assert purged_kfold_splits(n=3, k=5, embargo=1) == []


def test_is_layer_worth_it_kills_fake_layer():
    """假層：in-sample 漂亮但 OOS 比 baseline 差 → 判定不值得上線。"""
    baseline = [10.0, 12.0, 9.0, 11.0]
    candidate = [-5.0, -3.0, -8.0, -4.0]  # OOS 崩
    verdict = is_layer_worth_it(baseline, candidate, min_improvement=0, min_folds=3)
    assert verdict["worth"] is False
    assert verdict["improvement"] < 0


def test_is_layer_worth_it_accepts_real_improvement():
    """真有加分：候選 OOS 平均贏過 baseline 且 fold 數達標 → 值得上線。"""
    baseline = [10.0, 12.0, 9.0, 11.0]
    candidate = [20.0, 22.0, 19.0, 21.0]
    verdict = is_layer_worth_it(baseline, candidate, min_improvement=0, min_folds=3)
    assert verdict["worth"] is True
    assert verdict["improvement"] > 0


def test_is_layer_worth_it_needs_enough_folds():
    """fold 數不足 → 不採信（避免運氣），即使候選看起來較好。"""
    verdict = is_layer_worth_it([10.0], [50.0], min_improvement=0, min_folds=3)
    assert verdict["worth"] is False
    assert "fold 數不足" in verdict["reason"]


if __name__ == "__main__":
    test_walk_forward_splits_rolls_forward()
    test_walk_forward_splits_too_short()
    test_walk_forward_returns_per_fold_oos()
    test_purged_kfold_no_leakage()
    test_purged_kfold_too_few()
    test_is_layer_worth_it_kills_fake_layer()
    test_is_layer_worth_it_accepts_real_improvement()
    test_is_layer_worth_it_needs_enough_folds()
    print("\n🎉 全部防過擬合驗證框架測試通過！")
