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

    # ----- 風控（Phase 4 監聽系統用）-----
    # 以下三個百分比皆「可不填」(None)；填了才啟用該機制。
    # 用小數表示，例如 0.10 = 10%。

    # 固定止盈：現價漲到「進場價 ×(1+此值)」就全部賣出。例：0.10 = +10% 出場
    take_profit_pct = Column(Float, nullable=True)

    # 固定止損：現價跌到「進場價 ×(1−此值)」就全部賣出。例：0.05 = −5% 出場
    stop_loss_pct = Column(Float, nullable=True)

    # 追蹤止損：從「持倉期間最高價」回落此比例就賣出。例：0.03 = 回落 3% 出場
    # 跟固定止損的差別：止損點會隨價格創新高而往上抬，鎖住已賺到的獲利
    trailing_stop_pct = Column(Float, nullable=True)

    # 監測頻率（秒）：啟動後每隔幾秒檢查一次行情。預設 60 秒
    check_interval_sec = Column(Integer, default=60)

    # Bot 是否啟用中
    is_active = Column(Boolean, default=False)

    # 建立時間
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self) -> str:
        return f"<Bot {self.id} {self.name} ({self.strategy} on {self.symbol})>"
