"""
心跳 + dead-man switch（維運安全軌 H2）
========================================
一人公司沒有同事幫你盯系統。這支服務做兩件分工不同的事：

1. **每日心跳日報（給人看）**：每天固定時刻發一則通知到 LINE/Discord——
   「我還活著、持倉 X 檔、啟用 Bot Y 個、今日決策 N 筆、權益 $Z」。
   人沒收到日報就該起疑。

2. **dead-man ping（給機器看）**：每隔幾分鐘對「系統外側」的監測服務
   （healthchecks.io）發一個 GET。本機掛掉 → ping 停 → 外側服務主動發警報。
   為什麼警報要在外側：本機死了，本機發不出「我死了」的通知。

設計原則：
- 心跳**永不崩**——它就是用來證明活著的，任何查詢失敗都以 "?" 帶過照樣發。
- 不依賴開市：休市日也要證明系統活著。
- `HEARTBEAT_PING_URL` 留空 = dead-man 功能關（優雅降級，與全專案慣例一致）。
"""

from datetime import datetime, time as dt_time

import requests

from backend.config import settings
from backend.database import SessionLocal
from backend.models import Bot, DecisionLog
from backend.services.alpaca_client import alpaca_client
from backend.services.notifier import notify


def build_heartbeat_message(
    *,
    positions_count,
    active_bots,
    decisions_today,
    equity,
    now: datetime,
) -> str:
    """純函式：組每日心跳日報的文字。

    任一數字查不到時呼叫端傳 None，這裡以 "?" 顯示（缺資料也要發，發不出去才是事故）。
    """
    def _fmt(v):
        return "?" if v is None else v

    equity_text = "?" if equity is None else f"${equity:,.2f}"
    return (
        f"💓 [心跳] {now:%Y-%m-%d %H:%M} 系統存活\n"
        f"持倉 {_fmt(positions_count)} 檔｜啟用 Bot {_fmt(active_bots)} 個｜"
        f"今日決策 {_fmt(decisions_today)} 筆｜權益 {equity_text}"
    )


def run_daily_heartbeat() -> None:
    """每日心跳日報：蒐集現況 → notify。

    每一段查詢都各自 best-effort：持倉/權益要連 Alpaca、Bot/決策數要查 DB，
    任何一段失敗都換成 None 繼續——心跳本身永不崩、永遠會發。
    """
    # 持倉檔數（list_positions 失敗本身就回 []，但保險再包一層）
    try:
        positions_count = len(alpaca_client.list_positions())
    except Exception:
        positions_count = None

    # 帳戶權益（離線/無金鑰 → None）
    try:
        equity = float(alpaca_client.get_account().portfolio_value)
    except Exception:
        equity = None

    # 啟用中 Bot 數 + 今日決策筆數（DB 壞了也不擋心跳）
    active_bots = decisions_today = None
    try:
        db = SessionLocal()
        try:
            active_bots = db.query(Bot).filter(Bot.is_active.is_(True)).count()
            today_start = datetime.combine(datetime.now().date(), dt_time.min)
            decisions_today = (
                db.query(DecisionLog).filter(DecisionLog.created_at >= today_start).count()
            )
        finally:
            db.close()
    except Exception:
        pass

    notify(build_heartbeat_message(
        positions_count=positions_count,
        active_bots=active_bots,
        decisions_today=decisions_today,
        equity=equity,
        now=datetime.now(),
    ))


def ping_deadman() -> None:
    """對外側監測服務（healthchecks.io）發一個 GET 當「我還活著」的訊號。

    URL 留空 = 功能關，直接 return。失敗只印警告不丟例外——
    ping 偶爾失敗沒關係（外側有 grace 期），不該因此干擾排程器。
    """
    url = settings.HEARTBEAT_PING_URL
    if not url:
        return
    try:
        requests.get(url, timeout=10)
    except Exception as e:
        print(f"⚠️ dead-man ping 失敗（{e}）——外側若持續沒收到 ping 會發警報，這正是它的工作。")
