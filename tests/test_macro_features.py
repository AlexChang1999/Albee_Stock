"""
環境特徵單元測試（Phase 11 step-03）
====================================
完全不連網：用記憶體 SQLite 當快取、直接塞 MacroObservation 列控制 released_at。
重點驗：
- point-in-time：某序列值只在其 released_at 之後的 bar 才出現（公布前為 NaN，非當期值）。
- 無未來函數：df.iloc[:i+1] 與完整 df 在第 i 根算出同值。
- 數值正確：yield_curve = DGS10 − DGS2、fed_funds_3m_chg = 最新 − 回看 3 期。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_macro_features.py -q
"""

import sys
from datetime import date, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import MacroObservation  # noqa: F401（讓 Base 認得這張表）
from backend.services import macro_data
from backend.services.macro_features import _as_of_value, attach_macro_features


@pytest.fixture
def db():
    """記憶體 SQLite session，建好所有表，測完即丟。"""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()


def _add(db, series_id, period, released, value):
    db.add(
        MacroObservation(
            series_id=series_id,
            period_date=period,
            released_at=released,
            value=value,
            source="test",
        )
    )


def _price_df(dates):
    return pd.DataFrame({"timestamp": pd.to_datetime(dates), "close": [1.0] * len(dates)})


# ---------- _as_of_value 直接測（核心防洩漏邏輯）----------
def test_as_of_value_point_in_time(db):
    """released_at 之前回 None；之後回值；periods_back 往回數可見序列。"""
    _add(db, "FEDFUNDS", date(2024, 4, 1), date(2024, 5, 1), 5.0)
    _add(db, "FEDFUNDS", date(2024, 5, 1), date(2024, 6, 1), 5.5)
    db.commit()
    s = macro_data.get_macro_series(db, "FEDFUNDS")

    assert _as_of_value(s, date(2024, 4, 30), 0) is None        # 第一筆都還沒公布
    assert _as_of_value(s, date(2024, 5, 1), 0) == 5.0          # 公布當日看得到
    assert _as_of_value(s, date(2024, 6, 1), 0) == 5.5          # 最新可見
    assert _as_of_value(s, date(2024, 6, 1), 1) == 5.0          # 回看 1 期


def test_macro_feature_hidden_until_released(db):
    """FEDFUNDS 公布前該 bar 的 fed_funds_level 為 NaN，公布當日(含)後為當期值。"""
    _add(db, "FEDFUNDS", date(2024, 5, 1), date(2024, 6, 5), 5.25)
    db.commit()
    out = attach_macro_features(_price_df(["2024-06-04", "2024-06-05"]), db)
    assert pd.isna(out["fed_funds_level"].iloc[0])             # 公布前一天 → NaN
    assert out["fed_funds_level"].iloc[1] == 5.25             # 公布當天 → 看得到


def test_yield_curve_numeric(db):
    """yield_curve = DGS10 − DGS2（都已公布）。"""
    _add(db, "DGS10", date(2024, 6, 3), date(2024, 6, 4), 4.2)
    _add(db, "DGS2", date(2024, 6, 3), date(2024, 6, 4), 4.5)
    db.commit()
    out = attach_macro_features(_price_df(["2024-06-05"]), db)
    assert out["yield_curve"].iloc[0] == pytest.approx(-0.3)


def test_fed_funds_3m_change(db):
    """fed_funds_3m_chg = 最新可見值 − 回看 3 期（4 個月頻點都已公布）。"""
    for i, val in enumerate([5.0, 5.1, 5.2, 5.5]):
        period = date(2024, 2 + i, 1)
        _add(db, "FEDFUNDS", period, period + timedelta(days=35), val)
    db.commit()
    out = attach_macro_features(_price_df(["2024-07-01"]), db)
    assert out["fed_funds_3m_chg"].iloc[0] == pytest.approx(0.5)   # 5.5 − 5.0
    assert out["fed_funds_level"].iloc[0] == pytest.approx(5.5)


def test_no_look_ahead(db):
    """df.iloc[:i+1] 與完整 df 在第 i 根算出同特徵（macro 特徵逐 bar 獨立）。"""
    _add(db, "VIXCLS", date(2024, 6, 1), date(2024, 6, 2), 18.0)
    _add(db, "VIXCLS", date(2024, 6, 5), date(2024, 6, 6), 25.0)
    db.commit()
    dates = ["2024-06-03", "2024-06-04", "2024-06-07"]
    full = attach_macro_features(_price_df(dates), db)
    for i in range(len(dates)):
        partial = attach_macro_features(_price_df(dates[: i + 1]), db)
        a, b = partial["vix_level"].iloc[i], full["vix_level"].iloc[i]
        assert (pd.isna(a) and pd.isna(b)) or a == b, i


def test_graceful_when_no_macro_data(db):
    """完全沒有總經資料 → 各特徵欄為 NaN，不崩（優雅降級）。"""
    out = attach_macro_features(_price_df(["2024-06-05"]), db)
    for col in ["fed_funds_level", "cpi_yoy", "yield_curve", "vix_level"]:
        assert pd.isna(out[col].iloc[0]), col


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
