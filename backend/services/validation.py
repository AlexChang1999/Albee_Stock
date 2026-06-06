"""
防過擬合驗證框架（Anti-Overfitting Validation）── Phase 7 step-07
==================================================================
★ 整個 Phase 7 能不能信的關鍵。沒有它，前面幾步都是「用更複雜的方法更精緻地騙自己」。

提供嚴謹的時序驗證工具，讓「狀態分類 / 自適應選策略 / meta-labeling」這些加上去的層，
**都必須在真正的樣本外證明自己有加分**，否則一律砍掉。

工具：
- walk_forward：滾動前進驗證。模擬「真實上線」——在過去保留訓練/暖機，緊接的未來測試，往前滾。
  回出每個 fold 的 OOS 績效（數字會比 in-sample 保守）。
- purged_kfold_splits：金融時序專用的清洗式交叉驗證切分（給學習式模型用）。
  移除訓練/測試交界會洩漏未來的重疊樣本（embargo）。
- is_layer_worth_it：判定「加這層有沒有在 OOS 上贏過不加它」（內建最小提升門檻 + fold 數檢查）。

心態鐵則：**這套框架是用來「殺掉沒用的層」，不是用來「美化績效」**。
希望它把你心愛的點子判死——那才是它在工作。

重用：Phase 6 step-04 的 split_train_test 是「單次切分」，walk_forward 是它的滾動推廣；
每個 fold 在子 df 上跑 _run_on_df（含成本，與正式回測同一條路徑）。
"""

from backend.config import settings
from backend.services.backtest_engine import _run_on_df
from backend.strategies import get_strategy


def walk_forward_splits(
    n: int,
    train_window: int | None = None,
    test_window: int | None = None,
    step: int | None = None,
) -> list[dict]:
    """
    產生滾動前進的 (訓練段, 測試段) 索引切分（純函式，不碰資料，好測）。

    第一個測試段從第 train_window 根開始（前面留給訓練/暖機），之後每次往前滾 step 根。
    回傳每個 fold 的 {train_start, train_end, test_start, test_end}（半開區間，可直接 iloc 切）。

    :param n: 資料總根數
    :return: fold 切分清單（n 太短湊不出任何完整測試段時回空 list）
    """
    train_window = train_window if train_window is not None else settings.VALIDATION_TRAIN_WINDOW
    test_window = test_window if test_window is not None else settings.VALIDATION_TEST_WINDOW
    step = step if step is not None else settings.VALIDATION_STEP

    folds = []
    test_start = train_window
    while test_start + test_window <= n:
        folds.append({
            "train_start": max(0, test_start - train_window),
            "train_end": test_start,
            "test_start": test_start,
            "test_end": test_start + test_window,
        })
        test_start += step
    return folds


def walk_forward(
    df,
    strategy_key: str,
    params: dict | None = None,
    train_window: int | None = None,
    test_window: int | None = None,
    step: int | None = None,
    initial_cash: float = 10000.0,
) -> list[dict]:
    """
    對某策略做滾動前進驗證：每個 fold 只在「測試段」上跑含成本回測，回該 fold 的 OOS 績效。

    與 optimizer 的 OOS 語意一致：在測試段子 df 上跑 _run_on_df（策略在測試段內自行暖機），
    挑層/比層一律看這些 OOS 數字，不看 in-sample。

    :return: 每個 fold 一筆 {fold, test_start, test_end, expected_value, win_rate_pct,
             total_return_pct, num_round_trips}。湊不出 fold 時回空 list。
    """
    params = params or {}
    commission_bps = settings.BACKTEST_COMMISSION_BPS
    slippage_bps = settings.BACKTEST_SLIPPAGE_BPS

    folds = walk_forward_splits(len(df), train_window, test_window, step)
    results = []
    for i, fold in enumerate(folds):
        test_df = df.iloc[fold["test_start"]: fold["test_end"]].reset_index(drop=True)
        m = _run_on_df(
            get_strategy(strategy_key, params), test_df, initial_cash,
            commission_bps=commission_bps, slippage_bps=slippage_bps,
        )
        results.append({
            "fold": i,
            "test_start": fold["test_start"],
            "test_end": fold["test_end"],
            "expected_value": m["expected_value"],
            "win_rate_pct": m["win_rate_pct"],
            "total_return_pct": m["total_return_pct"],
            "num_round_trips": m["num_round_trips"],
        })
    return results


def purged_kfold_splits(
    n: int,
    k: int | None = None,
    embargo: int | None = None,
) -> list[dict]:
    """
    清洗式 K-Fold 切分（López de Prado），給「學習式模型」用，避免時序交界洩漏未來。

    把 0..n 連續切成 k 個測試塊；每塊當測試段時，訓練段 = 其餘樣本，但**再清掉測試段
    前後各 embargo 根**（這些緊鄰樣本與測試段高度相關，留著會洩漏未來、灌水分數）。

    :return: 每個 fold 一筆 {test_idx: [...], train_idx: [...]}（索引清單，半開塊已展開成點）。
             n < k 時回空 list。
    """
    k = k if k is not None else settings.VALIDATION_KFOLD
    embargo = embargo if embargo is not None else settings.VALIDATION_EMBARGO
    if n < k or k <= 1:
        return []

    # 連續切 k 塊（前 n%k 塊多 1 根，盡量平均）
    base = n // k
    rem = n % k
    bounds = []
    start = 0
    for i in range(k):
        size = base + (1 if i < rem else 0)
        bounds.append((start, start + size))
        start += size

    folds = []
    for (ts, te) in bounds:
        test_idx = list(range(ts, te))
        # 清洗區：測試塊前後各 embargo 根都不能進訓練段
        purge_lo = max(0, ts - embargo)
        purge_hi = min(n, te + embargo)
        train_idx = [j for j in range(n) if j < purge_lo or j >= purge_hi]
        folds.append({"test_idx": test_idx, "train_idx": train_idx})
    return folds


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def is_layer_worth_it(
    baseline_oos: list[float],
    candidate_oos: list[float],
    min_improvement: float | None = None,
    min_folds: int | None = None,
) -> dict:
    """
    判定「加這層」有沒有在 OOS 上贏過「不加這層」。

    吃兩組「每個 fold 的 OOS 指標」（例如各 fold 的 expected_value）：baseline = 不加層，
    candidate = 加層。回判定結果與理由，**worth=True 才准上線**。

    判定條件（全部要過）：
      1. 兩組 fold 數一致，且 ≥ min_folds（樣本太少不採信，避免運氣）。
      2. candidate 的 OOS 平均 − baseline 的 OOS 平均 ≥ min_improvement（提升門檻）。

    :return: {"worth": bool, "improvement": float, "baseline_mean": float,
             "candidate_mean": float, "folds": int, "reason": str}
    """
    min_improvement = min_improvement if min_improvement is not None else settings.VALIDATION_MIN_IMPROVEMENT
    min_folds = min_folds if min_folds is not None else settings.VALIDATION_MIN_FOLDS

    n_b, n_c = len(baseline_oos), len(candidate_oos)
    base_mean = _mean(baseline_oos)
    cand_mean = _mean(candidate_oos)
    improvement = cand_mean - base_mean

    if n_b != n_c:
        return _verdict(False, improvement, base_mean, cand_mean, min(n_b, n_c),
                        f"baseline/candidate fold 數不一致（{n_b} vs {n_c}），無法公平比較")
    if n_c < min_folds:
        return _verdict(False, improvement, base_mean, cand_mean, n_c,
                        f"fold 數不足（{n_c} < {min_folds}），樣本太少不採信")
    if improvement < min_improvement:
        return _verdict(False, improvement, base_mean, cand_mean, n_c,
                        f"OOS 提升 {improvement:.2f} < 門檻 {min_improvement}，這層不值得上線（該砍）")
    return _verdict(True, improvement, base_mean, cand_mean, n_c,
                    f"OOS 提升 {improvement:.2f} ≥ 門檻 {min_improvement}，這層在樣本外加分")


def _verdict(worth, improvement, base_mean, cand_mean, folds, reason) -> dict:
    return {
        "worth": worth,
        "improvement": round(improvement, 4),
        "baseline_mean": round(base_mean, 4),
        "candidate_mean": round(cand_mean, 4),
        "folds": folds,
        "reason": reason,
    }
