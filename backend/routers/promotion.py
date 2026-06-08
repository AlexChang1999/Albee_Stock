"""
董事會核准 API（Phase 10 step-06，人在迴路）
================================================
讓老闆在一頁「核准 / 退回」某 Bot 從 Paper（模擬）晉升到真錢。流程：
  系統/人提議（propose）→ 待核（proposed_live）→ 老闆核准（approve）/ 退回（reject）。

★安全紅線（最重要）：
  本檔的「核准」只是**多一道人工閘**，approved_live 只是「人已同意」的旗標，
  **不放行真錢**。真錢下單仍須 ALPACA_BASE_URL 實盤 + ALLOW_LIVE_TRADING=true 雙閘，
  由 alpaca_client.submit_market_order 把關（兩者 AND）。本檔完全不碰那道安全閥、
  不改 alpaca_client、不改 .env 語意、不做自動晉升（一律人工點按 approve/reject）。

職責分離：本檔只管「晉升狀態」的流轉與證據呈現，不建 Bot、不下單、不跑回測。
達標證據（Paper 實績 + 機會清單 OOS EV）一律取自既有服務，不在這裡重算。
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Bot, TradeLog, Opportunity
from backend.services.performance import compute_bot_stats
from backend.services.automation_config import get_config
from backend.services import notifier

router = APIRouter(tags=["Promotion"])


# ---------- 請求資料格式 ----------
class RejectIn(BaseModel):
    """退回時附理由（會寫進 Bot 的 promotion_reason 供日後追溯）。"""
    reason: str = ""


# ---------- 純函式（不碰 DB / 網路，好單元測試）----------
def evaluate_promotion_readiness(
    bot_stats: dict,
    oos_expected_value: Optional[float],
    *,
    ev_threshold: float,
    winrate_threshold: float,
    min_round_trips: int = 3,
) -> dict:
    """
    判斷一個 Paper Bot 是否「達標、值得提議上真錢」。純函式、好測試。

    達標規則（三者皆須過，誠實守則：EV 看樣本外、要有足夠樣本）：
      1. 機會清單的樣本外 EV（OOS EV）≥ ev_threshold。
      2. Paper 實跑勝率 ≥ winrate_threshold。
      3. Paper 完整買賣次數 ≥ min_round_trips（樣本太少不算數，避免運氣）。

    :param bot_stats: compute_bot_stats(...) 的結果（含 win_rate_pct / num_round_trips）。
    :param oos_expected_value: 該 (symbol, strategy) 在機會清單的最佳 OOS EV；None = 沒對應候選。
    :return: {"ready": bool, "reasons": [未達標原因...], "oos_expected_value": ..., 各指標}
    """
    reasons: list[str] = []

    if oos_expected_value is None or oos_expected_value < ev_threshold:
        reasons.append(
            f"OOS EV {oos_expected_value} 未達門檻 {ev_threshold}"
        )
    win_rate = bot_stats.get("win_rate_pct", 0.0)
    if win_rate < winrate_threshold:
        reasons.append(f"Paper 勝率 {win_rate}% 未達門檻 {winrate_threshold}%")
    round_trips = bot_stats.get("num_round_trips", 0)
    if round_trips < min_round_trips:
        reasons.append(f"Paper 完整買賣 {round_trips} 次，樣本不足（需 ≥ {min_round_trips}）")

    return {
        "ready": not reasons,
        "reasons": reasons,
        "oos_expected_value": oos_expected_value,
        "win_rate_pct": win_rate,
        "num_round_trips": round_trips,
    }


def _evidence_summary(stats: dict, oos_ev: Optional[float]) -> str:
    """組一句「達標證據」摘要，存進 promotion_reason 供前端與日後追溯。"""
    return (
        f"OOS EV={oos_ev}；Paper 勝率={stats.get('win_rate_pct')}%、"
        f"完整買賣={stats.get('num_round_trips')} 次、報酬={stats.get('return_pct')}%"
    )


# ---------- 內部小工具（碰 DB）----------
def _get_bot_or_404(db: Session, bot_id: int) -> Bot:
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="找不到這個 Bot")
    return bot


def _bot_paper_stats(db: Session, bot_id: int) -> dict:
    """查某 Bot 的 Paper 交易紀錄（由舊到新）算實績。重用 compute_bot_stats。"""
    rows = (
        db.query(TradeLog)
        .filter(TradeLog.bot_id == bot_id)
        .order_by(TradeLog.created_at.asc())
        .all()
    )
    trades = [{"side": r.side, "qty": r.qty, "price": r.price} for r in rows]
    return compute_bot_stats(trades)


def _best_oos_ev(db: Session, symbol: str, strategy_key: str) -> Optional[float]:
    """取該 (symbol, strategy) 在機會清單的最佳 OOS EV（沒有就 None）。"""
    rows = (
        db.query(Opportunity.oos_expected_value)
        .filter(
            Opportunity.symbol == symbol,
            Opportunity.strategy_key == strategy_key,
            Opportunity.oos_expected_value.isnot(None),
        )
        .all()
    )
    vals = [r[0] for r in rows if r[0] is not None]
    return max(vals) if vals else None


def _serialize(db: Session, bot: Bot) -> dict:
    """把 Bot 的晉升狀態 + 達標證據組成前端要的一包。"""
    stats = _bot_paper_stats(db, bot.id)
    oos_ev = _best_oos_ev(db, bot.symbol, bot.strategy)
    return {
        "bot_id": bot.id,
        "name": bot.name,
        "symbol": bot.symbol,
        "strategy_key": bot.strategy,
        "promotion_status": bot.promotion_status,
        "promotion_proposed_at": (
            bot.promotion_proposed_at.isoformat() if bot.promotion_proposed_at else None
        ),
        "promotion_reason": bot.promotion_reason,
        "paper_stats": stats,
        "oos_expected_value": oos_ev,
    }


# ---------- 端點 ----------
@router.get("/promotions")
def list_promotions(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    列出晉升清單。預設只回「待核（proposed_live）」；帶 status 可看其他狀態。

    :param status: 可選；paper / proposed_live / approved_live / rejected。預設 proposed_live。
    """
    target = status or "proposed_live"
    bots = (
        db.query(Bot)
        .filter(Bot.promotion_status == target)
        .order_by(Bot.promotion_proposed_at.desc())
        .all()
    )
    return [_serialize(db, b) for b in bots]


@router.post("/promotions/{bot_id}/propose")
def propose_promotion(bot_id: int, db: Session = Depends(get_db)):
    """
    提議某 Bot 上真錢：paper / rejected → proposed_live，附達標證據，並主動通知一次。

    冪等：已是 proposed_live 直接回現況、不重複通知（去抖，不洗頻）。
    達標與否由 evaluate_promotion_readiness 判斷；未達標回 409 並附原因（不硬提議）。
    """
    bot = _get_bot_or_404(db, bot_id)

    # 已在待核 → 冪等回現況，不重複通知
    if bot.promotion_status == "proposed_live":
        return _serialize(db, bot)
    # 已核准 → 不需再提議
    if bot.promotion_status == "approved_live":
        raise HTTPException(status_code=409, detail="此 Bot 已核准上真錢，無需再提議")

    cfg = get_config(db)
    stats = _bot_paper_stats(db, bot.id)
    oos_ev = _best_oos_ev(db, bot.symbol, bot.strategy)
    verdict = evaluate_promotion_readiness(
        stats,
        oos_ev,
        ev_threshold=cfg.ev_threshold,
        winrate_threshold=cfg.winrate_threshold,
    )
    if not verdict["ready"]:
        raise HTTPException(
            status_code=409,
            detail="尚未達標，不提議上真錢：" + "；".join(verdict["reasons"]),
        )

    bot.promotion_status = "proposed_live"
    bot.promotion_proposed_at = datetime.now()
    bot.promotion_reason = _evidence_summary(stats, oos_ev)
    db.commit()
    db.refresh(bot)

    # 主動通知一次（單一事件、不會在 /promotions 輪詢時重複洗頻）
    notifier.notify(
        f"📈 Bot #{bot.id}「{bot.name}」（{bot.symbol}/{bot.strategy}）Paper 表現達標，"
        f"已提議上真錢，待你核准。{bot.promotion_reason}"
    )
    return _serialize(db, bot)


@router.post("/promotions/{bot_id}/approve")
def approve_promotion(bot_id: int, db: Session = Depends(get_db)):
    """
    老闆核准：proposed_live → approved_live。冪等（已核准回現況）。

    ★ approved_live 只是「人已同意」旗標，不放行真錢；真錢仍受雙閘把關。
    """
    bot = _get_bot_or_404(db, bot_id)
    if bot.promotion_status == "approved_live":
        return _serialize(db, bot)
    if bot.promotion_status != "proposed_live":
        raise HTTPException(status_code=409, detail="只有『待核』的 Bot 能核准")
    bot.promotion_status = "approved_live"
    db.commit()
    db.refresh(bot)
    return _serialize(db, bot)


@router.post("/promotions/{bot_id}/reject")
def reject_promotion(bot_id: int, body: RejectIn, db: Session = Depends(get_db)):
    """
    老闆退回：proposed_live → rejected，附理由（寫進 promotion_reason 供追溯）。冪等。
    """
    bot = _get_bot_or_404(db, bot_id)
    if bot.promotion_status == "rejected":
        return _serialize(db, bot)
    if bot.promotion_status != "proposed_live":
        raise HTTPException(status_code=409, detail="只有『待核』的 Bot 能退回")
    bot.promotion_status = "rejected"
    bot.promotion_reason = (body.reason or "").strip() or "（未填理由）"
    db.commit()
    db.refresh(bot)
    return _serialize(db, bot)
