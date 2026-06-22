"""
因子數值表測試（Phase 10 step-03）
====================================
涵蓋：
1. 純函式 features_to_snapshot_row：7 因子鍵映射 + symbol/as_of/regime，缺值帶 None。
2. collect_factor_snapshots：對 watchlist 各檔抓 K 線→算因子→落表；落表值＝直接算的值
   （無偷看、不重算第二套）；保留天數修剪過舊快照。
3. GET /factors：依 as_of 由新到舊 + symbol 篩選 + limit。
4. GET /factors/export.csv：表頭欄位順序固定、內容正確。

不連網：臨時 SQLite + monkeypatch market_data.get_bars（給合成 K 線）。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_factor_snapshot.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import csv
import io
from contextlib import contextmanager
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.database import Base, get_db
from backend.models import FactorSnapshot
from backend.services import opportunity_scan, regime_features
from backend.services.opportunity_scan import (
    features_to_snapshot_row,
    collect_factor_snapshots,
)


def _session(tmp_path, name="fac.db"):
    engine = create_engine(f"sqlite:///{tmp_path / name}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _synth_df(n=40, base=100.0):
    """造一段遞增 OHLCV 日線（欄位小寫），足夠算出所有因子。"""
    rows = []
    for i in range(n):
        c = base + i  # 緩升
        rows.append({
            "open": c - 0.5,
            "high": c + 1.0,
            "low": c - 1.0,
            "close": c,
            "volume": 1000 + i * 10,
        })
    return pd.DataFrame(rows)


# ---------- 1. features_to_snapshot_row（純函式） ----------
def test_row_maps_all_keys_and_fills_none():
    as_of = datetime(2026, 6, 8, 12, 0, 0)
    features = {
        "volume_ratio": 3.0,
        "return_5d": 0.02,
        "return_20d": 0.1,
        "volatility_20d": 0.3,
        "trend_strength": 25.0,
        "atr_pct": 0.05,
        # range_position 故意缺 → 應帶 None
    }
    row = features_to_snapshot_row("aapl", features, "trending", as_of)
    assert row["symbol"] == "aapl"
    assert row["as_of"] == as_of
    assert row["regime"] == "trending"
    assert row["volume_ratio"] == 3.0
    assert row["range_position"] is None  # 缺值帶 None
    # 7 因子鍵 + symbol/as_of/regime 都在
    for k in ("volume_ratio", "return_5d", "return_20d", "volatility_20d",
              "trend_strength", "atr_pct", "range_position"):
        assert k in row


# ---------- 2. collect_factor_snapshots（落表值＝直接算的值 + 修剪） ----------
def test_collect_writes_one_per_symbol_and_matches_compute(tmp_path, monkeypatch):
    db = _session(tmp_path)
    df = _synth_df()

    monkeypatch.setattr(opportunity_scan.settings, "SCREENER_WATCHLIST", "AAPL,TSLA")
    monkeypatch.setattr(opportunity_scan.settings, "FACTOR_RETENTION_DAYS", 90)
    # collect_factor_snapshots 改批次抓（1 次 HTTP）→ 換掉批次版假函式
    monkeypatch.setattr(
        opportunity_scan.market_data, "get_bars_multi",
        lambda syms, days=60, source="alpaca": {s: df for s in syms},
    )

    as_of = datetime(2026, 6, 8, 12, 0, 0)
    written = collect_factor_snapshots(db, as_of=as_of)
    assert written == 2  # watchlist 兩檔各一筆
    assert db.query(FactorSnapshot).count() == 2

    # 落表值＝直接用 compute_features 算的值（沒重算第二套、沒偷看）
    expected = regime_features.compute_features(df)
    aapl = db.query(FactorSnapshot).filter_by(symbol="AAPL").first()
    assert aapl.as_of == as_of
    assert aapl.volume_ratio == expected["volume_ratio"]
    assert aapl.return_20d == expected["return_20d"]
    assert aapl.trend_strength == expected["trend_strength"]


def test_collect_prunes_old_snapshots(tmp_path, monkeypatch):
    db = _session(tmp_path)
    df = _synth_df()

    monkeypatch.setattr(opportunity_scan.settings, "SCREENER_WATCHLIST", "AAPL")
    monkeypatch.setattr(opportunity_scan.settings, "FACTOR_RETENTION_DAYS", 90)
    # collect_factor_snapshots 改批次抓（1 次 HTTP）→ 換掉批次版假函式
    monkeypatch.setattr(
        opportunity_scan.market_data, "get_bars_multi",
        lambda syms, days=60, source="alpaca": {s: df for s in syms},
    )

    now = datetime(2026, 6, 8, 12, 0, 0)
    # 種一筆 200 天前的舊快照
    db.add(FactorSnapshot(symbol="AAPL", as_of=now - timedelta(days=200), regime="ranging"))
    db.commit()
    assert db.query(FactorSnapshot).count() == 1

    collect_factor_snapshots(db, as_of=now)
    # 舊的（>90 天）被修剪，只留這輪新寫入的
    remaining = db.query(FactorSnapshot).all()
    assert len(remaining) == 1
    assert remaining[0].as_of == now


def test_collect_no_prune_when_retention_zero(tmp_path, monkeypatch):
    db = _session(tmp_path)
    df = _synth_df()
    monkeypatch.setattr(opportunity_scan.settings, "SCREENER_WATCHLIST", "AAPL")
    monkeypatch.setattr(opportunity_scan.settings, "FACTOR_RETENTION_DAYS", 0)  # 不修剪
    # collect_factor_snapshots 改批次抓（1 次 HTTP）→ 換掉批次版假函式
    monkeypatch.setattr(
        opportunity_scan.market_data, "get_bars_multi",
        lambda syms, days=60, source="alpaca": {s: df for s in syms},
    )

    now = datetime(2026, 6, 8, 12, 0, 0)
    db.add(FactorSnapshot(symbol="AAPL", as_of=now - timedelta(days=500), regime="ranging"))
    db.commit()
    collect_factor_snapshots(db, as_of=now)
    assert db.query(FactorSnapshot).count() == 2  # 舊的保留 + 新的


# ---------- 3 + 4. 端點往返 + CSV ----------
@contextmanager
def _isolated_client(tmp_path):
    from backend.main import app

    engine = create_engine(
        f"sqlite:///{tmp_path / 'app_fac.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    def _override():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    try:
        with TestClient(app) as client:
            yield client, TestingSession
    finally:
        app.dependency_overrides.pop(get_db, None)


def _seed(db):
    t0 = datetime(2026, 6, 1, 10, 0, 0)
    db.add_all([
        FactorSnapshot(symbol="AAPL", as_of=t0, volume_ratio=2.0, regime="ranging"),
        FactorSnapshot(symbol="AAPL", as_of=t0 + timedelta(days=1), volume_ratio=3.0, regime="trending"),
        FactorSnapshot(symbol="TSLA", as_of=t0 + timedelta(days=2), volume_ratio=4.0, regime="high_volatility"),
    ])
    db.commit()


def test_get_factors_sorted_filtered(tmp_path):
    with _isolated_client(tmp_path) as (client, TestingSession):
        db = TestingSession()
        try:
            _seed(db)
        finally:
            db.close()

        # 依 as_of 由新到舊
        rows = client.get("/factors").json()
        assert [r["symbol"] for r in rows] == ["TSLA", "AAPL", "AAPL"]

        # symbol 篩選（不分大小寫）
        aapl = client.get("/factors?symbol=aapl").json()
        assert len(aapl) == 2 and all(r["symbol"] == "AAPL" for r in aapl)

        # limit 夾取
        one = client.get("/factors?limit=1").json()
        assert len(one) == 1 and one[0]["symbol"] == "TSLA"


def test_export_csv_header_and_rows(tmp_path):
    with _isolated_client(tmp_path) as (client, TestingSession):
        db = TestingSession()
        try:
            _seed(db)
        finally:
            db.close()

        resp = client.get("/factors/export.csv?symbol=AAPL")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

        reader = list(csv.reader(io.StringIO(resp.text)))
        header = reader[0]
        assert header == [
            "symbol", "as_of", "volume_ratio", "return_5d", "return_20d",
            "volatility_20d", "trend_strength", "atr_pct", "range_position", "regime",
        ]
        # 兩筆 AAPL，由新到舊
        data_rows = reader[1:]
        assert len(data_rows) == 2
        assert all(r[0] == "AAPL" for r in data_rows)
        assert data_rows[0][9] == "trending"  # regime 欄
