"""
決策審計軌跡資料模型（Phase 6 step-08）
========================================
每一次 Bot 檢查都留下「為何在這個時點買 / 賣 / 不動」的持久紀錄。

跟 TradeLog 的差別：
- TradeLog 只在「真的成交」時才寫。
- DecisionLog 連「沒成交但有決策」的時點都寫——觀望、續抱、休市跳過、購買力不足、熔斷。
自動跑真錢的系統必須能事後查驗每個決定（「昨天 10:35 為什麼沒進場？」），
這份紀錄也是日後餵 LLM 做檢討的素材。
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime

from backend.database import Base


# action 列舉值（用常數避免打錯字；存進 DB 仍是字串）。
# 涵蓋「有成交」與「沒成交但有決策」兩類時點。
ACTION_BOUGHT = "bought"                              # 進場買進
ACTION_SOLD = "sold"                                  # 出場賣出（風控或策略）
ACTION_HOLD = "hold"                                  # 續抱 / 空手觀望（沒動作）
ACTION_SKIPPED_MARKET_CLOSED = "skipped_market_closed"      # 休市跳過
ACTION_SKIPPED_NO_BUYING_POWER = "skipped_no_buying_power"  # 購買力不足跳過（step-05）
ACTION_SKIPPED_CIRCUIT_BREAKER = "skipped_circuit_breaker"  # 組合回撤熔斷跳過（step-09）
ACTION_DEMOTED = "demoted"                            # tracking error 自動降級停 Bot（維運安全軌 H3）


class DecisionLog(Base):
    __tablename__ = "decision_logs"

    id = Column(Integer, primary_key=True, index=True)

    # 是哪一個 Bot 的決策（對應 bots.id）
    bot_id = Column(Integer, index=True)

    # 股票代號
    symbol = Column(String, nullable=False)

    # 策略 / 風控當下的訊號："buy" / "sell" / "hold"
    signal = Column(String, nullable=False)

    # 決策原因（策略訊號說明 / 風控觸發原因 / 跳過原因），例如「黃金交叉」「觸發止損」「休市」
    reason = Column(String)

    # 決策當下的參考價（最新成交價；查不到時為 None）
    price = Column(Float, nullable=True)

    # 實際採取的動作（見上方 ACTION_* 常數）
    action = Column(String, nullable=False)

    # 決策時間
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self) -> str:
        return f"<DecisionLog {self.id} bot={self.bot_id} {self.action} {self.signal} {self.symbol}>"
