"""
策略知識庫資料模型（StrategyKnowledge）── Phase 8 step-01
========================================================
給「一個策略 + 它的理論 / 場景 / 使用時機 / 驗證狀態」一個持久的家。
這是「可成長策略庫」的容器，也是後續組合（step-03）、驗證（step-04）、
排序（step-05）、人在迴路審核（step-06）共用的單一資料來源。

跟既有兩張表的分工：
- StrategyPreset：使用者手調、隨時回測的「草稿方案」。
- BacktestRun  ：每跑一次回測留一筆歷史（給思考助手當記憶）。
- StrategyKnowledge（本檔）：經「自動驗證管線」篩選、帶驗證狀態與使用時機說明的
  「策展候選 / 已策展」策略；狀態機 candidate → validated → curated / rejected。

驗證狀態機（status）：
  candidate ──(step-04 驗證 OOS 加分)──► validated ──(step-06 人工晉升)──► curated
      │                                      │
      └──────────────(任何時點人工/自動退回)─┴──────────────► rejected
人在迴路鐵則：validated → curated 這一步只能由人觸發（step-06）。
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, JSON, Text

from backend.database import Base


class StrategyKnowledge(Base):
    __tablename__ = "strategy_knowledge"

    id = Column(Integer, primary_key=True, index=True)

    # 顯示名稱，例如 "RSI 反轉（震盪盤）"
    name = Column(String, nullable=False)

    # 理論來源 / 場景 / 使用時機說明（人類可讀，供策展與檢索）
    theory = Column(Text, nullable=True)      # 理論來源（出自哪套理論 / 文獻 / 經驗）
    scenario = Column(Text, nullable=True)    # 適用場景（什麼市況下用）
    usage_note = Column(Text, nullable=True)  # 使用時機說明（step-05 由狀態親和性 + LLM 生成）

    # 對應 STRATEGY_REGISTRY 的策略代號；組合策略則為 "composite"
    strategy_key = Column(String, nullable=False)
    # 策略參數（JSON）；組合策略時放 members / method 等設定
    params = Column(JSON, default=dict)
    # 若是組合策略，記其子策略清單（JSON）；非組合則為 None
    composite_of = Column(JSON, nullable=True)

    # 驗證狀態機：candidate / validated / curated / rejected
    status = Column(String, nullable=False, default="candidate", index=True)

    # 樣本外（OOS）驗證指標（step-04 寫入）；未驗證為 None
    oos_metrics = Column(JSON, nullable=True)
    # 狀態親和性（連 Phase 7：這策略在哪種市場狀態 OOS 最好）；未算為 None
    regime_affinity = Column(JSON, nullable=True)

    # 自動部署冪等戳記（curated→Paper Bot 自動部署排程用）：None = 還沒部署過。
    # 自動 / 手動部署成功後戳上時間，避免排程重複對同一筆知識建 Bot。
    deployed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self) -> str:
        return f"<StrategyKnowledge {self.id} {self.name} ({self.strategy_key}/{self.status})>"
