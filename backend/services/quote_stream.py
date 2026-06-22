"""
即時報價中樞（QuoteHub）
========================
負責「一條後端連線 → 扇出給多個前端」的即時報價推送。

為什麼這樣設計？
- Alpaca 免費版限制「一個帳戶同時只能開一條即時資料連線」。
  若讓每個瀏覽器各自連 Alpaca，會互相打架。
- 正解：後端集中向 Alpaca「拉」最新成交價（每隔幾秒一次），
  再把結果透過 WebSocket「推」給所有正在看的前端。前端只連後端，不碰 Alpaca。

運作流程：
1. 前端用 WebSocket 連上後端 /ws/quotes，送 {"action":"subscribe","symbols":["AAPL"]}
2. 後端把這個前端登記為「想看 AAPL」，並啟動背景輪詢任務（若還沒啟動）
3. 背景任務每 N 秒向 Alpaca 拉一次目前有人訂閱的股票價格，推給對應前端
4. 沒有任何前端在看時，背景任務自動停止（不浪費 Alpaca 額度）

注意：這是「輪詢 + 推送」版本（穩、收盤也不會像壞掉）。
拉價走「批次」：一輪所有訂閱股票只打 1 次 Alpaca（multi-symbol latest-trade），
N 檔 N 次往返 → 1 次。未來要升級成 Alpaca 真 tick 串流，
只要換掉 `_fetch_prices` 的來源，前端完全不用動。
"""

import asyncio
import time

from backend.config import settings
from backend.services.alpaca_client import alpaca_client


class QuoteHub:
    """管理所有前端連線、訂閱關係，以及背景輪詢任務。"""

    def __init__(self) -> None:
        # 每個前端 WebSocket → 它訂閱了哪些股票代號
        # 例：{ws_A: {"AAPL", "TSLA"}, ws_B: {"AAPL"}}
        self._clients: dict[object, set[str]] = {}
        # 背景輪詢任務的把手（None = 沒在跑）
        self._task: asyncio.Task | None = None
        # 拉價函式（批次：吃 symbol list、回 {symbol: price}）。
        # 抽出來是為了「測試時可替換成假資料」，不必真的連 Alpaca。
        self._fetch_prices = alpaca_client.get_latest_prices
        # 輪詢間隔（秒），讀設定檔
        self.poll_interval: float = settings.QUOTE_POLL_INTERVAL_SEC

    # ---------- 連線管理 ----------
    async def connect(self, ws) -> None:
        """接受一個前端 WebSocket 連線，登記進來（一開始沒訂閱任何股票）。"""
        await ws.accept()
        self._clients[ws] = set()

    def disconnect(self, ws) -> None:
        """前端斷線時，移除它的登記；若沒人在看了就停掉輪詢。"""
        self._clients.pop(ws, None)
        self._maybe_stop()

    # ---------- 訂閱管理 ----------
    def subscribe(self, ws, symbols: list[str]) -> None:
        """登記某前端想看哪些股票，並確保背景輪詢有在跑。"""
        self._clients.setdefault(ws, set()).update(symbols)
        self._ensure_running()

    def unsubscribe(self, ws, symbols: list[str]) -> None:
        """取消某前端對某些股票的訂閱。"""
        if ws in self._clients:
            self._clients[ws].difference_update(symbols)

    # ---------- 純邏輯（好測試，不碰網路/async）----------
    def subscribed_symbols(self) -> set[str]:
        """目前所有前端「合起來」想看的股票集合（去重）。"""
        result: set[str] = set()
        for symbols in self._clients.values():
            result |= symbols
        return result

    def clients_for(self, symbol: str) -> list:
        """回傳有訂閱某股票的前端清單（用 list 複本，避免推送時改到原 dict）。"""
        return [ws for ws, symbols in self._clients.items() if symbol in symbols]

    # ---------- 背景輪詢 ----------
    def _ensure_running(self) -> None:
        """若背景輪詢任務還沒跑（或已結束），就啟動一個。"""
        if self._task is not None and not self._task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 沒有事件迴圈（例如單元測試直接呼叫 subscribe）→ 不啟動輪詢，
            # 但訂閱簿記照常運作。真正在 FastAPI 裡跑時一定有迴圈。
            return
        self._task = loop.create_task(self._poll_loop())

    def _maybe_stop(self) -> None:
        """沒有任何前端在連線時，取消背景輪詢任務（省 Alpaca 額度）。"""
        if not self._clients and self._task is not None:
            self._task.cancel()
            self._task = None

    async def _poll_loop(self) -> None:
        """
        背景任務：每隔 poll_interval 秒，把目前有人訂閱的股票價格拉下來推出去。
        第一圈會「立刻」執行一次，所以前端訂閱後很快就會看到第一筆價格。
        """
        while True:
            symbols = sorted(self.subscribed_symbols())
            if symbols:
                try:
                    # 批次拉價：所有訂閱股票 1 次請求。同步網路請求直接 await 會卡住
                    # 事件迴圈，用 to_thread 丟到別的執行緒跑，不阻塞前端推送。
                    prices = await asyncio.to_thread(self._fetch_prices, symbols)
                except Exception:
                    # 整輪抓失敗（暫時斷線等）不該讓迴圈死掉，下一輪再試。
                    prices = {}
                ts = time.time()
                for symbol in symbols:
                    # 用「訂閱時的原字串」推送（前端用 === 比對 symbol）；
                    # 批次回應的 key 是大寫，兩種都查。抓不到的檔這輪自然不推送。
                    price = prices.get(symbol)
                    if price is None:
                        price = prices.get(symbol.upper())
                    if price is None:
                        continue
                    await self._broadcast(symbol, {
                        "symbol": symbol,
                        "price": float(price),
                        "ts": ts,
                    })
            await asyncio.sleep(self.poll_interval)

    async def _broadcast(self, symbol: str, message: dict) -> None:
        """把某股票的最新價，推給所有訂閱它的前端。推送失敗的前端視為斷線清掉。"""
        for ws in self.clients_for(symbol):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(ws)


# 全域共用的單一中樞（整個後端就這一個）
hub = QuoteHub()
