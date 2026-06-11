"""
Bot 活動事件中樞（BotActivityHub）
==================================
把「Bot 執行循環的每個步驟」變成即時事件，推給前端做可視化動畫。

為什麼需要這個？
- Bot 一輪 run_bot_once 不到 1 秒、排程 60 秒一輪，前端 30 秒輪詢只看得到
  last_checked_at——中間全黑盒，使用者無法確認機器人是「真跑」還是「假跑」。
- 正解：後端在執行循環各步驟（喚醒→抓數據→算訊號→風控→決策→下單→待機）
  發「真實事件」，走 WebSocket /ws/bot-activity 推給前端。前端動畫 100% 由
  真事件驅動，零假動畫。

執行緒橋接（最關鍵的設計）：
- run_bot_once 由 APScheduler 在「背景執行緒」跑（同步），而 WebSocket 連線
  活在 uvicorn 的 asyncio 事件迴圈上。跨執行緒喚醒迴圈，asyncio 官方唯一保證
  安全的入口是 loop.call_soon_threadsafe。
- 推送走「單一 asyncio.Queue + 單一 forwarder task」：所有 send 都在迴圈執行緒
  上序列化，(a) 保證事件順序（cycle_start → fetch → … → cycle_end 順序就是語義）、
  (b) 避免對同一 WebSocket 並發 send 交錯（starlette 不保證並發安全）。

安全鐵則：可視化絕不影響交易主流程——
- emit() 整段 try/except 吞掉，組事件失敗、hub 沒接上迴圈，都靜默 no-op。
- 事件只進記憶體扇出 + ring buffer（新連線回放用），不落 DB
  （持久化已有 DecisionLog，勿重複）。
"""

import asyncio
import time
from collections import deque


# phase 枚舉（前端據此挑動畫）：
#   cycle_start    這一輪開始（Bot 醒來）
#   fetch_data     抓資料中（查持倉/現價、抓 K 線）
#   compute_signal 策略計算訊號中
#   risk_check     風控檢查中（止損/追蹤止損/止盈）
#   decision       決策結果（帶 signal/action/reason/price；含觀望/跳過）
#   order_submitted 已送出市價單（帶 side/qty）
#   cycle_end      這一輪結束（帶 status + next_run_in_sec，前端據此倒數）
PHASES = {
    "cycle_start",
    "fetch_data",
    "compute_signal",
    "risk_check",
    "decision",
    "order_submitted",
    "cycle_end",
}


class BotActivityHub:
    """管理所有前端連線 + thread→asyncio 橋 + 事件扇出。"""

    # ring buffer 容量：新連線回放最近這麼多則，feed 開頁不會空白
    RECENT_MAX = 60

    def __init__(self) -> None:
        # 已連線的前端 WebSocket（廣播給全部，前端自己按 bot_id 過濾——
        # 單人系統、Bot 個位數，不值得做訂閱簿記）
        self._clients: set = set()
        # uvicorn 的事件迴圈（attach_loop 時記住；None = 還沒啟動/測試環境）
        self._loop: asyncio.AbstractEventLoop | None = None
        # 事件佇列 + 單一 forwarder task（在迴圈執行緒上序列化所有 send）
        self._queue: asyncio.Queue | None = None
        self._task: asyncio.Task | None = None
        # 最近事件的 ring buffer（新連線回放用）
        self._recent: deque = deque(maxlen=self.RECENT_MAX)

    # ---------- 啟動（main.py lifespan 呼叫一次）----------
    def attach_loop(self) -> None:
        """在 FastAPI lifespan 裡呼叫：記住主迴圈、建佇列、起 forwarder。

        lifespan 本身跑在 uvicorn 的事件迴圈上，get_running_loop 拿到的
        就是正確的迴圈。沒呼叫過（測試環境）→ publish 自動 no-op。
        """
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        self._task = self._loop.create_task(self._forward_loop())

    # ---------- 發佈（APScheduler 執行緒呼叫，thread-safe）----------
    def publish(self, event: dict) -> None:
        """把一則事件丟進佇列（跨執行緒安全）。

        沒有迴圈 / 迴圈已關（單元測試、啟動早期）→ 靜默 no-op，
        仿 QuoteHub._ensure_running 的防呆：可視化壞了不能影響交易。
        """
        self._recent.append(event)
        loop, queue = self._loop, self._queue
        if loop is None or queue is None or loop.is_closed():
            return
        # call_soon_threadsafe 是 asyncio 官方唯一保證跨執行緒安全的入口；
        # put_nowait 會在迴圈執行緒上執行，喚醒 forwarder 依序扇出 → 保證順序
        loop.call_soon_threadsafe(queue.put_nowait, event)

    # ---------- 連線管理（WebSocket 端點呼叫，都在迴圈執行緒上）----------
    async def connect(self, ws) -> None:
        """接受一個前端連線：先回放最近事件（feed 不空白），再登記進廣播名單。"""
        await ws.accept()
        for event in list(self._recent):
            try:
                await ws.send_json(event)
            except Exception:
                return  # 回放途中就斷線 → 不登記
        self._clients.add(ws)

    def disconnect(self, ws) -> None:
        """前端斷線時移除登記。"""
        self._clients.discard(ws)

    # ---------- 扇出（單一 consumer，保證事件順序）----------
    async def _forward_loop(self) -> None:
        """背景任務：從佇列逐則取出，推給所有連線。推失敗的連線視為斷線清掉。"""
        while True:
            event = await self._queue.get()
            for ws in list(self._clients):
                try:
                    await ws.send_json(event)
                except Exception:
                    self.disconnect(ws)


# 全域共用的單一中樞（整個後端就這一個）
hub = BotActivityHub()


def safe_float(value):
    """best-effort 轉 float：失敗（None / 測試假物件）回 None，絕不拋例外。"""
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def emit(bot, phase: str, detail: str = "", **extra) -> None:
    """組一則 Bot 活動事件並發佈。整段吞例外——可視化絕不影響交易主流程。

    :param bot: Bot ORM 物件（測試可能是假物件，屬性用 getattr 防呆）。
    :param phase: PHASES 之一。
    :param detail: 給人看的中文描述（前端直接顯示）。
    :param extra: 各 phase 的附加欄位——
        decision 帶 decision={signal, action, reason, price}；
        order_submitted 帶 order={side, qty}；
        cycle_end 帶 status / next_run_in_sec / is_active。
    """
    try:
        event = {
            "type": "bot_activity",
            "bot_id": getattr(bot, "id", None),
            "bot_name": getattr(bot, "name", ""),
            "symbol": getattr(bot, "symbol", ""),
            "phase": phase,
            "detail": detail,
            "ts": time.time(),
        }
        event.update(extra)
        hub.publish(event)
    except Exception:
        pass  # 鐵則：事件壞了就丟掉，交易照常
