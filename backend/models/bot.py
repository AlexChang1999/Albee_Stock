"""
Bot 資料模型
============
一個 Bot = 一個獨立運行的交易策略設定。

例如：
- 「AAPL 均線交叉 Bot」：用均線交叉策略，盯著蘋果股票
- 「TSLA RSI Bot」：用 RSI 策略，盯著特斯拉

每個 Bot 都是資料庫裡的一筆紀錄。
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON

from backend.database import Base


class Bot(Base):
    __tablename__ = "bots"  # 資料表名稱

    id = Column(Integer, primary_key=True, index=True)

    # Bot 的名稱，方便辨識，例如 "AAPL 均線交叉"
    name = Column(String, nullable=False)

    # 用哪一種策略，對應 strategies/ 裡的策略代號，例如 "ma_crossover"
    strategy = Column(String, nullable=False)

    # 交易標的（股票代號），例如 "AAPL"
    symbol = Column(String, nullable=False)

    # 策略參數，用 JSON 存（不同策略需要的參數不同）
    # 例如均線交叉：{"short_window": 5, "long_window": 20}
    params = Column(JSON, default=dict)

    # 每次下單金額（美元），新手先用固定金額控制風險
    trade_amount = Column(Float, default=1000.0)

    # Bot 是否啟用中
    is_active = Column(Boolean, default=False)

    # 建立時間
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self) -> str:
        return f"<Bot {self.id} {self.name} ({self.strategy} on {self.symbol})>"
