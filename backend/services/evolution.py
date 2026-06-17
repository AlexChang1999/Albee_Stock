"""
自動驗證管線（OOS + 防過擬合）── Phase 8 step-04
==================================================
★ 整個 Phase 8 能不能信的關鍵守門。任何候選策略（生成的 or 組合的）要進策展庫前，
**一律跑同一條嚴格驗證管線**，只有在**樣本外真的加分**的才通過。
把「自我進化」與「自我過擬合」分開的唯一防線。

直接重用 Phase 6 / 7 的成果，**不自寫驗證 / 切分 / 評分邏輯**：
- 同源同回看抓資料：market_data.get_bars（呼應「回測 = 實盤」鐵則 3）。
- 含成本 + 隔日成交回測 + 單次 OOS 切分：backtest_engine._run_on_df + optimizer.split_train_test。
- 滾動前進樣本外判定：validation.walk_forward + validation.is_layer_worth_it（Phase 7 step-07）。

「在 OOS 真加分」的定義：拿候選策略每個 fold 的樣本外 EV，對比「不交易（EV=0）」的基準。
walk-forward 的 OOS EV 平均需達門檻（VALIDATION_MIN_IMPROVEMENT）且 fold 數達標
（VALIDATION_MIN_FOLDS），才判 validated；否則 rejected。判定一律看 OOS / walk-forward，
**不看 in-sample**（違反原目標鐵則 2 = 自欺）。
"""

from backend.config import settings
from backend.services import market_data
from backend.services import validation
from backend.services.backtest_engine import _run_on_df
from backend.services.optimizer import split_train_test
from backend.strategies import get_strategy


def is_noop(folds: list[dict]) -> bool:
    """
    候選在所有 walk-forward fold 都零交易（num_round_trips 全 0）＝沒下場的 no-op。

    no-op 的每個 fold OOS EV 都是 0，會跟「不交易」基準（baseline EV=0）剛好打平，
    在 VALIDATION_MIN_IMPROVEMENT=0 下被 is_layer_worth_it 判 worth=True 而假性過閘。
    這不是「贏過不出手」，是「根本沒出手所以不會輸」——必須跟真加分分開。

    純函式（不碰 DB / 不回測），讓 validate_candidate 與重判腳本共用同一判準。
    空 folds 視為 no-op（沒有任何交易證據）。
    """
    return sum(int(f.get("num_round_trips", 0)) for f in folds) == 0


def validate_candidate(
    knowledge_row,
    symbol: str,
    days: int = 365,
    initial_cash: float = 10000.0,
    source: str | None = None,
) -> dict:
    """
    對一筆候選 StrategyKnowledge 跑驗證管線，寫回 oos_metrics 與 status（validated / rejected）。

    :param knowledge_row: StrategyKnowledge ORM 物件（會被就地更新；commit 交給 router）
    :param symbol: 在哪檔股票上驗證（知識列本身不綁標的，驗證時指定）
    :param days: 回看天數（同源同回看）
    :return: 驗證摘要（同步寫進 knowledge_row.oos_metrics）
    :raises ValueError: 抓不到資料
    """
    strategy_key = knowledge_row.strategy_key
    params = knowledge_row.params or {}
    src = source or settings.DATA_SOURCE

    df = market_data.get_bars(symbol.upper(), days=days, source=src)
    if df.empty:
        raise ValueError(f"抓不到 {symbol} 的歷史資料")

    commission_bps = settings.BACKTEST_COMMISSION_BPS
    slippage_bps = settings.BACKTEST_SLIPPAGE_BPS

    # 1) 單次 OOS 切分：在「測試段」上跑一次含成本回測（供查驗，不當判定依據）
    _, test_df = split_train_test(df, settings.OOS_TEST_RATIO)
    test_df = test_df.reset_index(drop=True)
    single_split = _run_on_df(
        get_strategy(strategy_key, params), test_df, initial_cash,
        commission_bps=commission_bps, slippage_bps=slippage_bps,
    )

    # 2) 滾動前進（walk-forward）：每個 fold 的樣本外 EV
    folds = validation.walk_forward(df, strategy_key, params, initial_cash=initial_cash)
    if not folds:
        # 資料太短湊不出任何完整 fold：明確告知（而非靜默判 rejected，
        # 否則使用者分不清「資料太短」與「策略真的爛」）。
        need = settings.VALIDATION_TRAIN_WINDOW + settings.VALIDATION_TEST_WINDOW
        raise ValueError(
            f"資料太短，湊不出 walk-forward fold（至少需 {need} 根，"
            f"{symbol.upper()} 實際只有 {len(df)} 根）。請拉長 days 或換資料較長的標的。"
        )
    # single_split 摘要：no-op 與正常路徑都要寫，先抽出來共用
    single_split_summary = {
        "expected_value": single_split["expected_value"],
        "win_rate_pct": single_split["win_rate_pct"],
        "total_return_pct": single_split["total_return_pct"],
        "num_round_trips": single_split["num_round_trips"],
    }

    # 2.5) 零交易守門：所有 fold 都沒下場 → no-op，直接 rejected（不進 verdict）。
    # 與 verdict-reject（含 "verdict" 鍵）、auto_validate 操作性 reject（含 "auto_validate" 鍵）
    # 三者可由 oos_metrics 的鍵稽核區分。
    if is_noop(folds):
        oos_metrics = {
            "expected_value": 0.0,
            "noop": {
                "reason": "所有 fold 零交易（num_round_trips 全 0）＝沒下場的 no-op，非真加分",
                "total_round_trips": 0,
            },
            "walk_forward": folds,
            "single_split": single_split_summary,
            "symbol": symbol.upper(),
            "days": days,
        }
        knowledge_row.oos_metrics = oos_metrics
        knowledge_row.status = "rejected"
        return {"id": knowledge_row.id, "status": "rejected", "oos_metrics": oos_metrics}

    candidate_oos = [f["expected_value"] for f in folds]
    # 基準 = 不交易（每 fold EV = 0）；候選需在 OOS 上贏過「不出手」
    baseline_oos = [0.0] * len(folds)

    # 3) 是否「在 OOS 真加分」（內建提升門檻 + fold 數檢查）
    verdict = validation.is_layer_worth_it(baseline_oos, candidate_oos)
    status = "validated" if verdict["worth"] else "rejected"

    oos_metrics = {
        # 排序 / 顯示用的頭條：walk-forward 樣本外 EV 平均
        "expected_value": verdict["candidate_mean"],
        "verdict": verdict,
        "walk_forward": folds,
        "single_split": single_split_summary,
        "symbol": symbol.upper(),
        "days": days,
    }

    # 寫回知識列（commit 交給呼叫端 / router）
    knowledge_row.oos_metrics = oos_metrics
    knowledge_row.status = status

    return {"id": knowledge_row.id, "status": status, "oos_metrics": oos_metrics}
