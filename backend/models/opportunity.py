"""
機會清單資料模型（Phase 10 step-02）
======================================
常駐探勘把海選（screener）找到的「值得部署」候選**持久化**進這張表，
讓好策略在名額滿時也不被丟掉、關掉 app 也留著，下次開機接著看。

跟既有 BacktestRun 的差別：
- BacktestRun 記「某次回測的完整結果」（含資金曲線、檢討），是歷史明細。
- Opportunity 是「目前還值得關注的候選清單」——同 symbol+strategy 只留一筆（會被後續掃描
  更新而非重複堆積），是一份「現況排行」，給戰情頁 / 董事會核准頁取用。

誠實守則（Phase 6 step-04）：這裡存的 EV / 勝率一律是**樣本外（OOS）**，不存樣本內，
避免拿過擬合的漂亮數字當賣點。

status 流轉：
- new      ：這次掃描新發現的候選（尚未提醒過）。
- seen     ：已就「超過提醒門檻」發過一次通知（去抖，不重複洗頻）。
- deployed ：已被核准 / 部署成 Bot（保留給 step-06 人工核准用）。
- expired  ：已失效 / 下架（保留給後續清理用）。
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON

from backend.database import Base


class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, index=True)

    # 候選標的（股票代號）。同 symbol+strategy_key 視為「同一個機會」，掃描時更新不重複。
    symbol = Column(String, nullable=False, index=True)

    # 該標的本次海選挑出的最佳策略代號（對應 strategies/ 的 key）
    strategy_key = Column(String, nullable=False)

    # 該策略的最佳參數組合（JSON）
    params = Column(JSON, default=dict)

    # 樣本外（OOS）期望值與勝率——挑冠軍 / 設門檻一律看這兩個（防過擬合）
    oos_expected_value = Column(Float, nullable=True)
    oos_win_rate_pct = Column(Float, nullable=True)

    # OOS 期望值佔本金 %（維運安全軌 H3：tracking error 對帳的回測側基準。
    # 回測全進全出複利 vs Paper 固定 trade_amount，美元 EV 不可直接比，用 % 歸一化）
    oos_expectancy_pct = Column(Float, nullable=True)

    # 海選時順手帶上的新聞情緒（dict 或 None；只當次要排序加權，不當主訊號）
    sentiment = Column(JSON, nullable=True)

    # 最後一次被掃描更新的時間
    scanned_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 狀態流轉（見檔頭說明）
    status = Column(String, nullable=False, default="new", index=True)

    def __repr__(self) -> str:
        return f"<Opportunity {self.symbol} {self.strategy_key} ev={self.oos_expected_value} {self.status}>"
