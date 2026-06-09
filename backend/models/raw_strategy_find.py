"""
原始策略素材資料模型（Phase 10 step-04）
==========================================
市場蒐集員定時從網路（RSS / 部落格）收回來的「策略描述文字」原料，先落這張表，
當作人 / strategy-builder skill 把它寫成可跑策略的素材。

職責很窄：**這張表只存「收回來的原始文字」，不存任何回測結果、不代表任何策略已上線。**
收回來的點子一律走既有引擎證明自己：
  人 / strategy-builder 寫成 strategies/<name>.py → 過 OOS 閘（optimizer / validation）
  → 達標才進候選（step-02 機會清單）→ step-06 人工核准才上真錢。

跟既有表的差別：
- Opportunity（step-02）：已通過回測、有 OOS EV 的「候選清單」。
- RawStrategyFind（本表）：還沒驗證、純文字的「靈感收件匣」，等人去消化。

status 流轉（人工驅動，爬蟲只負責產生 new）：
- new       ：剛爬回來、還沒看過。
- triaged   ：人看過、覺得值得試（待寫成策略）。
- built     ：已被寫成 strategies/<name>.py（接著要去過 OOS 閘）。
- discarded ：看過覺得沒用、丟棄（保留紀錄避免下次又重收同一篇）。
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime

from backend.database import Base


class RawStrategyFind(Base):
    __tablename__ = "raw_strategy_finds"

    id = Column(Integer, primary_key=True, index=True)

    # 來源標籤（例如 RSS feed 的網域 / 名稱），方便分組看「哪個來源收得多」
    source = Column(String, nullable=False, default="")

    # 原文網址：同一篇文章只收一次的去重鍵（爬蟲 upsert 時以此判斷是否已存在）
    source_url = Column(String, nullable=False, index=True)

    # 文章標題
    title = Column(String, nullable=False, default="")

    # 摘要 / 內文節錄（純文字，給人快速判斷值不值得展開）
    summary = Column(Text, nullable=False, default="")

    # 抓回來的時間
    fetched_at = Column(DateTime, default=datetime.now)

    # 狀態流轉（見檔頭說明）
    status = Column(String, nullable=False, default="new", index=True)

    def __repr__(self) -> str:
        return f"<RawStrategyFind {self.source} {self.title!r} {self.status}>"
