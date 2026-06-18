"""
FastAPI 入口
============
這是後端的「大門」。啟動後會提供一組 API 給前端（或你用瀏覽器/工具）呼叫。

啟動方式（在專案根目錄、啟動 venv 後）：
    uvicorn backend.main:app --reload

啟動後打開瀏覽器看自動產生的 API 文件：
    http://127.0.0.1:8000/docs

本檔只負責三件事：
1. 建立 app、設定 CORS、定義啟動/關閉流程（lifespan）
2. 提供最基本的端點（健康檢查 /、帳戶 /account）
3. 把各功能的路由（routers/）掛上去

實際的 API 細節分散在 backend/routers/ 底下，依功能各自一個檔案。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import init_db, SessionLocal
from backend.models import Bot
from backend.services.alpaca_client import alpaca_client
from backend.bots.bot_manager import bot_manager
from backend.routers import bots, backtest, orders, presets, chat, quotes, fundamentals, bars, recommendations, automation, strategies, knowledge, explorations, company, opportunities, promotion, factors, collector, political, macro, positions, bot_activity
from backend.services.bot_activity import hub as activity_hub
from backend.services.scheduler_lock import acquire_scheduler_lock, release_scheduler_lock


def _resume_active_bots() -> None:
    """
    啟動時把資料庫裡 is_active=True 的 Bot 重新掛回排程。

    排程器（APScheduler）只活在記憶體裡，後端一重啟就清空。
    若不在這裡重掛，重啟後那些「顯示啟用中」的 Bot 其實不會再跑，
    狀態與實際行為會對不上。這裡用各 Bot 自己的 check_interval_sec 重建排程。
    """
    db = SessionLocal()
    try:
        active = db.query(Bot).filter(Bot.is_active.is_(True)).all()
        for bot in active:
            seconds = bot.check_interval_sec or 60
            bot_manager.start_bot(bot, interval_seconds=seconds)
        if active:
            print(f"♻️  已恢復 {len(active)} 個啟用中的 Bot 排程")
    finally:
        db.close()


# lifespan：定義 app「啟動時」與「關閉時」要做的事。
# 這是 FastAPI 現在推薦的寫法（取代舊的 @app.on_event）。
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- 啟動時 ---
    init_db()  # 把資料庫的表建好（如果還沒建）
    # Bot 活動事件中樞接上事件迴圈（必須在恢復排程之前——排程一接回來就會發事件）
    activity_hub.attach_loop()

    # 排程器選主：多實例（地端 + 雲端 VM 同連 Neon）時，只有搶到鎖的 leader 掛排程，
    # 避免重複下單 / 重複推播 / 互蓋止損。沒搶到的實例只當唯讀 API。
    # SQLite 單機永遠是 leader（無競爭）。下方所有 schedule_* 與 _resume_active_bots
    # 都會「對外動作或寫狀態」，故整段只在 leader 執行。
    is_leader = acquire_scheduler_lock()
    if not is_leader:
        print("🟡 已有其他實例擔任排程 leader：本實例只提供 API，不掛排程、不對外推播/下單")
        yield
        return

    _resume_active_bots()  # 重啟後把啟用中的 Bot 排程接回來
    # 模式 B：掛上盤前自動部署的每日定時工作（時刻讀 DB 規則；是否真的部署仍由 enabled 總開關控制）
    _db = SessionLocal()
    try:
        from backend.services.automation_config import get_config
        _cfg = get_config(_db)
        bot_manager.schedule_auto_deploy(_cfg.scan_hour)
        # Phase 10 step-02：掛上常駐機會探勘的週期 job（盤中每 N 分鐘；0=關，內部會跳過）
        bot_manager.schedule_opportunity_scan(_cfg.scan_interval_min)
        # Phase 10 step-04：掛上市場蒐集員收料 job（每 N 分鐘抓 RSS；0=關，沒設 feed 也會跳過）
        bot_manager.schedule_collector_scan(settings.COLLECTOR_INTERVAL_MIN)
        # Phase 12 step-02：掛上探勘橋每日 job（收件匣素材 → LLM triage → candidate；
        # DISCOVERY_ENABLED=false = 完全不掛，行為與沒這功能一樣）
        bot_manager.schedule_discovery(settings.DISCOVERY_HOUR)
        # Phase 12 step-03：掛上候選自動驗證每日 job（candidate → 既有 OOS 閘 →
        # validated/rejected，判準零修改；AUTO_VALIDATE_ENABLED=false = 完全不掛）
        bot_manager.schedule_auto_validate(settings.AUTO_VALIDATE_HOUR)
        # 知識庫策略 → 自動建 Paper Bot（排在驗證之後，吃到當天剛驗過的；★只建 paper、
        # 不碰真錢雙閘；AUTO_DEPLOY_KNOWLEDGE_ENABLED=false = 完全不掛）
        bot_manager.schedule_auto_deploy_knowledge(settings.AUTO_DEPLOY_KNOWLEDGE_HOUR)
        # 維運安全軌 H2：每日心跳日報 + dead-man ping（URL 沒設 = ping 關，日報照發）
        bot_manager.schedule_heartbeat(settings.HEARTBEAT_HOUR)
        bot_manager.schedule_deadman_ping(settings.HEARTBEAT_PING_INTERVAL_MIN)
        # 維運安全軌 H3：tracking error 每日對帳（連續違規自動降級停 Bot，人再決定）
        bot_manager.schedule_tracking_check(settings.TRACKING_CHECK_HOUR)
        # 每日領導股回測紀錄（只落 BacktestRun、不下單；LEADER_BACKTEST_ENABLED=false = 不掛）
        bot_manager.schedule_leader_backtest(settings.LEADER_BACKTEST_HOUR)
        # 開機補跑：家用電腦不是 24/7——啟動時把「時刻已過 + 今天還沒跑」的每日 job
        # 依管線順序立刻補跑（必須排在所有 schedule_* 之後，設定才齊）。
        bot_manager.schedule_catchup_on_boot()
    finally:
        _db.close()
    print(f"🚀 Albee Stock 啟動完成（排程 leader；模擬交易模式：{settings.IS_PAPER}）")
    yield
    # --- 關閉時 ---：釋放排程鎖，讓其他實例能接手當 leader
    release_scheduler_lock()


app = FastAPI(title="Albee Stock 交易機器人", lifespan=lifespan)

# CORS：允許前端（Vite 開發伺服器，預設 5173 埠）呼叫這個後端。
# 沒有這段，瀏覽器會以「跨來源」為由擋掉前端的 API 請求。
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],  # 允許所有 HTTP 方法（GET/POST...）
    allow_headers=["*"],
)


# ---------- 基本端點 ----------
@app.get("/")
def root():
    """健康檢查：確認服務有在跑。"""
    return {"message": "Albee Stock 後端運行中", "paper_trading": settings.IS_PAPER}


@app.get("/status")
def get_status():
    """
    回傳目前的交易環境狀態，給前端顯示醒目的「模擬／實盤」標示。

    live_armed = True 代表雙閘全開（實盤網址 + 安全閥），此時下單會動真錢。
    切換環境仍須手動改 .env，這裡只負責「如實顯示」現況，不提供切換按鈕，
    以保留防手滑的設計。
    """
    return {
        "is_paper": settings.IS_PAPER,            # 是否模擬環境（網址含 paper）
        "allow_live": settings.ALLOW_LIVE_TRADING,  # 安全閥是否開
        # 兩道閘都開 = 真的會送真錢單
        "live_armed": (not settings.IS_PAPER) and settings.ALLOW_LIVE_TRADING,
    }


@app.get("/account")
def get_account():
    """取得 Alpaca 帳戶資訊。"""
    try:
        acc = alpaca_client.get_account()
        return {
            "status": str(acc.status),
            "cash": acc.cash,
            "buying_power": acc.buying_power,
            "portfolio_value": acc.portfolio_value,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"連線 Alpaca 失敗：{e}")


# ---------- 掛上各功能的路由 ----------
# include_router 會把 routers/ 裡定義好的那一疊路由併進這個 app。
app.include_router(bots.router)
app.include_router(backtest.router)
app.include_router(orders.router)
app.include_router(presets.router)
app.include_router(chat.router)
app.include_router(quotes.router)
app.include_router(bot_activity.router)
app.include_router(fundamentals.router)
app.include_router(bars.router)
app.include_router(recommendations.router)
app.include_router(automation.router)
app.include_router(strategies.router)
app.include_router(knowledge.router)
app.include_router(explorations.router)
app.include_router(company.router)
app.include_router(opportunities.router)
app.include_router(promotion.router)
app.include_router(factors.router)
app.include_router(collector.router)
app.include_router(political.router)
app.include_router(macro.router)
app.include_router(positions.router)
