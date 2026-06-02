"""
交易紀錄資料模型
================
每當 Bot 送出一筆交易（買或賣），就記一筆到這裡，方便事後檢視績效。
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime

from backend.database import Base


class TradeLog(Base):
    __tablename__ = "trade_logs"

    id = Column(Integer, primary_key=True, index=True)

    # 是哪一個 Bot 觸發的（對應 bots.id）
    bot_id = Column(Integer, index=True)

    # 股票代號
    symbol = Column(String, nullable=False)

    # 買還是賣："buy" / "sell"
    side = Column(String, nullable=False)

    # 數量（股數）
    qty = Column(Float, nullable=False)

    # 成交（或下單時）的價格
    price = Column(Float)

    # Alpaca 回傳的訂單 ID，方便對帳
    order_id = Column(String)

    # 觸發這筆交易的原因（策略訊號說明），例如 "短均線向上穿越長均線"
    reason = Column(String)

    # 交易時間
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self) -> str:
        return f"<TradeLog {self.id} {self.side} {self.qty} {self.symbol} @ {self.price}>"
