"""
Alpaca API 封裝
===============
把 Alpaca 的「交易」和「資料」功能包成好用的函式，
這樣策略和 Bot 不用直接面對 Alpaca SDK 的細節。

提供的功能：
- get_account()           取得帳戶資訊
- get_position(symbol)    查某檔股票目前持倉
- submit_market_order()   送出市價單（買/賣）
- submit_stop_order()     送出停損單（GTC，託管在券商端，斷電仍有效）
- submit_trailing_stop_order()  送出原生追蹤止損單（券商端自追盤中最高價）
- cancel_order()          撤單（撤不掉回 False，多半代表已成交）
- get_order()             查單一訂單現況
- get_open_orders()       列出未成交訂單（reconcile 用）
- get_bars()              取得歷史 K 線資料（給策略算指標）
- get_bars_multi()        一次請求抓多檔歷史 K 線（批次，省 N 倍往返）
- get_latest_price()      取得最新成交價
- get_latest_prices()     一次請求抓多檔最新成交價（批次）

資料 API 都過同一個 token bucket 限流器（免費版 200 req/min 保險絲）；
交易單（submit_*/cancel）不限流——下單延遲不可接受，且單量遠低於資料請求。
"""

import threading
import time
from datetime import datetime, timedelta

import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    GetOrdersRequest,
    MarketOrderRequest,
    StopOrderRequest,
    TrailingStopOrderRequest,
)
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame

from backend.config import settings


class _RateLimiter:
    """
    行程內共用的 token bucket 限流器（執行緒安全）。

    Alpaca 免費版資料 API 約 200 req/min。批次化抓取後請求數已大降，
    這是「保險絲」不是常態路徑：額度內直接放行（零延遲），
    超量才 sleep 等 token 補充（每秒補 per_minute/60 個）。
    per_minute=0 代表不限流（測試 / 付費方案用）。
    """

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._tokens = float(per_minute)  # 一開始滿桶
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """取得一個請求額度；額度不足時 sleep 到補充為止。"""
        if self.per_minute <= 0:
            return
        while True:
            with self._lock:
                now = time.monotonic()
                # 時鐘倒退（測試注入假時鐘、系統校時）視為 0 經過，絕不倒扣 token——
                # 否則負數巨量倒扣會算出「等好幾小時」的 sleep，整個行程卡死。
                elapsed = max(0.0, now - self._last)
                # 依經過時間補充 token（上限 = 滿桶 per_minute）
                self._tokens = min(
                    float(self.per_minute),
                    self._tokens + elapsed * (self.per_minute / 60.0),
                )
                self._last = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                # 算出湊滿 1 個 token 還要等多久（鎖外 sleep，不卡其他執行緒）
                wait = (1.0 - self._tokens) / (self.per_minute / 60.0)
            print(f"⏳ Alpaca 限流：請求過密，等待 {wait:.1f}s（額度 {self.per_minute}/min）")
            time.sleep(wait)


class AlpacaClient:
    """封裝 Alpaca 的交易與資料功能。"""

    def __init__(self) -> None:
        # 延遲初始化：這裡「不」立刻建立 Alpaca 的 client。
        # 原因：Alpaca SDK 在建立 client 時就會檢查金鑰，金鑰為空會直接丟
        # ValueError。若在這裡建立，沒有 .env 的環境（例如 CI 跑測試）光是
        # import 這個模組就會崩潰。改成第一次真正用到時才建立（見下方 property）。
        self._trading: TradingClient | None = None
        self._data: StockHistoricalDataClient | None = None
        # 開市狀態的短期快取：(到期時間戳, 是否開市)。
        # 多個 Bot 幾乎同時排程時，不必每個都各問一次 Alpaca 的 clock，省 API 額度。
        self._clock_cache: tuple[float, bool] | None = None
        # 資料 API 限流（免費版 200 req/min 的保險絲；0 = 不限流）
        self._limiter = _RateLimiter(settings.ALPACA_RATE_LIMIT_PER_MIN)

    @property
    def trading(self) -> TradingClient:
        """交易用客戶端（查帳戶、下單）。第一次用到才建立。paper=True 為模擬交易。"""
        if self._trading is None:
            self._trading = TradingClient(
                settings.ALPACA_API_KEY,
                settings.ALPACA_SECRET_KEY,
                paper=settings.IS_PAPER,
            )
        return self._trading

    @property
    def data(self) -> StockHistoricalDataClient:
        """資料用客戶端（查報價、抓 K 線）。第一次用到才建立。"""
        if self._data is None:
            self._data = StockHistoricalDataClient(
                settings.ALPACA_API_KEY,
                settings.ALPACA_SECRET_KEY,
            )
        return self._data

    # ---------- 市場狀態 ----------
    # 開市狀態快取多久（秒）。開/收盤只在固定時刻發生，短暫快取不影響正確性，
    # 卻能讓「多 Bot 同一輪檢查」共用一次查詢結果。
    CLOCK_CACHE_TTL_SEC = 30

    def is_market_open(self) -> bool:
        """
        美股現在是否開盤中。
        監聽系統每次檢查前先問這個：休市就別抓資料/下單，
        省 API 額度、也避免在沒有成交的時段送出怪單。

        結果會快取 CLOCK_CACHE_TTL_SEC 秒：多個 Bot 幾乎同時跑時，
        只有第一個真的去問 Alpaca，其餘吃快取，避免短時間內重複呼叫。
        """
        now = time.monotonic()
        if self._clock_cache is not None and now < self._clock_cache[0]:
            return self._clock_cache[1]

        self._limiter.acquire()  # 只有快取失效真的要打 API 時才占額度
        is_open = bool(self.trading.get_clock().is_open)
        self._clock_cache = (now + self.CLOCK_CACHE_TTL_SEC, is_open)
        return is_open

    # ---------- 帳戶 ----------
    def get_account(self):
        """取得帳戶資訊（現金、購買力等）。"""
        return self.trading.get_account()

    def get_position(self, symbol: str):
        """
        查某檔股票目前持倉。
        若沒有持倉，Alpaca 會丟例外，這裡接住並回傳 None。
        """
        try:
            return self.trading.get_open_position(symbol)
        except Exception:
            return None

    def list_positions(self):
        """
        列出目前所有持倉。
        連線/金鑰失敗（離線、沒設 .env、CI）時回空清單，讓上層優雅降級、不崩。
        """
        try:
            return self.trading.get_all_positions()
        except Exception:
            return []

    # ---------- 下單 ----------
    def _assert_live_allowed(self) -> None:
        """
        實盤安全閥（所有下單共用的同一道閘，第一道就擋）。
        連到實盤(真錢) 但沒有明確開啟 ALLOW_LIVE_TRADING → 直接拒絕，不送出。
        這道檢查刻意放在最前面：早於建立 client、早於任何真錢動作。
        市價/停損/追蹤止損所有 submit_* 都必須先過這裡，新增單型不可繞過。
        """
        if not settings.IS_PAPER and not settings.ALLOW_LIVE_TRADING:
            raise RuntimeError(
                "拒絕下單：目前連到『實盤(真錢)』環境，但安全閥未開啟。"
                "若確定要用真錢交易，請在 .env 設定 ALLOW_LIVE_TRADING=true。"
            )

    @staticmethod
    def _to_tif(time_in_force: str) -> TimeInForce:
        """把 "day"/"gtc" 字串轉成 Alpaca 的 TimeInForce 列舉。"""
        return TimeInForce.GTC if time_in_force.lower() == "gtc" else TimeInForce.DAY

    def submit_market_order(self, symbol: str, qty: float, side: str):
        """
        送出市價單。
        :param symbol: 股票代號，例如 "AAPL"
        :param qty: 股數
        :param side: "buy" 或 "sell"
        :return: Alpaca 的訂單物件
        """
        self._assert_live_allowed()  # 實盤安全閥（雙閘）

        order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL

        order_request = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=TimeInForce.DAY,  # 當日有效
        )
        return self.trading.submit_order(order_request)

    def submit_stop_order(
        self,
        symbol: str,
        qty: float,
        stop_price: float,
        side: str = "sell",
        time_in_force: str = "gtc",
    ):
        """
        送出停損單（stop order）。
        預設 GTC：掛在「券商伺服器端」直到成交或撤單——本機當機/斷網/重開機，
        止損照樣執行。這是維運安全軌「電腦掛掉不裸奔」的核心。
        注意：Alpaca 的 stop 單只支援整股（qty 必須是整數股數）。
        :param stop_price: 觸發價（跌破即以市價出場）
        """
        self._assert_live_allowed()  # 實盤安全閥（雙閘，與市價單同一道）

        order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL
        order_request = StopOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            stop_price=stop_price,
            time_in_force=self._to_tif(time_in_force),
        )
        return self.trading.submit_order(order_request)

    def submit_trailing_stop_order(
        self,
        symbol: str,
        qty: float,
        trail_percent: float,
        side: str = "sell",
        time_in_force: str = "gtc",
    ):
        """
        送出原生追蹤止損單（trailing stop order）。
        由券商端自己追蹤盤中最高價（HWM），比本機每分鐘輪詢精準，且斷電不失效。
        注意：同樣只支援整股。
        :param trail_percent: 回檔百分比「數字」，例如 3.0 代表從最高點回檔 3% 觸發
        """
        self._assert_live_allowed()  # 實盤安全閥（雙閘，與市價單同一道）

        order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL
        order_request = TrailingStopOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            trail_percent=trail_percent,
            time_in_force=self._to_tif(time_in_force),
        )
        return self.trading.submit_order(order_request)

    def cancel_order(self, order_id: str) -> bool:
        """
        撤單。回傳是否成功撤掉。
        已成交/已撤/查無此單 → 回 False、不丟例外。
        呼叫端據此判斷「券商端保護單是不是已經先成交了」：
        本機要出場前先撤保護單，撤不掉就代表券商端已處理，放棄本機賣出。
        """
        try:
            self.trading.cancel_order_by_id(order_id)
            return True
        except Exception:
            return False

    def get_order(self, order_id: str):
        """
        查單一訂單現況（status / filled_qty / filled_avg_price）。
        查不到（id 錯、連線失敗）回 None，讓上層優雅降級。
        """
        try:
            return self.trading.get_order_by_id(order_id)
        except Exception:
            return None

    def get_open_orders(self, symbol: str | None = None) -> list:
        """
        列出未成交（open）訂單，可選擇只看某一檔。
        reconcile 自癒用：每輪檢查券商端保護單是否還活著。
        連線/金鑰失敗回空清單（優雅降級，與 list_positions 同款）。
        """
        try:
            request = GetOrdersRequest(
                status=QueryOrderStatus.OPEN,
                symbols=[symbol] if symbol else None,
            )
            return self.trading.get_orders(filter=request)
        except Exception:
            return []

    # ---------- 資料 ----------
    def get_latest_price(self, symbol: str) -> float:
        """
        取得某檔股票的「最新成交價」。
        用成交價(trade)而非買賣報價(quote)，因為休市時 bid/ask 常為 0，
        用成交價在盤中、盤後都比較可靠。
        """
        self._limiter.acquire()
        request = StockLatestTradeRequest(symbol_or_symbols=symbol)
        trade = self.data.get_stock_latest_trade(request)[symbol]
        return trade.price

    def get_latest_prices(self, symbols: list[str]) -> dict[str, float]:
        """
        一次請求抓「多檔」最新成交價，回 {symbol: price}。

        N 檔 N 次 HTTP 往返 → 1 次（Alpaca 的 latest-trade API 原生支援多檔，
        回應本來就是按 symbol 索引的 dict）。抓不到的檔不在回傳 dict 裡，
        呼叫端用 .get() 取、缺的視為這輪沒報價。
        """
        # 大寫正規化 + 保序去重；空清單直接回空 dict，不打 API
        symbols = list(dict.fromkeys(s.upper() for s in symbols))
        if not symbols:
            return {}
        self._limiter.acquire()
        request = StockLatestTradeRequest(symbol_or_symbols=symbols)
        trades = self.data.get_stock_latest_trade(request)
        return {sym: float(trade.price) for sym, trade in trades.items()}

    def get_bars(self, symbol: str, days: int = 60) -> pd.DataFrame:
        """
        取得最近 N 天的「日 K 線」資料，回傳 pandas DataFrame。
        策略會用這份資料來計算指標（例如均線）。

        :param symbol: 股票代號
        :param days: 往前抓幾天
        :return: 含 open/high/low/close/volume 欄位的 DataFrame
        """
        self._limiter.acquire()
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,  # 日 K
            start=datetime.now() - timedelta(days=days),
        )
        bars = self.data.get_stock_bars(request)
        # .df 會直接給我們一個 pandas DataFrame，很方便
        df = bars.df
        # 資料是多層索引(symbol, timestamp)，這裡只留單一股票、重設索引
        if not df.empty:
            df = df.reset_index()
        return df

    def get_bars_multi(self, symbols: list[str], days: int = 60) -> dict[str, pd.DataFrame]:
        """
        一次 HTTP 請求抓「多檔」日 K，回 {symbol: DataFrame}。

        N 檔 N 次往返 → 1 次（StockBarsRequest 的 symbol_or_symbols 原生吃 list）。
        每檔 DataFrame 的欄位 / 排序 / 索引契約與 get_bars() 完全一致
        （reset_index 後同樣保留 symbol + timestamp 欄）。
        查無資料的檔回「空 DataFrame」——key 仍在，呼叫端不用接 KeyError。
        """
        # 大寫正規化 + 保序去重；空清單直接回空 dict，不打 API
        symbols = list(dict.fromkeys(s.upper() for s in symbols))
        if not symbols:
            return {}

        self._limiter.acquire()
        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=days),
        )
        df = self.data.get_stock_bars(request).df

        # 先以空 DataFrame 打底：Alpaca 對查無資料的 symbol 直接不回任何列
        result: dict[str, pd.DataFrame] = {s: pd.DataFrame() for s in symbols}
        if not df.empty:
            df = df.reset_index()  # 多層索引 (symbol, timestamp) → 一般欄位
            for sym, group in df.groupby("symbol", sort=False):
                result[str(sym)] = group.reset_index(drop=True)
        return result


# 建立一個全域共用的實例，其他檔案 import 後直接用。
# 因為改成延遲初始化，這行不會碰到金鑰，沒有 .env 也能安全 import；
# 真正的金鑰檢查/錯誤會發生在第一次呼叫 API（用到 trading/data）時。
alpaca_client = AlpacaClient()
