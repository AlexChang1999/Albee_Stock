"""
tracking error 對帳 + 自動降級（維運安全軌 H3）
================================================
「回測=實盤」鐵則守住了**估計**的誠實，但策略真的跑起來後，沒人比對
「回測說 OOS 期望值 X% vs Paper 實跑到底拿到多少」——tracking error 拉開
= 策略走鐘或回測假設失真。這支服務補上「有晉升、沒降級」的缺口：

- 每日對帳：Paper 每回合已實現報酬率（滾動近 N 回合均值）vs
  該 (symbol, strategy) 在機會清單的 OOS expectancy_pct。
- 實跑連續低於「OOS × 折扣」→ **自動停 Bot**（is_active=False + 移除排程）
  + 通知 + 落決策審計，**人再決定**砍掉或調整。

降級邊界（刻意保守）：
- 只停「新決策」，**不平倉、不撤券商端保護單**——既有持倉的保護不中斷。
- 單向不自動恢復：重啟由人走既有 POST /bots/{id}/start。
- 只在「有新回合平倉」的日子計數——防同一批樣本連日重複扣分。
- 樣本不足 / 無 OOS 基準 → 不對帳、不冤殺（comparable=False）。
- 與 promotion 狀態機正交：已 approved_live 的 Bot 一樣會被降級停跑。
"""

from datetime import datetime

from backend.config import settings
from backend.database import SessionLocal
from backend.models import Bot, TradeLog
from backend.models.decision_log import ACTION_DEMOTED
from backend.services.notifier import notify
from backend.services.performance import compute_round_trip_returns


def evaluate_tracking(
    round_trip_returns_pct: list[float],
    oos_expectancy_pct: float | None,
    *,
    min_round_trips: int = 5,
    window: int = 10,
    demote_ratio: float = 0.5,
) -> dict:
    """純函式：判定這個 Bot「這一刻」的 tracking 狀態。

    :param round_trip_returns_pct: Paper 每回合已實現報酬率 %（時間正序）。
    :param oos_expectancy_pct: 回測側基準（OOS 期望值佔本金 %）；None = 無基準。
    :param min_round_trips: 回合數低於此值不對帳（樣本太少不冤殺）。
    :param window: 取最近幾回合的平均來比（滾動窗）。
    :param demote_ratio: 門檻折扣——實跑 < OOS × 此值 算一次違規。
    :return: {
        "comparable":   bool   能不能對帳（False 時 breach 一律 False），
        "paper_ev_pct": float|None  實跑滾動均值，
        "threshold_pct": float|None 違規門檻，
        "breach":       bool   這一刻是否違規，
        "reason":       str    人看的一句話（通知 / 審計用）,
    }
    """
    n = len(round_trip_returns_pct or [])
    if oos_expectancy_pct is None:
        return {
            "comparable": False, "paper_ev_pct": None, "threshold_pct": None,
            "breach": False, "reason": "無 OOS 基準（機會清單沒有 oos_expectancy_pct），不對帳",
        }
    if n < min_round_trips:
        return {
            "comparable": False, "paper_ev_pct": None, "threshold_pct": None,
            "breach": False, "reason": f"完整回合 {n} < {min_round_trips}，樣本不足不對帳",
        }

    recent = round_trip_returns_pct[-window:]
    paper_ev = sum(recent) / len(recent)
    # oos ≤ 0 防衛性視為門檻 0（理論上部署閘已擋掉負 EV 的 Bot，這裡保險）
    threshold = max(oos_expectancy_pct * demote_ratio, 0.0)
    breach = paper_ev < threshold
    return {
        "comparable": True,
        "paper_ev_pct": round(paper_ev, 4),
        "threshold_pct": round(threshold, 4),
        "breach": breach,
        "reason": (
            f"Paper 近 {len(recent)} 回合均值 {paper_ev:.2f}% "
            f"{'<' if breach else '≥'} 門檻 {threshold:.2f}%"
            f"（OOS {oos_expectancy_pct:.2f}% × {demote_ratio}）"
        ),
    }


def _best_oos_expectancy(db, symbol: str, strategy_key: str) -> float | None:
    """取該 (symbol, strategy) 在機會清單的最佳 OOS expectancy_pct（仿 promotion._best_oos_ev）。"""
    from backend.models import Opportunity

    rows = (
        db.query(Opportunity.oos_expectancy_pct)
        .filter(
            Opportunity.symbol == symbol,
            Opportunity.strategy_key == strategy_key,
            Opportunity.oos_expectancy_pct.isnot(None),
        )
        .all()
    )
    vals = [r[0] for r in rows if r[0] is not None]
    return max(vals) if vals else None


def _demote_bot(db, bot: Bot, reason: str) -> None:
    """自動降級：停排程 + is_active=False + 落欄 + 決策審計 + 通知。

    ★只停「新決策」——不平倉、不撤券商端保護單（既有持倉的保護不中斷），
    砍不砍倉由人決定。單向不自動恢復。
    """
    from backend.bots.bot_manager import bot_manager
    from backend.models import DecisionLog

    bot.is_active = False
    bot.demoted_at = datetime.now()
    bot.demote_reason = reason
    db.add(DecisionLog(
        bot_id=bot.id,
        symbol=bot.symbol,
        signal="hold",
        reason=reason,
        price=None,
        action=ACTION_DEMOTED,
    ))
    db.commit()
    bot_manager.stop_bot(bot.id)
    notify(
        f"🔻 [{bot.name}] tracking error 自動降級：{reason}\n"
        f"已停排程（持倉與券商端保護單**不動**）。確認後可砍倉/調參，"
        f"或用 POST /bots/{bot.id}/start 重新啟用。"
    )


def run_tracking_check() -> None:
    """每日對帳入口（排程呼叫）：對每個啟用中的 Bot 跑一輪 tracking 判定。

    - 回合數沒有比上次多 → 跳過不計數（防同一批樣本連日重複扣分）。
    - 違規 → breach_count +1；回到門檻上 → 歸零。
    - breach_count ≥ TRACKING_DEMOTE_AFTER → 自動降級。
    - 單一 Bot 出錯不影響其他 Bot（best-effort）。
    """
    db = SessionLocal()
    try:
        bots = db.query(Bot).filter(Bot.is_active.is_(True)).all()
        for bot in bots:
            try:
                rows = (
                    db.query(TradeLog)
                    .filter(TradeLog.bot_id == bot.id)
                    .order_by(TradeLog.created_at.asc())
                    .all()
                )
                trades = [{"side": r.side, "qty": r.qty, "price": r.price} for r in rows]
                round_trips = compute_round_trip_returns(trades)

                # 沒有新回合 → 同一批樣本不重複計數
                if len(round_trips) <= (bot.tracking_last_rt_count or 0):
                    continue
                bot.tracking_last_rt_count = len(round_trips)

                verdict = evaluate_tracking(
                    [rt["return_pct"] for rt in round_trips],
                    _best_oos_expectancy(db, bot.symbol, bot.strategy),
                    min_round_trips=settings.TRACKING_MIN_ROUND_TRIPS,
                    window=settings.TRACKING_WINDOW,
                    demote_ratio=settings.TRACKING_DEMOTE_RATIO,
                )
                if not verdict["comparable"]:
                    db.commit()  # 仍要存 tracking_last_rt_count
                    continue

                if verdict["breach"]:
                    bot.tracking_breach_count = (bot.tracking_breach_count or 0) + 1
                else:
                    bot.tracking_breach_count = 0
                db.commit()

                if bot.tracking_breach_count >= settings.TRACKING_DEMOTE_AFTER:
                    _demote_bot(
                        db, bot,
                        f"連續 {bot.tracking_breach_count} 次對帳違規｜{verdict['reason']}",
                    )
            except Exception as e:
                # 單一 Bot 對帳失敗不擋其他 Bot；rollback 防 session 卡死
                db.rollback()
                print(f"⚠️ [{getattr(bot, 'name', bot)}] tracking 對帳失敗：{e}")
    finally:
        db.close()
