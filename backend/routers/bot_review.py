"""
bot 汰弱審查員 API（Phase 13）
==============================
唯讀報表 + 一個手動觸發端點：

- GET  /bot-review/fits    ：策略×標的適配排行（哪檔股票適合哪個策略）——讀 strategy_symbol_fits。
- GET  /bot-review/culled  ：被審查員汰弱的 Bot 清單（含理由、時間）。
- POST /bot-review/run     ：手動跑一輪審查（不等每日排程，當場考核 + 汰弱），回統計。

定位：報表 + 手動觸發。真正的考核 / 汰弱邏輯在 services/bot_review.py；這裡不重算績效、
不直接動 Bot（POST 只是叫那支服務跑一輪）。
"""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Bot, StrategySymbolFit
from backend.services.bot_review import run_bot_review

router = APIRouter(tags=["BotReview"])

# verdict 排序權重（good 在前、insufficient 墊底；同級再按報酬率高到低）
_VERDICT_RANK = {"good": 0, "poor": 1, "insufficient": 2}


def _serialize_fit(f: StrategySymbolFit) -> dict:
    return {
        "id": f.id,
        "strategy_key": f.strategy_key,
        "symbol": f.symbol,
        "num_round_trips": f.num_round_trips,
        "win_rate_pct": f.win_rate_pct,
        "return_pct": f.return_pct,
        "max_drawdown_pct": f.max_drawdown_pct,
        "verdict": f.verdict,
        "sample_bot_id": f.sample_bot_id,
        "updated_at": f.updated_at.isoformat() if f.updated_at else None,
    }


def _serialize_culled(b: Bot) -> dict:
    return {
        "id": b.id,
        "name": b.name,
        "strategy": b.strategy,
        "symbol": b.symbol,
        "cull_reason": b.cull_reason,
        "culled_at": b.culled_at.isoformat() if b.culled_at else None,
    }


@router.get("/bot-review/fits")
def list_fits(
    strategy: Optional[str] = None,
    symbol: Optional[str] = None,
    verdict: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """
    策略×標的適配排行（good → poor → insufficient，同級按報酬率高到低）。

    :param strategy: 可選；只看某策略代號。
    :param symbol: 可選；只看某標的（不分大小寫）。
    :param verdict: 可選；只看某評等（good/poor/insufficient）。
    :param limit: 最多回幾筆（夾在 1~1000）。
    """
    q = db.query(StrategySymbolFit)
    if strategy:
        q = q.filter(StrategySymbolFit.strategy_key == strategy)
    if symbol:
        q = q.filter(StrategySymbolFit.symbol == symbol.upper())
    if verdict:
        q = q.filter(StrategySymbolFit.verdict == verdict)
    rows = q.limit(max(1, min(limit, 1000))).all()
    # verdict 優先、報酬率次之的排序在 Python 端做（跨 DB 一致、不靠方言）
    rows.sort(key=lambda f: (_VERDICT_RANK.get(f.verdict, 9), -(f.return_pct or 0.0)))
    return [_serialize_fit(f) for f in rows]


@router.get("/bot-review/culled")
def list_culled(limit: int = 200, db: Session = Depends(get_db)):
    """被審查員汰弱的 Bot 清單（最近汰的在前）。"""
    rows = (
        db.query(Bot)
        .filter(Bot.culled_at.isnot(None))
        .order_by(Bot.culled_at.desc())
        .limit(max(1, min(limit, 1000)))
        .all()
    )
    return [_serialize_culled(b) for b in rows]


@router.post("/bot-review/run")
def trigger_review(db: Session = Depends(get_db)):
    """
    手動跑一輪審查（考核 paper 艦隊 → upsert fit → 軟汰弱不及格 Bot）。

    回 run_bot_review 的統計：reviewed / fits_updated / culled / skipped_insufficient / failed。
    BOT_REVIEW_ENABLED=false 時服務內部直接 no-op（回全 0），與排程行為一致。
    """
    return run_bot_review(db)
