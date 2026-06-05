"""
回測 API
========
用歷史資料模擬策略表現，不會真的下單。

兩種模式：
- POST /backtest      ：手動指定「策略 + 參數」跑一次。
- POST /auto-backtest ：全自動掃描——程式自己把 8 種策略 × 各自參數網格全跑一遍，
                        依期望值 EV 排名挑最佳，最佳組合自動存進回測歷史（一鍵最強）。
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import BacktestRun
from backend.services.backtest_engine import run_backtest
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
