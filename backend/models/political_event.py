"""
政治事件資料模型（Phase 10 step-05）
======================================
政治專討員從 Discord 頻道偵測到的貼文（例如川普發文鏡像），經本機 Ollama 判讀後
落這張表：內容摘要 + 多空/風險分數 + 發文時間 + 頻率特徵。

★ 定位（最重要、最易被誤用）：**這是「煞車」資料，不是「油門」。**
  分數只接既有 `event_risk.assess_event_risk`（重大負面 → 不開新倉 / 縮部位），
  **絕不**據此猜方向、加碼重壓。「貼文 → 漲跌」最易過擬合、無乾淨 point-in-time
  對齊資料可誠實回測（與 event_risk 被標 non-verifiable 一致）。

頻率特徵（posts_last_24h / posts_last_1h）只當「觀測佐證」記錄下來，
**不**因為高頻發文就放大部位（factor 上限 1.0）。

label / score 沿用既有情緒格式（screener.parse_sentiment）：
  label ∈ {bullish, bearish, neutral}；score ∈ [-100, 100]，方便直接餵進既有風險閘。
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, Text, DateTime

from backend.database import Base


class PoliticalEvent(Base):
    __tablename__ = "political_events"

    id = Column(Integer, primary_key=True, index=True)

    # 來源（例如 "discord:#trump-mirror"）與作者（鏡像的原始發文者）
    source = Column(String, nullable=False, default="")
    author = Column(String, nullable=False, default="")

    # 貼文內容摘要（純文字、截斷；不存整篇，避免 DB 膨脹）
    content_summary = Column(Text, nullable=False, default="")

    # LLM 判讀（與 screener.parse_sentiment 同格式，方便餵 event_risk）
    label = Column(String, nullable=False, default="neutral")
    score = Column(Float, nullable=False, default=0.0)
    reason = Column(Text, nullable=False, default="")

    # 發文時間（來自 Discord 訊息時間戳）與我們處理的時間
    posted_at = Column(DateTime, default=datetime.now, index=True)
    fetched_at = Column(DateTime, default=datetime.now)

    # 頻率特徵（觀測佐證，不放大部位）：此貼文前 24h / 1h 內的發文數
    posts_last_24h = Column(Integer, nullable=True)
    posts_last_1h = Column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<PoliticalEvent {self.author} {self.label} {self.score} @{self.posted_at}>"
