"""
總經資料層單元測試（Phase 11 step-01）
======================================
重點驗「point-in-time 不偷看未來」與「沒 FRED key 優雅降級」。
完全不連網：用 monkeypatch 假造 fred_client 的回傳；用記憶體 SQLite 當快取。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_macro.py -q
"""

import sys
from datetime import date
from pathlib import Path

# Windows 主控台 cp950 印 emoji/中文會崩潰，強制改 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import MacroObservation  # noqa: F401（讓 Base 認得這張表）
from backend.services import macro_data, fred_client


@pytest.fixture
def db():
    """記憶體 SQLite session，建好所有表（含 macro_observations），測完即丟。"""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()


def _fake_obs(rows):
    """產生一個假的 fred_client.get_observations（忽略參數、固定回 rows）。"""
    return lambda sid, start=None, end=None: rows


def test_refresh_sets_released_at_with_publication_lag(db, monkeypatch):
    """非農 PAYEMS 落差 35 天：released_at 應 = period_date + 35d。"""
    monkeypatch.setattr(
        fred_client, "get_observations", _fake_obs([{"date": "2024-05-01", "value": 272.0}])
    )
    n = macro_data.refresh_series(db, "PAYEMS")
    assert n == 1
    obs = db.query(MacroObservation).one()
    assert obs.period_date == date(2024, 5, 1)
    assert obs.released_at == date(2024, 6, 5)  # 5/1 + 35d
    assert obs.value == 272.0


def test_point_in_time_hides_unreleased(db, monkeypatch):
    """★核心：as_of 在公布日之前 → 看不到該筆；在公布日（含）之後 → 看得到。"""
    monkeypatch.setattr(
        fred_client, "get_observations", _fake_obs([{"date": "2024-05-01", "value": 272.0}])
    )
    macro_data.refresh_series(db, "PAYEMS")  # released_at = 2024-06-05

    # 公布前一天：回測不該看到（防偷看未來）
    before = macro_data.get_macro_series(db, "PAYEMS", as_of=date(2024, 6, 4))
    assert len(before) == 0

    # 公布當天/之後：看得到
    after = macro_data.get_macro_series(db, "PAYEMS", as_of=date(2024, 6, 5))
    assert len(after) == 1
    assert after.iloc[0]["value"] == 272.0


def test_no_as_of_returns_all(db, monkeypatch):
    """不帶 as_of → 回全部（研究/報表視角，非回測）。"""
    monkeypatch.setattr(
        fred_client,
        "get_observations",
        _fake_obs(
            [
                {"date": "2024-04-01", "value": 270.0},
                {"date": "2024-05-01", "value": 272.0},
            ]
        ),
    )
    macro_data.refresh_series(db, "PAYEMS")
    allrows = macro_data.get_macro_series(db, "PAYEMS")
    assert len(allrows) == 2


def test_refresh_is_idempotent_upsert(db, monkeypatch):
    """重抓同期間 → 更新值、不重複堆積（唯一鍵 series+period）。"""
    monkeypatch.setattr(
        fred_client, "get_observations", _fake_obs([{"date": "2024-05-01", "value": 272.0}])
    )
    macro_data.refresh_series(db, "PAYEMS")
    # 第二次回傳同期間但修正值
    monkeypatch.setattr(
        fred_client, "get_observations", _fake_obs([{"date": "2024-05-01", "value": 275.0}])
    )
    macro_data.refresh_series(db, "PAYEMS")
    rows = db.query(MacroObservation).all()
    assert len(rows) == 1
    assert rows[0].value == 275.0


def test_graceful_when_no_key(db, monkeypatch):
    """沒 FRED key（get_observations 回 None）→ refresh 回 0、不崩。"""
    monkeypatch.setattr(fred_client, "get_observations", _fake_obs(None))
    assert macro_data.refresh_series(db, "PAYEMS") == 0
    assert len(macro_data.get_macro_series(db, "PAYEMS")) == 0


def test_publication_lag_fallback_for_unknown_series(db, monkeypatch):
    """未知序列用 settings.MACRO_DEFAULT_LAG_DAYS 當落差（預設 35）。"""
    from backend.config import settings

    monkeypatch.setattr(settings, "MACRO_DEFAULT_LAG_DAYS", 10)
    assert macro_data.publication_lag_days("SOME_UNKNOWN_ID") == 10
    # 已知序列不受影響
    assert macro_data.publication_lag_days("DGS10") == 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
