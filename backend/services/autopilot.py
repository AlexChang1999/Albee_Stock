"""
模式 B：自動駕駛護欄（Autopilot）── Phase 4
=============================================
藍圖「雙軌 AI 交易模式」的紅燈模式：後端週期性自動海選，當策略的
期望值 EV 與勝率「同時達標」就**無需人工確認**，自動建立 Bot 並掛上排程。

這是整套系統風險最高的功能，所以層層設防（全部讀 config 的環境變數）：

  1) 總開關 AUTO_PILOT_ENABLED 預設 False——沒明確開，這支整個不會被排程。
  2) 雙閾值：EV ≥ AUTO_PILOT_MIN_EV 且 勝率 ≥ AUTO_PILOT_MIN_WIN_RATE 才部署。
  3) 數量上限 AUTO_PILOT_MAX_BOTS：自動 Bot 達上限就停止再部署，防失控暴增。
  4) 同標的去重：某標的已有「自動建立」的 Bot，就不再重複自動建。
  5) 不繞過實盤雙閘：真正下單仍走 alpaca_client.submit_market_order，
     沒開實盤雙閘（ALLOW_LIVE_TRADING + 實盤網址）時只會在 Paper 模擬下單，不燒真錢。

設計成「一個函式跑一輪」（run_autopilot_scan），方便：
  - 排程器每隔 AUTO_PILOT_INTERVAL_SEC 自動呼叫一次；
  - 也能被 API（POST /automation/scan-now）手動觸發一次、立即看結果。
"""

from backend.config import settings
from backend.database import SessionLocal
from backend.models import Bot
from backend.services import screener
from backend.services.notifier import notify


def get_rules() -> dict:
    """回傳目前的模式 B 規則設定（給前端顯示 / API 查詢）。"""
    return {
        "enabled": settings.AUTO_PILOT_ENABLED,
        "min_ev": settings.AUTO_PILOT_MIN_EV,
        "min_win_rate": settings.AUTO_PILOT_MIN_WIN_RATE,
        "interval_sec": settings.AUTO_PILOT_INTERVAL_SEC,
        "max_bots": settings.AUTO_PILOT_MAX_BOTS,
        "trade_amount": settings.AUTO_PILOT_TRADE_AMOUNT,
        # 下單環境現況（提醒使用者自動 Bot 會在哪個環境交易）
        "is_paper": settings.IS_PAPER,
        "live_armed": (not settings.IS_PAPER) and settings.ALLOW_LIVE_TRADING,
    }


def _existing_auto_state(db) -> tuple[int, set[str]]:
    """查現有「自動建立」的 Bot：回傳 (數量, 已佔用的標的集合)，給上限與去重判斷用。"""
    rows = db.query(Bot).filter(Bot.auto_created.is_(True)).all()
    symbols = {b.symbol.upper() for b in rows}
    return len(rows), symbols


def run_autopilot_scan(force: bool = False) -> dict:
    """
    跑一輪模式 B 自動駕駛。

    :param force: True 時略過「總開關關閉」的檢查，仍跑一輪（給手動 scan-now 用，
        讓使用者就算總開關沒開也能「乾跑一次」看會挑出什麼、但仍會實際部署）。
        排程自動呼叫時用 force=False：總開關關著就直接跳過、什麼都不做。
    :return: dict，本輪掃描與部署的結果摘要（給 API 回傳 / 通知）。
    """
    # --- 總開關（force=True 可略過，給手動觸發用）---
    if not settings.AUTO_PILOT_ENABLED and not force:
        return {
            "ran": False,
            "reason": "AUTO_PILOT_ENABLED=false（模式 B 總開關關閉）",
            "deployed": [],
        }

    min_ev = settings.AUTO_PILOT_MIN_EV
    min_win_rate = settings.AUTO_PILOT_MIN_WIN_RATE
    max_bots = settings.AUTO_PILOT_MAX_BOTS
    trade_amount = settings.AUTO_PILOT_TRADE_AMOUNT

    # --- 海選：直接讓 screener 用 EV 門檻過濾（第一層量能 + 第二層回測取最佳 EV）---
    scan = screener.screen(min_ev=min_ev)
    recommendations = scan.get("recommendations", [])

    deployed = []          # 本輪實際部署的
    rejected = []          # 達 EV 門檻但勝率不足、被擋下的
    skipped_existing = []  # 同標的已有自動 Bot、去重跳過的
    cap_reached = False    # 是否因達數量上限而停止
    auto_count = 0         # 目前自動 Bot 數（含本輪新建），給回傳摘要用

    # 延後匯入，避免和 bot_manager 形成模組載入循環
    from backend.bots.bot_manager import bot_manager

    db = SessionLocal()
    try:
        auto_count, auto_symbols = _existing_auto_state(db)

        for rec in recommendations:
            symbol = rec["symbol"].upper()
            metrics = rec.get("metrics", {})
            ev = metrics.get("expected_value")
            win_rate = metrics.get("win_rate_pct")

            # 第二道閘：勝率門檻（EV 已由 screener 用 min_ev 過濾過）
            if win_rate is None or win_rate < min_win_rate:
                rejected.append({"symbol": symbol, "ev": ev, "win_rate": win_rate})
                continue

            # 去重：此標的已有自動建立的 Bot 就跳過
            if symbol in auto_symbols:
                skipped_existing.append(symbol)
                continue

            # 數量上限：達上限就停止再部署
            if auto_count >= max_bots:
                cap_reached = True
                break

            # --- 通過所有閘 → 自動建立 Bot 並掛排程 ---
            bot = Bot(
                name=f"🤖 {symbol} {rec['strategy_key']}（自動）",
                strategy=rec["strategy_key"],
                symbol=symbol,
                params=rec.get("params") or {},
                trade_amount=trade_amount,
                is_active=True,
                auto_created=True,
            )
            db.add(bot)
            db.commit()
            db.refresh(bot)

            bot_manager.start_bot(bot, interval_seconds=bot.check_interval_sec or 60)

            auto_count += 1
            auto_symbols.add(symbol)
            deployed.append({
                "bot_id": bot.id,
                "symbol": symbol,
                "strategy_key": rec["strategy_key"],
                "ev": ev,
                "win_rate": win_rate,
            })
            notify(
                f"🤖 模式 B 自動部署：{bot.name}\n"
                f"EV={ev} 勝率={win_rate}% "
                f"（環境：{'⚠️ 實盤真錢' if (not settings.IS_PAPER and settings.ALLOW_LIVE_TRADING) else '模擬 Paper'}）"
            )
    finally:
        db.close()

    return {
        "ran": True,
        "forced": force,
        "rules": {"min_ev": min_ev, "min_win_rate": min_win_rate, "max_bots": max_bots},
        "universe_size": scan.get("universe_size"),
        "layer1_passed": scan.get("layer1_passed", []),
        "candidates": len(recommendations),
        "deployed": deployed,
        "rejected_low_win_rate": rejected,
        "skipped_existing": skipped_existing,
        "cap_reached": cap_reached,
        "auto_bots_total": auto_count,
    }
