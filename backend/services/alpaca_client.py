"""
Alpaca API 封裝
===============
把 Alpaca 的「交易」和「資料」功能包成好用的函式，
這樣策略和 Bot 不用直接面對 Alpaca SDK 的細節。

提供的功能：
- get_account()           取得帳戶資訊
- get_position(symbol)    查某檔股票目前持倉
- submit_market_order()   送出市價單（買/賣）
- get_bars()              取得歷史 K 線資料（給策略算指標）
- get_latest_price()      取得最新成交價
"""

from datetime import datetime, timedelta

import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame

from backend.config import settings


class AlpacaClient:
    """封裝 Alpaca 的交易與資料功能。"""

    def __init__(self) -> None:
        # 延遲初始化：這裡「不」立刻建立 Alpaca 的 client。
        # 原因：Alpaca SDK 在建立 client 時就會檢查金鑰，金鑰為空會直接丟
        # ValueError。若在這裡建立，沒有 .env 的環境（例如 CI 跑測試）光是
        # import 這個模組就會崩潰。改成第一次真正用到時才建立（見下方 property）。
        self._trading: TradingClient | None = None
        self._data: StockHistoricalDataClient | None = None

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

    # ---------- 下單 ----------
    def submit_market_order(self, symbol: str, qty: float, side: str):
        """
        送出市價單。
        :param symbol: 股票代號，例如 "AAPL"
        :param qty: 股數
        :param side: "buy" 或 "sell"
        :return: Alpaca 的訂單物件
        """
        order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL

        order_request = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=TimeInForce.DAY,  # 當日有效
        )
        return self.trading.submit_order(order_request)

    # ---------- 資料 ----------
    def get_latest_price(self, symbol: str) -> float:
        """
        取得某檔股票的「最新成交價」。
        用成交價(trade)而非買賣報價(quote)，因為休市時 bid/ask 常為 0，
        用成交價在盤中、盤後都比較可靠。
        """
        request = StockLatestTradeRequest(symbol_or_symbols=symbol)
        trade = self.data.get_stock_latest_trade(request)[symbol]
        return trade.price

    def get_bars(self, symbol: str, days: int = 60) -> pd.DataFrame:
        """
        取得最近 N 天的「日 K 線」資料，回傳 pandas DataFrame。
        策略會用這份資料來計算指標（例如均線）。

        :param symbol: 股票代號
        :param days: 往前抓幾天
        :return: 含 open/high/low/close/volume 欄位的 DataFrame
        """
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


# 建立一個全域共用的實例，其他檔案 import 後直接用。
# 因為改成延遲初始化，這行不會碰到金鑰，沒有 .env 也能安全 import；
# 真正的金鑰檢查/錯誤會發生在第一次呼叫 API（用到 trading/data）時。
alpaca_client = AlpacaClient()
