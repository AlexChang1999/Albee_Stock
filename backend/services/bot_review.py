"""
bot 汰弱審查員（Phase 13）
==========================
自動部署讓 Bot 數 ＝ 好策略數 × 標的數，會持續長（5 策略 × 38 檔 = 190 Bot）。
沒人管，艦隊很快塞滿「驗證時看似可以、實跑卻爛」的 Bot。這支服務是新「職位」：
每日定時對全體 **paper** Bot 做三件事——

1. **考核**：用既有 `performance.compute_bot_stats` 算每支 Bot 的實跑績效。
2. **記錄 fit**：把「(策略, 標的) → 績效 + 評等」upsert 進 `strategy_symbol_fits`
   註冊表（這就是「哪檔股票適合哪個策略」的排行/記憶）。
3. **軟汰弱**：實跑夠久（≥ MIN_AGE_DAYS）夠多筆（≥ MIN_ROUND_TRIPS）但績效不及格的
   Bot → 停用 + 標記（`is_active=False` + `culled_at`/`cull_reason`），**不刪資料**。

明確界線（防 slop / 防漂移，仿 tracking.py 的降級邊界）：
- ★ 只碰 `promotion_status="paper"` 的 Bot。proposed_live / approved_live（真錢相關）
  一律不動——汰弱是 paper 艦隊的清理，與上真錢無關。
- **軟汰弱非實刪**：只停新決策，**不平倉、不撤券商端保護單**；保留交易史 / DecisionLog /
  fit 註冊的來源。要真刪 Bot 走人工。
- 冪等：只看 `culled_at IS NULL`，被汰過的不再處理。
- 失敗隔離：單支 Bot 例外不擋整批（rollback 該支、繼續）。
- 一輪汰弱數設上限（MAX_CULL_PER_RUN）：門檻萬一設錯，一次最多誤殺這麼多支，不會清空整片。

設計：`run_bot_review` 才碰 DB（仿 auto_validate / auto_deploy_knowledge）；評等與汰弱判斷
抽成純函式 `review_bot`（吃 stats + 年齡 + 門檻，吐 verdict / cull / reason），好寫單元測試。
"""

import logging
from datetime import datetime

from backend.config import settings
from backend.database import SessionLocal
from backend.models import Bot, TradeLog, StrategySymbolFit
from backend.models.decision_log import ACTION_BOT_CULLED
from backend.services.notifier import notify
from backend.services.performance import compute_bot_stats

logger = logging.getLogger(__name__)


def review_bot(
    stats: dict,
    age_days: float,
    *,
    min_round_trips: int,
    min_age_days: int,
    good_winrate: float,
    cull_winrate: float,
    cull_return_pct: float,
    cull_max_dd: float,
) -> dict:
    """純函式：判定一支 Bot「這一刻」的評等與是否該汰弱。

    :param stats: performance.compute_bot_stats 的輸出
        （num_round_trips / win_rate_pct / return_pct / max_drawdown_pct）。
    :param age_days: Bot 建立至今天數（觀察寬限用）。
    :param min_round_trips: 低於此＝樣本不足，verdict="insufficient" 且永不汰。
    :param min_age_days: 建立後沒滿這天數不汰（給新 Bot 表現時間）。
    :param good_winrate: 評 "good" 的勝率門檻（且報酬率為正）。
    :param cull_winrate / cull_return_pct / cull_max_dd: 汰弱門檻
        （勝率 < / 報酬率 < / 回撤 > 任一中即汰）。
    :return: {
        "verdict": "good"|"poor"|"insufficient",  # 寫進 fit 註冊表
        "cull":    bool,                          # 是否該軟汰弱
        "reason":  str,                           # 汰弱理由（帶數字，給人看 / 審計）
    }
    """
    rt = int(stats.get("num_round_trips", 0) or 0)
    wr = float(stats.get("win_rate_pct", 0.0) or 0.0)
    ret = float(stats.get("return_pct", 0.0) or 0.0)
    dd = float(stats.get("max_drawdown_pct", 0.0) or 0.0)

    # ── 評等（給 fit 註冊表；只看績效，不看年齡）──
    if rt < min_round_trips:
        verdict = "insufficient"   # 樣本太少，還看不出好壞
    elif wr >= good_winrate and ret > 0:
        verdict = "good"
    else:
        verdict = "poor"

    # ── 汰弱判斷（要夠久 + 夠多筆，任一門檻不及格才汰）──
    cull = False
    reason = ""
    if rt >= min_round_trips and age_days >= min_age_days:
        fails: list[str] = []
        if wr < cull_winrate:
            fails.append(f"勝率 {wr:.1f}% < {cull_winrate:.0f}%")
        if ret < cull_return_pct:
            fails.append(f"報酬 {ret:.1f}% < {cull_return_pct:.0f}%")
        if dd > cull_max_dd:
            fails.append(f"回撤 {dd:.1f}% > {cull_max_dd:.0f}%")
        if fails:
            cull = True
            reason = (f"實跑 {rt} 回合、滿 {int(age_days)} 天，"
                      f"不及格：{'；'.join(fails)}")
    return {"verdict": verdict, "cull": cull, "reason": reason}


def _upsert_fit(db, bot: Bot, stats: dict, verdict: str, now: datetime) -> None:
    """把這支 Bot 的成績 upsert 進 strategy_symbol_fits（(策略,標的) 唯一，覆寫最新快照）。"""
    fit = (
        db.query(StrategySymbolFit)
        .filter(
            StrategySymbolFit.strategy_key == bot.strategy,
            StrategySymbolFit.symbol == bot.symbol,
        )
        .first()
    )
    if fit is None:
        fit = StrategySymbolFit(strategy_key=bot.strategy, symbol=bot.symbol)
        db.add(fit)
    fit.num_round_trips = int(stats.get("num_round_trips", 0) or 0)
    fit.win_rate_pct = float(stats.get("win_rate_pct", 0.0) or 0.0)
    fit.return_pct = float(stats.get("return_pct", 0.0) or 0.0)
    fit.max_drawdown_pct = float(stats.get("max_drawdown_pct", 0.0) or 0.0)
    fit.verdict = verdict
    fit.sample_bot_id = bot.id
    fit.updated_at = now


def _cull_bot(db, bot: Bot, reason: str) -> None:
    """軟汰弱：停排程 + is_active=False + culled_at/cull_reason + 決策審計 + 通知。

    仿 tracking._demote_bot：★只停新決策——不平倉、不撤券商端保護單；資料全留可查。
    """
    from backend.bots.bot_manager import bot_manager
    from backend.models import DecisionLog

    bot.is_active = False
    bot.culled_at = datetime.now()
    bot.cull_reason = reason
    db.add(DecisionLog(
        bot_id=bot.id,
        symbol=bot.symbol,
        signal="hold",
        reason=reason,
        price=None,
        action=ACTION_BOT_CULLED,
    ))
    db.commit()
    bot_manager.stop_bot(bot.id)
    notify(
        f"🗑️ [{bot.name}] 審查員汰弱：{reason}\n"
        f"已停用（持倉與券商端保護單**不動**、資料保留可查）。"
        f"要真刪走人工；想復用 POST /bots/{bot.id}/start。"
    )
    # 汰弱後嘗試觸發策略反饋迴圈：LLM 分析失效原因、提案新參數候選
    try:
        from backend.services.strategy_feedback import generate_candidate_from_paper
        generate_candidate_from_paper(bot.id, db)
    except Exception as _e:
        logger.warning("strategy_feedback 鉤子失敗（隔離，不影響汰弱）：%s", _e)


def run_bot_review(db=None) -> dict:
    """跑一輪審查：考核每支未汰的 paper Bot、upsert fit、軟汰弱不及格者。

    - BOT_REVIEW_ENABLED=false → 直接 return（排程掛載處也有閘，雙保險）。
    - 只取 promotion_status="paper" 且 culled_at IS NULL（冪等：汰過的不再碰）。
    - 單支例外 → 隔離（rollback 該支），繼續下一支。
    - 一輪汰弱數受 BOT_REVIEW_MAX_CULL_PER_RUN 上限保護（超過就只記 fit、不汰，留下輪）。

    :param db: 測試可注入 session；None = 自建（排程入口用）。
    :return: {"reviewed","fits_updated","culled","skipped_insufficient","failed"} 統計。
    """
    stats_out = {"reviewed": 0, "fits_updated": 0, "culled": 0,
                 "skipped_insufficient": 0, "failed": 0}
    if not settings.BOT_REVIEW_ENABLED:
        return stats_out

    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        bots = (
            db.query(Bot)
            .filter(Bot.promotion_status == "paper", Bot.culled_at.is_(None))
            .order_by(Bot.id)
            .all()
        )
        now = datetime.now()
        culled_this_run = 0
        for bot in bots:
            try:
                rows = (
                    db.query(TradeLog)
                    .filter(TradeLog.bot_id == bot.id)
                    .order_by(TradeLog.created_at.asc())
                    .all()
                )
                trades = [{"side": r.side, "qty": r.qty, "price": r.price} for r in rows]
                stats = compute_bot_stats(trades)
                age_days = (now - (bot.created_at or now)).days

                verdict = review_bot(
                    stats, age_days,
                    min_round_trips=settings.BOT_REVIEW_MIN_ROUND_TRIPS,
                    min_age_days=settings.BOT_REVIEW_MIN_AGE_DAYS,
                    good_winrate=settings.BOT_REVIEW_GOOD_WINRATE,
                    cull_winrate=settings.BOT_REVIEW_CULL_WINRATE,
                    cull_return_pct=settings.BOT_REVIEW_CULL_RETURN_PCT,
                    cull_max_dd=settings.BOT_REVIEW_CULL_MAX_DD,
                )
                _upsert_fit(db, bot, stats, verdict["verdict"], now)
                stats_out["reviewed"] += 1
                stats_out["fits_updated"] += 1
                if verdict["verdict"] == "insufficient":
                    stats_out["skipped_insufficient"] += 1

                # 該汰 + 未超一輪上限 → 軟汰弱（_cull_bot 內含 commit，連 fit 一起落）
                if verdict["cull"] and culled_this_run < settings.BOT_REVIEW_MAX_CULL_PER_RUN:
                    _cull_bot(db, bot, verdict["reason"])
                    culled_this_run += 1
                    stats_out["culled"] += 1
                else:
                    db.commit()   # 只記 fit（含「該汰但已達上限」的情形：留下輪再汰）
            except Exception as e:
                db.rollback()
                stats_out["failed"] += 1
                logger.warning("審查員：bot %s 考核失敗（隔離、續下一支）：%s",
                               getattr(bot, "id", "?"), e)
                continue
    finally:
        if own_session:
            db.close()

    logger.info(
        "審查員完成：reviewed=%s fits_updated=%s culled=%s insufficient=%s failed=%s",
        stats_out["reviewed"], stats_out["fits_updated"], stats_out["culled"],
        stats_out["skipped_insufficient"], stats_out["failed"],
    )
    return stats_out
