"""
回測 API
========
用歷史資料模擬策略表現，不會真的下單。

三種模式：
- POST /backtest               ：手動指定「策略 + 參數」跑一次。
- POST /auto-backtest          ：全自動掃描——程式自己把 8 種策略 × 各自參數網格全跑一遍，
                                 依期望值 EV 排名挑最佳，最佳組合自動存進回測歷史（一鍵最強）。
- POST /backtest/stress/{run_id}：對已存的回測跑蒙地卡羅壓力測試（bootstrap 重抽日報酬），
                                 回傳「換個順序重來 N 次」的風險分布；按需計算、不持久化。
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import BacktestRun
from backend.services.analytics import returns_from_equity
from backend.services.backtest_engine import run_backtest
from backend.services.monte_carlo import stress_summary
from backend.services.optimizer import run_auto_backtest

router = APIRouter(tags=["Backtest"])


class BacktestRequest(BaseModel):
    """執行回測時要傳的資料。"""
    strategy: str = "ma_crossover"
    symbol: str
    params: dict = {}
    days: int = 365  # 回測往前抓幾天
    initial_cash: float = 10000.0  # 初始資金
    source: str = settings.DATA_SOURCE  # 資料源：預設讀全系統設定 DATA_SOURCE，可覆寫


class AutoBacktestRequest(BaseModel):
    """全自動掃描要傳的資料（策略/參數都由程式決定，不用填）。"""
    symbol: str
    days: int = 365
    initial_cash: float = 10000.0
    source: str = settings.DATA_SOURCE  # 資料源：預設讀全系統設定 DATA_SOURCE，可覆寫
    timeframe: str = "1Day"             # K 線時間框架（M2；"1Min"~"1Day"）
    walk_forward: bool = True           # M3：walk-forward 聚合 OOS（False = 舊單次切分）


@router.post("/backtest")
def backtest(payload: BacktestRequest):
    """
    執行回測：用歷史資料模擬策略表現，回傳績效。
    這不會真的下單，純粹是「如果過去這樣做，結果會如何」的試算。
    """
    try:
        return run_backtest(
            strategy_name=payload.strategy,
            symbol=payload.symbol.upper(),
            params=payload.params,
            days=payload.days,
            initial_cash=payload.initial_cash,
            source=payload.source,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"回測失敗：{e}")


class StressRequest(BaseModel):
    """壓力測試參數（全部有預設值，可整包不填）。"""
    n_paths: int = 1000              # 模擬路徑數
    seed: int | None = None          # 隨機種子（給定則可重現）
    drawdown_threshold_pct: float = 20.0  # 「回撤超過 X%」的機率門檻
    ruin_threshold_pct: float = 50.0      # 「破產」定義：回撤超過此 %


@router.post("/backtest/stress/{run_id}")
def backtest_stress(run_id: int, payload: StressRequest = StressRequest(),
                    db: Session = Depends(get_db)):
    """
    對一筆已存的回測歷史跑蒙地卡羅壓力測試。

    流程：載入該筆的 equity_curve → 轉日報酬 → bootstrap 重抽出 N 條模擬路徑 →
    回傳最終權益百分位、回撤分布、破產機率等統計。按需計算、不寫回 DB
    （想換門檻重跑就再打一次，metrics JSON 保持精簡）。
    """
    run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail=f"找不到回測紀錄 id={run_id}")

    equity_curve = (run.metrics or {}).get("equity_curve")
    if not equity_curve:
        raise HTTPException(status_code=400, detail="這筆回測沒有 equity_curve，無法壓力測試")

    rets = returns_from_equity(equity_curve)
    initial_equity = float((run.metrics or {}).get("initial_cash") or equity_curve[0])
    try:
        summary = stress_summary(
            rets,
            initial_equity=initial_equity,
            n_paths=payload.n_paths,
            seed=payload.seed,
            drawdown_threshold_pct=payload.drawdown_threshold_pct,
            ruin_threshold_pct=payload.ruin_threshold_pct,
        )
    except ValueError as e:  # 日報酬筆數不足等輸入問題
        raise HTTPException(status_code=400, detail=f"壓力測試失敗：{e}")

    return {"run_id": run_id, "symbol": run.symbol, "strategy_key": run.strategy_key,
            **summary}


def _entry_summary(entry: dict) -> dict:
    """
    把排行榜中一筆結果壓成「摘要版」（給前端列表用）。
    刻意不帶 metrics 裡的 trades / equity_curve（資料量大，列表用不到）。
    """
    m = entry["metrics"]
    return {
        "strategy_key": entry["strategy_key"],
        "params": entry["params"],
        "expected_value": m.get("expected_value"),
        "expectancy_pct": m.get("expectancy_pct"),
        "profit_factor": m.get("profit_factor"),
        "win_rate_pct": m.get("win_rate_pct"),
        "total_return_pct": m.get("total_return_pct"),
        "buy_and_hold_pct": m.get("buy_and_hold_pct"),
        "max_drawdown_pct": m.get("max_drawdown_pct"),
        "num_round_trips": m.get("num_round_trips"),
        "total_cost": m.get("total_cost"),
        # ★樣本外指標（挑冠軍依據）＋樣本內對照（看過擬合落差）
        "oos_expected_value": m.get("oos_expected_value"),
        "oos_win_rate_pct": m.get("oos_win_rate_pct"),
        "oos_total_return_pct": m.get("oos_total_return_pct"),
        "is_expected_value": m.get("is_expected_value"),
        # ★M3 過擬合診斷欄位（walk-forward 聚合 OOS）
        "overfit_gap": m.get("overfit_gap"),
        "oos_num_round_trips": m.get("oos_num_round_trips"),
        "oos_folds": m.get("oos_folds"),
        "oos_sharpe": m.get("oos_sharpe"),
        "oos_sortino": m.get("oos_sortino"),
        "oos_profit_factor": m.get("oos_profit_factor"),
        "oos_max_drawdown_pct": m.get("oos_max_drawdown_pct"),
        "oos_avg_r_multiple": m.get("oos_avg_r_multiple"),
        "timeframe": m.get("timeframe"),
    }


@router.post("/auto-backtest")
def auto_backtest(payload: AutoBacktestRequest, db: Session = Depends(get_db)):
    """
    全自動掃描（最強）：
    程式自己跑遍「所有策略 × 參數組合」，依 EV 排名挑最佳。

    存檔策略（避免一次塞數十筆灌爆歷史）：
    - 每個策略只把它自己「最好的那組」存成一筆 BacktestRun（最多 8 筆）。
    - 全場冠軍那筆額外標記 is_good=True（直接進「好策略」榜）。
    回傳完整排行榜（摘要版）給前端顯示，最佳組合附完整 metrics 可看明細。
    """
    try:
        scan = run_auto_backtest(
            symbol=payload.symbol.upper(),
            days=payload.days,
            initial_cash=payload.initial_cash,
            source=payload.source,
            timeframe=payload.timeframe,
            walk_forward=payload.walk_forward,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"全自動回測失敗：{e}")

    leaderboard = scan["leaderboard"]
    if not leaderboard:
        raise HTTPException(status_code=400, detail="沒有產生任何回測結果")

    # 取每個策略「最好的那組」（leaderboard 已依 EV 排序，第一次遇到即最佳）
    best_per_strategy = {}
    for entry in leaderboard:
        key = entry["strategy_key"]
        if key not in best_per_strategy:
            best_per_strategy[key] = entry

    champion = scan["best"]  # 全場冠軍
    champion_run_id = None

    # 把每個策略的最佳組合各存一筆紀錄（冠軍那筆標記為好策略）
    stored_run_ids = []
    for entry in best_per_strategy.values():
        is_champion = entry is champion
        run = BacktestRun(
            preset_id=None,  # 自動掃描不綁特定方案
            strategy_key=entry["strategy_key"],
            params=entry["params"],
            symbol=scan["symbol"],
            period_days=scan["days"],
            metrics=entry["metrics"],
            is_good=is_champion,
        )
        db.add(run)
        db.flush()  # 先拿到 id
        stored_run_ids.append(run.id)
        if is_champion:
            champion_run_id = run.id
    db.commit()

    return {
        "symbol": scan["symbol"],
        "days": scan["days"],
        "initial_cash": scan["initial_cash"],
        "data_points": scan["data_points"],
        "combos_tested": scan["combos_tested"],
        "strategies_tested": scan["strategies_tested"],
        "stored_run_ids": stored_run_ids,
        "champion_run_id": champion_run_id,
        # 冠軍：附完整 metrics（前端可直接顯示交易明細）
        "best": {
            "strategy_key": champion["strategy_key"],
            "params": champion["params"],
            "metrics": champion["metrics"],
        },
        # 完整排行榜（摘要版，已依 EV 排好）
        "leaderboard": [_entry_summary(e) for e in leaderboard],
    }
