"""
策略方案資料模型（StrategyPreset）── Phase 5
================================================
「策略方案」是一份可命名、可單獨回測/收藏/比較的策略設定，獨立於 Bot 存在。

跟 Bot 的差別：
- Bot 是「實際在跑」的交易機器人（會盯盤、會下單）。
- StrategyPreset 只是「一組策略 + 參數 + 標的」的草稿，用來在工作台裡反覆
  回測、調參、比 EV。覺得好用了，再一鍵轉成 Bot 實跑。

每個方案 = 資料庫裡的一筆紀錄。
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text

from backend.database import Base


class StrategyPreset(Base):
    __tablename__ = "strategy_presets"

    id = Column(Integer, primary_key=True, index=True)

    # 方案名稱（可改名），例如 "AAPL RSI 保守版"
    name = Column(String, nullable=False)

    # 用哪個策略，對應 STRATEGY_REGISTRY 的代號，例如 "rsi"、"williams_r"
    strategy_key = Column(String, nullable=False)

    # 策略參數（JSON），不同策略需要的參數不同
    params = Column(JSON, default=dict)

    # 交易標的（股票代號），例如 "AAPL"
    symbol = Column(String, nullable=False)

    # 是否收藏（好策略加星）
    is_favorite = Column(Boolean, default=False)

    # 備註（自由文字），記這方案的想法/出處
    notes = Column(Text, nullable=True)

    # 建立時間
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self) -> str:
        return f"<StrategyPreset {self.id} {self.name} ({self.strategy_key} on {self.symbol})>"
