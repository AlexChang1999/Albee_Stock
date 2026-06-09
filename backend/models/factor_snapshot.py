"""因子數值表資料模型（Phase 10 step-03）

把市場狀態因子（regime_features 的 7 個因子 + 當下 regime 標籤）落成可查、可匯出的
數值快照。**因子是觀測佐證、給人和回測看的報表，不是新的交易訊號**——不讓它自動下單。

每筆 = 某檔股票在某個時點（as_of，截至最後一根 K 線）算出的一組因子。
由常駐掃描（opportunity_scan）每輪順手寫入；保留天數由 settings.FACTOR_RETENTION_DAYS 控制。
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime

from backend.database import Base


class FactorSnapshot(Base):
    __tablename__ = "factor_snapshots"

    id = Column(Integer, primary_key=True, index=True)

    # 股票代號（同一檔每次掃描各落一筆，保留歷史趨勢）
    symbol = Column(String, nullable=False, index=True)

    # 觀測時點：因子「截至最後一根 K 線」的時間（無 look-ahead，只用到此刻為止的資料）
    as_of = Column(DateTime, nullable=False, default=datetime.now, index=True)

    # ----- regime_features.compute_features 的 7 個因子（缺值為 None）-----
    volume_ratio = Column(Float, nullable=True)      # 最新量 ÷ 近 20 日均量
    return_5d = Column(Float, nullable=True)         # 近 5 日報酬率
    return_20d = Column(Float, nullable=True)        # 近 20 日報酬率
    volatility_20d = Column(Float, nullable=True)    # 近 20 日日報酬標準差（年化）
    trend_strength = Column(Float, nullable=True)    # ADX 最新值（趨勢強度，不分方向）
    atr_pct = Column(Float, nullable=True)           # ATR ÷ 價格（波動幅度）
    range_position = Column(Float, nullable=True)    # 收盤在近 20 日高低區間的位置（0~1）

    # regime.classify_regime 的標籤（trending/ranging/high_volume_stall/high_volatility/unknown）
    regime = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<FactorSnapshot {self.symbol} {self.regime} @ {self.as_of}>"
