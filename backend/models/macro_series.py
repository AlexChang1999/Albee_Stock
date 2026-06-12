"""總經 / 環境資料快取模型（Phase 11 step-01）

把 FRED 抓回來的經濟數據（非農、失業率、聯邦基金利率、CPI、公債殖利率、VIX…）落成本機快取，
回測 / 特徵工程都從這裡讀，不必每次打外部 API。

★ point-in-time 鐵則（「回測=實盤」的延伸，本檔存在的理由）：
  經濟數據公布有遞延——某月的數據往往隔月才公布。所以每筆同時存：
    - period_date：資料「所屬期間」（例：2024-05-01 = 2024 年 5 月那筆）
    - released_at：市場「實際知道」這筆的日期 = period_date + 發布落差
  回測在某日只能看到 released_at <= 該日 的值，**嚴禁用 period_date 偷看尚未公布的未來數據**。
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, Date, DateTime, UniqueConstraint

from backend.database import Base


class MacroObservation(Base):
    __tablename__ = "macro_observations"

    id = Column(Integer, primary_key=True, index=True)

    # FRED 序列代號（PAYEMS 非農 / UNRATE 失業率 / FEDFUNDS 聯邦基金利率 / CPIAUCSL CPI / DGS10 ...）
    series_id = Column(String, nullable=False, index=True)

    # 資料所屬期間（月頻數據通常是月初日）
    period_date = Column(Date, nullable=False, index=True)

    # 市場實際「知道」這筆的日期 = period_date + 發布落差。回測對齊一律用這個（防偷看未來）。
    released_at = Column(Date, nullable=False, index=True)

    value = Column(Float, nullable=False)

    # 來源（目前只有 fred；保留欄位讓未來換 / 加資料源）
    source = Column(String, nullable=False, default="fred")

    # 這筆何時抓回來寫進快取（除錯 / 稽核用）
    fetched_at = Column(DateTime, nullable=False, default=datetime.now)

    # 同一序列同一期間只留一筆（重抓更新值，不重複堆積）
    __table_args__ = (
        UniqueConstraint("series_id", "period_date", name="uq_macro_obs_series_period"),
    )

    def __repr__(self) -> str:
        return (
            f"<MacroObservation {self.series_id} {self.period_date}"
            f"={self.value} (rel {self.released_at})>"
        )
