"""
組合層帳戶狀態資料模型（Phase 6 step-09）
==========================================
給「組合回撤熔斷」用的一張極簡單例表：只存「帳戶總權益的歷史峰值」。

為什麼要持久化峰值？
- 熔斷判斷 = 總權益從「峰值」回落超過門檻。峰值若只放記憶體，後端一重啟就歸零，
  熔斷會失效（剛重啟時 now==peak，永遠不觸發）。存資料庫後，重啟仍記得最高水位。
- 這張表設計成「單列」（id 固定為 1），每輪用 get_account().portfolio_value 更新峰值。
"""

from datetime import datetime

from sqlalchemy import Column, Integer, Float, DateTime

from backend.database import Base


class PortfolioState(Base):
    __tablename__ = "portfolio_state"

    # 固定單列：永遠用 id=1 這一筆（見 circuit_breaker 服務的讀寫）
    id = Column(Integer, primary_key=True, index=True)

    # 帳戶總權益（portfolio_value）的歷史峰值
    equity_peak = Column(Float, nullable=True)

    # 最後一次更新時間
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self) -> str:
        return f"<PortfolioState peak={self.equity_peak}>"
