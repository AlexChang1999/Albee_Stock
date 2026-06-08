"""
策略方案 + 回測紀錄 API ── Phase 5
================================================
這支 router 管兩種東西：

1. 策略方案（StrategyPreset）：可命名的策略草稿，能 CRUD、收藏。
   - GET/POST/PUT/DELETE /presets
2. 一鍵回測 + 回測紀錄（BacktestRun）：
   - POST /presets/{id}/backtest ：用 Python 跑回測 → 算含 EV 指標 → 存一筆紀錄 → 回結果
   - GET /backtest-runs          ：列出歷史，依「期望值 EV」排序（可篩好策略）
   - GET /backtest-runs/{id}     ：看單筆完整紀錄

設計重點：
- 回測是 Python 做的（這裡呼叫 run_backtest），不是 Claude。
- 挑策略看 EV（expected_value），所以歷史列表預設依 EV 由高到低排。
"""

import os
import tempfile

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import StrategyPreset, BacktestRun, Bot
from backend.services.backtest_engine import run_backtest
from backend.services.analytics import tearsheet_html

router = APIRouter(tags=["Presets"])


# ---------- 請求資料格式（Pydantic） ----------
class PresetIn(BaseModel):
    """建立 / 編輯策略方案要傳的資料。"""
    name: str
    strategy_key: str = "ma_crossover"
    symbol: str
    params: dict = {}
    is_favorite: bool = False
    notes: str | None = None


class BacktestParams(BaseModel):
    """對某方案跑回測時的選項（都有預設值，可不傳）。"""
    days: int = 365             # 回測往前抓幾天
    initial_cash: float = 10000.0


class ToBotIn(BaseModel):
    """把方案一鍵轉成 Bot 時的選項（都可不傳）。"""
    name: str | None = None        # 不帶就沿用方案名
    trade_amount: float = 1000.0   # 每次下單金額（比照 BotCreate 預設）


# ---------- 內部小工具 ----------
def _get_preset_or_404(db: Session, preset_id: int) -> StrategyPreset:
    """查出方案，找不到回 404。"""
    p = db.query(StrategyPreset).filter(StrategyPreset.id == preset_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="找不到這個策略方案")
    return p


def _preset_dict(p: StrategyPreset) -> dict:
    """把方案 ORM 物件轉成回傳用的 dict。"""
    return {
        "id": p.id,
        "name": p.name,
        "strategy_key": p.strategy_key,
        "params": p.params,
        "symbol": p.symbol,
        "is_favorite": p.is_favorite,
        "notes": p.notes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _ev_of(run: BacktestRun) -> float:
    """取某筆回測紀錄的期望值 EV（排序用）；缺值當 -inf 排最後。"""
    metrics = run.metrics or {}
    ev = metrics.get("expected_value")
    return ev if isinstance(ev, (int, float)) else float("-inf")


def _run_summary(run: BacktestRun) -> dict:
    """
    回測紀錄的「摘要版」（給列表用）。
    刻意不帶 metrics 裡的 trades / equity_curve（太大），只挑關鍵指標。
    """
    m = run.metrics or {}
    return {
        "id": run.id,
        "preset_id": run.preset_id,
        "strategy_key": run.strategy_key,
        "params": run.params,
        "symbol": run.symbol,
        "period_days": run.period_days,
        "is_good": run.is_good,
        "has_postmortem": bool(run.claude_postmortem),
        "created_at": run.created_at.isoformat() if run.created_at else None,
        # 關鍵指標摘要（EV 當頭條）
        "expected_value": m.get("expected_value"),
        "expectancy_pct": m.get("expectancy_pct"),
        "profit_factor": m.get("profit_factor"),
        "win_rate_pct": m.get("win_rate_pct"),
        "total_return_pct": m.get("total_return_pct"),
        "max_drawdown_pct": m.get("max_drawdown_pct"),
        "num_round_trips": m.get("num_round_trips"),
    }


# ========== 策略方案 CRUD ==========
@router.get("/presets")
def list_presets(db: Session = Depends(get_db)):
    """列出所有策略方案（收藏的排前面，其餘依建立時間新到舊）。"""
    presets = (
        db.query(StrategyPreset)
        .order_by(StrategyPreset.is_favorite.desc(), StrategyPreset.created_at.desc())
        .all()
    )
    return [_preset_dict(p) for p in presets]


@router.post("/presets")
def create_preset(payload: PresetIn, db: Session = Depends(get_db)):
    """建立一個新的策略方案。"""
    p = StrategyPreset(
        name=payload.name,
        strategy_key=payload.strategy_key,
        symbol=payload.symbol.upper(),
        params=payload.params,
        is_favorite=payload.is_favorite,
        notes=payload.notes,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _preset_dict(p)


@router.put("/presets/{preset_id}")
def update_preset(preset_id: int, payload: PresetIn, db: Session = Depends(get_db)):
    """編輯方案：改名、調參數、改標的、收藏與否、備註。"""
    p = _get_preset_or_404(db, preset_id)
    p.name = payload.name
    p.strategy_key = payload.strategy_key
    p.symbol = payload.symbol.upper()
    p.params = payload.params
    p.is_favorite = payload.is_favorite
    p.notes = payload.notes
    db.commit()
    db.refresh(p)
    return _preset_dict(p)


@router.delete("/presets/{preset_id}")
def delete_preset(preset_id: int, db: Session = Depends(get_db)):
    """刪除一個策略方案（不連動刪除它的回測歷史，歷史仍保留供 Claude 參考）。"""
    p = _get_preset_or_404(db, preset_id)
    name = p.name
    db.delete(p)
    db.commit()
    return {"message": f"已刪除策略方案：{name}"}


@router.post("/presets/{preset_id}/to-bot")
def preset_to_bot(
    preset_id: int,
    options: ToBotIn = ToBotIn(),
    db: Session = Depends(get_db),
):
    """
    好策略「一鍵轉 Bot」：把方案的策略/標的/參數複製成一個新 Bot 實跑（Phase 5 選配）。

    刻意做成「複製一份」而非綁定：之後改方案不會動到已建出來的 Bot。
    新 Bot 預設不啟動排程、風控欄位留空（None＝不啟用），交給使用者在 Bot 面板再調。
    全程 Paper，下單仍經 submit_market_order 雙閘把關，本端點不碰實盤安全閥。
    """
    p = _get_preset_or_404(db, preset_id)
    bot = Bot(
        name=options.name or p.name,
        strategy=p.strategy_key,
        symbol=p.symbol.upper(),
        params=p.params or {},
        trade_amount=options.trade_amount,
    )
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return {"id": bot.id, "name": bot.name, "symbol": bot.symbol, "strategy": bot.strategy}


# ========== 一鍵回測（Python 做） ==========
@router.post("/presets/{preset_id}/backtest")
def backtest_preset(
    preset_id: int,
    options: BacktestParams = BacktestParams(),
    db: Session = Depends(get_db),
):
    """
    對某方案跑一次 Python 回測：
    跑回測 → 算含 EV 的完整指標 → 存一筆 BacktestRun → 回結果。
    （Claude 不參與，純 Python 計算。）
    """
    p = _get_preset_or_404(db, preset_id)
    try:
        result = run_backtest(
            strategy_name=p.strategy_key,
            symbol=p.symbol,
            params=p.params or {},
            days=options.days,
            initial_cash=options.initial_cash,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"回測失敗：{e}")

    # 把這次回測存成一筆紀錄（當 Claude 的記憶）
    run = BacktestRun(
        preset_id=p.id,
        strategy_key=p.strategy_key,
        params=p.params or {},
        symbol=p.symbol,
        period_days=options.days,
        metrics=result,
        is_good=False,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # 回完整回測結果 + 這筆紀錄的 id（前端拿來顯示、之後可請 Claude 檢討）
    return {"run_id": run.id, **result}


# ========== 回測紀錄 ==========
@router.get("/backtest-runs")
def list_backtest_runs(favorite: bool = False, db: Session = Depends(get_db)):
    """
    列出回測歷史（摘要版），依期望值 EV 由高到低排序。
    :param favorite: True 時只回標記為「好策略」(is_good) 的紀錄
    """
    query = db.query(BacktestRun)
    if favorite:
        query = query.filter(BacktestRun.is_good.is_(True))
    runs = query.all()
    # SQLite 對 JSON 欄位排序不便，改在 Python 端依 EV 排（資料量小，無虞）
    runs.sort(key=_ev_of, reverse=True)
    return [_run_summary(r) for r in runs]


@router.get("/backtest-runs/{run_id}")
def get_backtest_run(run_id: int, db: Session = Depends(get_db)):
    """看單筆回測紀錄的完整內容（含 metrics 全套 + Claude 檢討）。"""
    run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="找不到這筆回測紀錄")
    return {
        "id": run.id,
        "preset_id": run.preset_id,
        "strategy_key": run.strategy_key,
        "params": run.params,
        "symbol": run.symbol,
        "period_days": run.period_days,
        "metrics": run.metrics,
        "is_good": run.is_good,
        "claude_postmortem": run.claude_postmortem,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@router.get("/backtest-runs/{run_id}/report", response_class=HTMLResponse)
def get_backtest_run_report(run_id: int, db: Session = Depends(get_db)):
    """
    產這筆回測的 quantstats HTML 績效報表（資金曲線、回撤、月報酬表、各項比率）。
    直接讀該筆 metrics 裡存好的 equity_curve，不必重跑回測、不連線。
    前端可用 <a target="_blank"> 或開新視窗直接顯示這份 HTML。
    """
    run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="找不到這筆回測紀錄")

    equity_curve = (run.metrics or {}).get("equity_curve")
    if not equity_curve or len(equity_curve) < 2:
        raise HTTPException(status_code=400, detail="這筆回測沒有足夠的資金曲線資料可產報表")

    # quantstats 只能寫到檔案，故先寫到暫存檔再讀回來回傳，讀完即刪。
    tmp_path = os.path.join(tempfile.gettempdir(), f"albee_report_{run_id}.html")
    try:
        tearsheet_html(
            equity_curve,
            tmp_path,
            title=f"{run.symbol} / {run.strategy_key} 績效報表",
        )
        with open(tmp_path, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"產生報表失敗：{e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return HTMLResponse(content=html)


@router.put("/backtest-runs/{run_id}/favorite")
def toggle_backtest_run_favorite(
    run_id: int, is_good: bool = True, db: Session = Depends(get_db)
):
    """把某筆回測標記/取消「好策略」（收藏進榜）。"""
    run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="找不到這筆回測紀錄")
    run.is_good = is_good
    db.commit()
    return {"id": run.id, "is_good": run.is_good}


# ========== 主動提醒（Phase 5 選配） ==========
def _build_reminders(db: Session) -> list[dict]:
    """
    掃出「值得使用者主動關注」的事項，純讀現有資料、不連網。回傳由重要到次要。

    三種來源：
      1. review_negative_ev：回測 EV 為負且還沒做檢討 → 提示請 Claude 助手檢討。
      2. deploy_good_strategy：標記為好策略(is_good)、但同 標的+策略 還沒建成 Bot →
         提示可一鍵轉 Bot 實跑。
      3. propose_live_candidate（Phase 10 step-06）：Paper Bot 實績達標、但還沒提議上真錢 →
         提示可送董事會核准。達標判斷一律走 promotion 的純函式（EV 看樣本外、樣本要夠）。
    """
    # 延遲匯入避免循環依賴（promotion 也用到 performance/automation_config）
    from backend.routers.promotion import (
        evaluate_promotion_readiness,
        _bot_paper_stats,
        _best_oos_ev,
    )
    from backend.services.automation_config import get_config

    reminders: list[dict] = []

    # 現有 Bot 的 (symbol, strategy) 集合，用來判斷好策略是否已實跑
    existing = {
        (b.symbol.upper(), b.strategy)
        for b in db.query(Bot.symbol, Bot.strategy).all()
    }

    for run in db.query(BacktestRun).all():
        ev = _ev_of(run)
        # 1) 負 EV 未檢討
        if ev != float("-inf") and ev < 0 and not run.claude_postmortem:
            reminders.append({
                "type": "review_negative_ev",
                "run_id": run.id,
                "preset_id": run.preset_id,
                "symbol": run.symbol,
                "strategy_key": run.strategy_key,
                "expected_value": ev,
                "message": f"{run.symbol}／{run.strategy_key} 回測 EV 為負（{ev:.2f}）且尚未檢討，"
                           f"建議請助手分析錯在哪。",
            })
        # 2) 好策略尚未實跑
        if run.is_good and (run.symbol.upper(), run.strategy_key) not in existing:
            reminders.append({
                "type": "deploy_good_strategy",
                "run_id": run.id,
                "preset_id": run.preset_id,
                "symbol": run.symbol,
                "strategy_key": run.strategy_key,
                "expected_value": None if ev == float("-inf") else ev,
                "message": f"{run.symbol}／{run.strategy_key} 已標為好策略但還沒實跑，"
                           f"可一鍵轉成 Bot。",
            })

    # 3) Paper Bot 實績達標、但還沒提議上真錢 → 提示送董事會核准
    cfg = get_config(db)
    for bot in db.query(Bot).filter(Bot.promotion_status == "paper").all():
        stats = _bot_paper_stats(db, bot.id)
        oos_ev = _best_oos_ev(db, bot.symbol, bot.strategy)
        verdict = evaluate_promotion_readiness(
            stats, oos_ev,
            ev_threshold=cfg.ev_threshold,
            winrate_threshold=cfg.winrate_threshold,
        )
        if verdict["ready"]:
            reminders.append({
                "type": "propose_live_candidate",
                "bot_id": bot.id,
                "symbol": bot.symbol,
                "strategy_key": bot.strategy,
                "expected_value": oos_ev,
                "message": f"{bot.symbol}／{bot.strategy} 的 Bot「{bot.name}」Paper 表現達標"
                           f"（OOS EV={oos_ev}、勝率={stats.get('win_rate_pct')}%），"
                           f"可提議送董事會核准上真錢。",
            })

    return reminders


@router.get("/reminders")
def get_reminders(db: Session = Depends(get_db)):
    """回傳主動提醒清單（給前端橫幅顯示）。無事項時回空陣列。"""
    return {"reminders": _build_reminders(db)}
