"""策略×標的適配註冊表（bot 汰弱審查員，Phase 13）

回答一個問題：「哪檔股票適合哪個策略？」

自動部署讓每個驗證過的策略部署到全部標的（N 檔各一個 paper Bot），Bot 數會持續長。
審查員每日把每支 paper Bot 的實跑績效，按「(策略, 標的)」聚合成一筆 fit 紀錄
（有則更新、無則新增 → upsert），日積月累成一張「策略配標的」的排行/記憶。

每筆 = 某個策略在某檔標的上的實跑成績（最近一次審查的快照）。
- verdict：good（夠多筆 + 勝率達標 + 報酬為正）/ poor（夠多筆但不及格）/ insufficient（樣本不足）。
- 這張表是給人看的報表 + 未來回饋迴路的依據（可選：部署前跳過已知 poor 的組合），
  **本身不下單、不直接動 Bot**——汰弱動作在 services/bot_review.py 做、落 DecisionLog 審計。
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, UniqueConstraint

from backend.database import Base


class StrategySymbolFit(Base):
    __tablename__ = "strategy_symbol_fits"

    # (策略, 標的) 唯一：審查員用它判斷 upsert（同組合只留一筆最新快照）
    __table_args__ = (
        UniqueConstraint("strategy_key", "symbol", name="uq_strategy_symbol"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # 策略代號（對 Bot.strategy，例 "ma_crossover"）
    strategy_key = Column(String, nullable=False, index=True)

    # 標的（股票代號，例 "AAPL"）
    symbol = Column(String, nullable=False, index=True)

    # ----- 最近一次審查算出的實跑績效（performance.compute_bot_stats）-----
    num_round_trips = Column(Integer, nullable=False, default=0)   # 累計完整買賣次數
    win_rate_pct = Column(Float, nullable=False, default=0.0)      # 勝率(%)
    return_pct = Column(Float, nullable=False, default=0.0)        # 已實現報酬率(%)
    max_drawdown_pct = Column(Float, nullable=False, default=0.0)  # 最大回撤(%)

    # 評等：good / poor / insufficient（門檻走 settings.BOT_REVIEW_*）
    verdict = Column(String, nullable=False, default="insufficient")

    # 最近一次據以更新的 Bot id（可回溯是哪支 Bot 的成績；同組合可能有多支 Bot）
    sample_bot_id = Column(Integer, nullable=True)

    # 最後更新時間（審查員每輪覆寫）
    updated_at = Column(DateTime, nullable=False, default=datetime.now)

    def __repr__(self) -> str:
        return (f"<StrategySymbolFit {self.strategy_key} on {self.symbol} "
                f"{self.verdict} ret={self.return_pct}%>")
