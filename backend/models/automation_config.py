"""
模式 B 自動部署規則資料模型（redesign Phase 4 後續：規則改吃 DB）
================================================================
原本「自動部署規則」（AUTO_DEPLOY_*）只能寫死在 .env、唯讀、改了要重啟後端。
這張表把那 6 個規則欄位搬進資料庫，讓前端可以即時編輯儲存、後端讀 DB 不讀 .env。

為什麼設計成「單列」（id 固定為 1）？
- 全系統只有「一份」自動部署規則，不需要多列；比照 portfolio_state 的單列持久化模式。
- 第一次建表時用 .env 的預設值「種」一筆（見 Alembic 遷移與 automation_config 服務的 load-or-seed）。

安全提醒：這裡的 enabled 是「自動駕駛總開關」，與「實盤雙閘」完全獨立——
開了 enabled 仍全程 Paper（模擬），不會碰到真錢。實盤要另外把 ALPACA_BASE_URL +
ALLOW_LIVE_TRADING 雙閘都打開才行，本表完全不碰那道安全閥。
"""

from datetime import datetime

from sqlalchemy import Column, Integer, Float, Boolean, DateTime

from backend.database import Base


class AutomationConfig(Base):
    __tablename__ = "automation_config"

    # 固定單列：永遠用 id=1 這一筆（見 automation_config 服務的 get_config）
    id = Column(Integer, primary_key=True, index=True)

    # 自動駕駛總開關（與實盤雙閘獨立；開了仍是 Paper）
    enabled = Column(Boolean, nullable=False, default=False)

    # 雙重門檻：EV 看絕對期望值、勝率看百分比（兩個都要過才自動部署）
    ev_threshold = Column(Float, nullable=False, default=150.0)
    winrate_threshold = Column(Float, nullable=False, default=55.0)  # 存「百分比」（55 = 55%）

    # 最多同時自動建幾個 Bot（防一次梭哈）；每個 Bot 配多少資金
    max_bots = Column(Integer, nullable=False, default=5)
    cash_per_bot = Column(Float, nullable=False, default=1000.0)

    # 盤前掃描的本機時刻（24 小時制的「時」，0~23）
    scan_hour = Column(Integer, nullable=False, default=8)

    # 最後一次更新時間
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self) -> str:
        return f"<AutomationConfig enabled={self.enabled} ev={self.ev_threshold} scan_hour={self.scan_hour}>"
