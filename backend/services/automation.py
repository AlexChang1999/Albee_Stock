"""
全自動護欄 — 模式 B 自動部署（改版 Phase 4）
=============================================
「自動駕駛」：盤前排程跑 AI 海選，對 EV + 勝率同時超標的策略「無人工確認」自動建 Bot。

這是整個系統風險最高的一塊，所以層層設防：
1. **總開關預設關**（settings.AUTO_DEPLOY_ENABLED=false）：沒明確開，排程不會自動建任何 Bot。
2. **雙重門檻**：EV 與勝率兩個都要過（plan_deployments 純函式把關）。
3. **名額上限**：最多同時自動建 N 個（防一次梭哈），且同一檔已有 Bot 不重複建。
4. **與實盤雙閘獨立**：開自動化 ≠ 開實盤。自動建的 Bot 下單一樣經 alpaca_client.submit_market_order
   的實盤雙閘把關，預設 Paper（模擬）。本檔完全不碰那道安全閥。

職責：本檔負責「決定要部署誰 + 實際建 Bot 掛排程」；海選交給 screener、建 Bot/排程沿用既有流程。
"""

from backend.config import settings
from backend.database import SessionLocal
from backend.models import Bot
from backend.services import screener
from backend.services.notifier import notify
from backend.bots.bot_manager import bot_manager


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
) -> list[dict]:
    """
    從（已依 EV 排序的）推薦清單，挑出符合自動部署條件的。

    規則：EV > 門檻 且 勝率 >= 門檻；同一檔已有 Bot 不重複建；
         不超過名額上限（max_bots − 目前已啟用數）。

    :return: 該部署的推薦子清單（順序即部署順序）。
    """
    slots = max_bots - active_count
    seen = set(existing_symbols)  # 複製一份，邊挑邊加避免同批重複
    planned = []
    for rec in recommendations:
        if slots <= 0:
            break
        symbol = rec.get("symbol")
        if not symbol or symbol in seen:
            continue
        m = rec.get("metrics") or {}
        ev = m.get("expected_value")
        wr = m.get("win_rate_pct")
        if not isinstance(ev, (int, float)) or ev <= ev_threshold:
            continue
        if not isinstance(wr, (int, float)) or wr < winrate_threshold:
            continue
        planned.append(rec)
        seen.add(symbol)
        slots -= 1
    return planned


# ============================================================
# 編排：實際跑一輪自動部署
# ============================================================
def run_auto_deploy(db=None, *, force: bool = False, dry_run: bool = False) -> dict:
    """
    跑一輪模式 B：海選 → 篩門檻 → 自動建 Bot + 掛排程。

    :param db: SQLAlchemy session；None 時自建一個（排程器呼叫時用）。
    :param force: True = 略過「總開關未開」的限制（手動觸發測試用）。排程一律 force=False。
    :param dry_run: True = 只回「會部署誰」不真的建（給 API 預覽 / 測試用）。
    :return: 摘要 dict（enabled、planned/deployed 清單、各項統計）。
    """
    if not settings.AUTO_DEPLOY_ENABLED and not force:
        return {"enabled": False, "reason": "自動部署總開關未開（AUTO_DEPLOY_ENABLED=false）",
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

        # 3) 純函式決定要部署誰
        planned = plan_deployments(
            recs,
            ev_threshold=settings.AUTO_DEPLOY_EV_THRESHOLD,
            winrate_threshold=settings.AUTO_DEPLOY_WINRATE_THRESHOLD,
            max_bots=settings.AUTO_DEPLOY_MAX_BOTS,
            existing_symbols=existing_symbols,
            active_count=active_count,
        )

        planned_summary = [
            {"symbol": r["symbol"], "strategy_key": r["strategy_key"],
             "ev": (r.get("metrics") or {}).get("expected_value")}
            for r in planned
        ]

        if dry_run:
            return {"enabled": True, "dry_run": True, "scanned": len(recs),
                    "planned": planned_summary, "deployed": []}

        # 4) 實際建 Bot + 掛排程（全程 Paper；下單仍受實盤雙閘把關）
        deployed = []
        for rec in planned:
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
            notify(f"🤖 模式 B 自動部署了 {len(deployed)} 個 Bot：{lines}（全程 Paper）")

        return {"enabled": True, "dry_run": False, "scanned": len(recs),
                "planned": planned_summary, "deployed": deployed}
    finally:
        if own_session:
            db.close()
