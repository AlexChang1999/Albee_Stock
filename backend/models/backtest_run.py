"""
回測紀錄資料模型（BacktestRun）── Phase 5
================================================
每跑一次 Python 回測就存一筆，當作「Claude 思考助手」的記憶來源：
Claude 之後可以讀這些歷史（含 EV 與事後檢討），越看越聰明。

注意：回測是 Python 做的（按鈕直接打 /presets/{id}/backtest），Claude 只負責「讀」
這些紀錄來思考，不負責跑回測。
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text

from backend.database import Base


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True, index=True)

    # 來自哪個策略方案（對應 strategy_presets.id）。
    # 可為 None：允許不綁方案、臨時跑一次也存得起來。
    preset_id = Column(Integer, index=True, nullable=True)

    # 這次回測用的策略代號 / 參數 / 標的（冗餘存一份，方案被改了也不影響歷史）
    strategy_key = Column(String, nullable=False)
    params = Column(JSON, default=dict)
    symbol = Column(String, nullable=False)

    # 回測區間（往前抓幾天）
    period_days = Column(Integer, nullable=True)

    # 完整績效指標（JSON），含 EV 全套（expected_value / profit_factor / ...）。
    # 直接存回測引擎回傳的 result，前端與 Claude 都讀這份。
    metrics = Column(JSON, default=dict)

    # 是否標記為「好策略」（收藏進榜）
    is_good = Column(Boolean, default=False)

    # Claude 的事後檢討（POST /chat/postmortem 寫入）。None = 還沒檢討過。
    claude_postmortem = Column(Text, nullable=True)

    # 建立時間
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self) -> str:
        return f"<BacktestRun {self.id} {self.strategy_key} on {self.symbol}>"
