"""
全自動護欄 — 模式 B 自動部署（改版 Phase 4 / Phase 6 強化）
=============================================================
「自動駕駛」：盤前排程跑 AI 海選，對 EV + 勝率同時超標的策略「無人工確認」自動建 Bot。

這是整個系統風險最高的一塊，所以層層設防：
1. **總開關預設關**（settings.AUTO_DEPLOY_ENABLED=false）：沒明確開，排程不會自動建任何 Bot。
2. **雙重門檻**：EV 與勝率兩個都要過（plan_deployments 純函式把關）。
3. **情緒閘**（Phase 6 step-07）：bearish / 分數過低 → 情緒否決，不進部署（EV 為主、情緒為輔）。
4. **組合回撤熔斷**（Phase 6 step-09）：總權益跌破門檻 → 整輪不建任何 Bot。
5. **資金守門**（Phase 6 step-05）：建 Bot 前查帳戶現金，只建付得起的，其餘列 rejected。
6. **名額上限**：最多同時自動建 N 個（防一次梭哈），且同一檔已有 Bot 不重複建。
7. **與實盤雙閘獨立**：開自動化 ≠ 開實盤。自動建的 Bot 下單一樣經 alpaca_client.submit_market_order
   的實盤雙閘把關，預設 Paper（模擬）。本檔完全不碰那道安全閥。

職責：本檔負責「決定要部署誰 + 實際建 Bot 掛排程」；海選交給 screener、建 Bot/排程沿用既有流程。
"""

from backend.config import settings
from backend.database import SessionLocal
from backend.models import Bot
from backend.services import screener
from backend.services.capital import plan_capital
from backend.services.circuit_breaker import check_breaker
from backend.services.notifier import notify
from backend.bots.bot_manager import bot_manager


# ============================================================
# 純函式：情緒入決策（Phase 6 step-07）
# ============================================================
def apply_sentiment(recommendations: list[dict], *, min_score: float, enabled: bool) -> list[dict]:
    """
    把第二層 LLM 的情緒分數真正接進部署決策（EV 為主、情緒為輔）。

    規則：
    - enabled=False → 原樣回傳（完全退回純 EV 行為，向後相容）。
    - label == "bearish" 或 score < min_score → **情緒否決**，從部署候選剔除。
    - sentiment 為 None（沒跑情緒 / 被外送閘擋下）→ 視為中性、不否決（best-effort）。
    - 非否決者：以情緒分數作為「OOS EV 排序的次要加權」（主排序鍵仍是 OOS EV，
      情緒絕不把更高 EV 的標的擠到更低 EV 標的後面）。

    :return: 通過情緒閘、且依（OOS EV, 情緒分數）排好的部署候選清單。
    """
    if not enabled:
        return list(recommendations)

    kept = [
        r for r in recommendations
        if not screener.is_vetoed_by_sentiment(r.get("sentiment"), min_score=min_score)
    ]
    kept.sort(
        key=lambda r: (
            (r.get("metrics") or {}).get("oos_expected_value", float("-inf")),
            screener.sentiment_score(r.get("sentiment")),
        ),
        reverse=True,
    )
    return kept


# ============================================================
# 純函式：決定「這批推薦裡，哪些該自動部署」（好寫單元測試）
# ============================================================
def plan_deployments(
    recommendations: list[dict],
    *,
    ev_threshold: float,
    winrate_threshold: float,
    max_bots: int,
    existing_symbols: set,
    active_count: int,
    sentiment_min_score: float = 0.0,
    sentiment_enabled: bool = False,
) -> list[dict]:
    """
    從（已依 OOS EV 排序的）推薦清單，挑出符合自動部署條件的。

    規則（依序）：
    1. ★樣本外 EV > 門檻 且 樣本外勝率 >= 門檻（Phase 6 step-04：門檻一律比對 OOS，
       不看樣本內，過擬合的策略過不了關）；同一檔已有 Bot 不重複建。
    2. 情緒閘（Phase 6 step-07）：bearish / 分數過低否決，其餘以情緒做次要加權排序。
    3. 名額上限：不超過 max_bots − 目前已啟用數。

    :return: 該部署的推薦子清單（順序即部署順序）。
    """
    slots = max_bots - active_count
    if slots <= 0:
        return []

    seen = set(existing_symbols)  # 複製一份，邊挑邊加避免同批重複
    candidates = []
    for rec in recommendations:
        symbol = rec.get("symbol")
        if not symbol or symbol in seen:
            continue
        m = rec.get("metrics") or {}
        ev = m.get("oos_expected_value")
        wr = m.get("oos_win_rate_pct")
        if not isinstance(ev, (int, float)) or ev <= ev_threshold:
            continue
        if not isinstance(wr, (int, float)) or wr < winrate_threshold:
            continue
        candidates.append(rec)
        seen.add(symbol)

    # 情緒閘（EV 為主、情緒為輔）：在 EV/勝率門檻之後串接，否決 bearish / 過低者
    candidates = apply_sentiment(
        candidates, min_score=sentiment_min_score, enabled=sentiment_enabled
    )

    return candidates[:slots]


# ============================================================
# 編排：實際跑一輪自動部署
# ============================================================
def run_auto_deploy(db=None, *, force: bool = False, dry_run: bool = False) -> dict:
    """
    跑一輪模式 B：海選 → 篩門檻 → 資金守門 → 自動建 Bot + 掛排程。

    :param db: SQLAlchemy session；None 時自建一個（排程器呼叫時用）。
    :param force: True = 略過「總開關未開」的限制（手動觸發測試用）。排程一律 force=False。
    :param dry_run: True = 只回「會部署誰」不真的建（給 API 預覽 / 測試用）。
    :return: 摘要 dict（enabled、planned/approved/rejected/deployed 清單、各項統計）。
    """
    if not settings.AUTO_DEPLOY_ENABLED and not force:
        return {"enabled": False, "reason": "自動部署總開關未開（AUTO_DEPLOY_ENABLED=false）",
                "deployed": [], "planned": []}

    # 組合回撤熔斷（Phase 6 step-09）：熔斷期間整輪不建任何 Bot（只擋進、不擋出）
    breaker = check_breaker(db)
    if breaker["tripped"]:
        return {"enabled": True, "circuit_breaker": True,
                "reason": f"組合回撤熔斷中（權益 {breaker['equity_now']} / 峰值 {breaker['equity_peak']}），暫停自動部署",
                "deployed": [], "planned": []}

    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        # 1) 跑海選（每檔配資用自動部署的設定值，才和實際建出來的 Bot 一致）
        scan = screener.screen_watchlist(
            initial_cash=settings.AUTO_DEPLOY_CASH_PER_BOT,
            min_ev=0.0,
        )
        recs = scan.get("recommendations", [])

        # 2) 現況：已有哪些標的的 Bot、目前啟用幾個（算名額）
        bots = db.query(Bot).all()
        existing_symbols = {b.symbol for b in bots}
        active_count = sum(1 for b in bots if b.is_active)

        # 3) 純函式決定要部署誰（EV/勝率 + 情緒閘 + 名額）
        planned = plan_deployments(
            recs,
            ev_threshold=settings.AUTO_DEPLOY_EV_THRESHOLD,
            winrate_threshold=settings.AUTO_DEPLOY_WINRATE_THRESHOLD,
            max_bots=settings.AUTO_DEPLOY_MAX_BOTS,
            existing_symbols=existing_symbols,
            active_count=active_count,
            sentiment_min_score=settings.SENTIMENT_MIN_SCORE,
            sentiment_enabled=settings.SENTIMENT_GATING,
        )

        # 4) 資金守門（Phase 6 step-05）：best-effort 查帳戶現金，只留付得起的。
        #    查不到帳戶（離線 / 無金鑰）→ 略過守門（approved = planned），不阻斷預覽 / 測試。
        rejected: list[dict] = []
        approved = planned
        try:
            from backend.services.alpaca_client import alpaca_client
            available_cash = float(alpaca_client.get_account().cash)
        except Exception:
            available_cash = None
        if available_cash is not None:
            approved, rejected = plan_capital(
                planned,
                available_cash=available_cash,
                cash_per_bot=settings.AUTO_DEPLOY_CASH_PER_BOT,
                reserve_ratio=settings.PORTFOLIO_CASH_RESERVE_RATIO,
            )

        planned_summary = [
            {"symbol": r["symbol"], "strategy_key": r["strategy_key"],
             "ev": (r.get("metrics") or {}).get("oos_expected_value")}
            for r in approved
        ]

        if dry_run:
            return {"enabled": True, "dry_run": True, "scanned": len(recs),
                    "planned": planned_summary, "rejected": rejected, "deployed": []}

        # 5) 實際建 Bot + 掛排程（全程 Paper；下單仍受實盤雙閘把關）
        deployed = []
        for rec in approved:
            bot = Bot(
                name=f"AUTO-{rec['symbol']}-{rec['strategy_key']}",
                strategy=rec["strategy_key"],
                symbol=rec["symbol"],
                params=rec.get("params") or {},
                trade_amount=settings.AUTO_DEPLOY_CASH_PER_BOT,
                is_active=True,
            )
            db.add(bot)
            db.commit()
            db.refresh(bot)
            bot_manager.start_bot(bot, interval_seconds=bot.check_interval_sec or 60)
            deployed.append({"id": bot.id, "symbol": bot.symbol, "strategy_key": bot.strategy})

        if deployed:
            lines = "、".join(f"{d['symbol']}({d['strategy_key']})" for d in deployed)
            msg = f"🤖 模式 B 自動部署了 {len(deployed)} 個 Bot：{lines}（全程 Paper）"
            if rejected:
                msg += f"；另有 {len(rejected)} 檔因資金不足未部署"
            notify(msg)

        return {"enabled": True, "dry_run": False, "scanned": len(recs),
                "planned": planned_summary, "rejected": rejected, "deployed": deployed}
    finally:
        if own_session:
            db.close()
