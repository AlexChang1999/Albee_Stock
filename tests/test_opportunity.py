"""
常駐機會探勘測試（Phase 10 step-02）
======================================
涵蓋：
1. 純函式 screener_results_to_rows：欄位映射 + 依 OOS EV 由高到低排序（None 最後）。
2. 純函式 upsert_opportunities：同 symbol+strategy 更新不重複（冪等）、保留既有 status。
3. run_opportunity_scan：盤中跑 → 寫表 + 新候選超門檻提醒一次後翻 seen（去抖）；收盤跳過不呼叫海選。
4. GET /opportunities：依 OOS EV 排序 + limit + status 篩選往返。

不連網：用臨時 SQLite + monkeypatch is_market_open / screen_watchlist / notify。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_opportunity.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastapi.testclient import TestClient

from backend.database import Base, get_db
from backend.models import Opportunity
from backend.services import opportunity_scan
from backend.services.opportunity_scan import (
    screener_results_to_rows,
    upsert_opportunities,
    run_opportunity_scan,
)


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'opp.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _rec(symbol, strategy, ev, win=60.0):
    """造一筆 screener recommendations 格式（metrics 內含 OOS 指標）。"""
    return {
        "symbol": symbol,
        "volume_ratio": 3.0,
        "sentiment": {"label": "bullish", "score": 40, "reason": ""},
        "strategy_key": strategy,
        "params": {"x": 1},
        "metrics": {"oos_expected_value": ev, "oos_win_rate_pct": win},
        "suggested_cash": 10000.0,
    }


# ---------- 1. screener_results_to_rows（純函式） ----------
def test_results_to_rows_maps_and_sorts():
    recs = [
        _rec("AAPL", "ma_crossover", 100.0),
        _rec("TSLA", "rsi", 300.0),
        {"symbol": "NONE", "strategy_key": "macd", "params": {}, "metrics": {}, "sentiment": None},
    ]
    rows = screener_results_to_rows(recs)
    # 依 OOS EV 由高到低，缺值（None）排最後
    assert [r["symbol"] for r in rows] == ["TSLA", "AAPL", "NONE"]
    top = rows[0]
    assert top["strategy_key"] == "rsi"
    assert top["oos_expected_value"] == 300.0
    assert top["oos_win_rate_pct"] == 60.0
    assert rows[-1]["oos_expected_value"] is None


def test_results_to_rows_empty():
    assert screener_results_to_rows([]) == []
    assert screener_results_to_rows(None) == []


# ---------- 2. upsert_opportunities（冪等 + 保留 status） ----------
def test_upsert_idempotent_and_preserves_status(tmp_path):
    db = _session(tmp_path)
    rows = [
        {"symbol": "AAPL", "strategy_key": "ma_crossover", "params": {}, "oos_expected_value": 100.0, "oos_win_rate_pct": 60.0, "sentiment": None},
        {"symbol": "TSLA", "strategy_key": "rsi", "params": {}, "oos_expected_value": 300.0, "oos_win_rate_pct": 55.0, "sentiment": None},
    ]
    r1 = upsert_opportunities(db, rows)
    assert r1 == {"inserted": 2, "updated": 0}
    assert db.query(Opportunity).count() == 2

    # 把 AAPL 標成 seen，再 upsert 同一批：不新增、走更新、status 保留 seen
    aapl = db.query(Opportunity).filter_by(symbol="AAPL").first()
    aapl.status = "seen"
    db.commit()

    # 更新後 EV 變動但 status 不被打回 new
    rows[0]["oos_expected_value"] = 150.0
    r2 = upsert_opportunities(db, rows)
    assert r2 == {"inserted": 0, "updated": 2}
    assert db.query(Opportunity).count() == 2  # 沒重複堆積
    aapl = db.query(Opportunity).filter_by(symbol="AAPL").first()
    assert aapl.status == "seen"           # 保留
    assert aapl.oos_expected_value == 150.0  # 指標有更新


def test_upsert_skips_incomplete_rows(tmp_path):
    db = _session(tmp_path)
    rows = [{"symbol": None, "strategy_key": "rsi"}, {"symbol": "AAPL", "strategy_key": None}]
    r = upsert_opportunities(db, rows)
    assert r == {"inserted": 0, "updated": 0}
    assert db.query(Opportunity).count() == 0


# ---------- 3. run_opportunity_scan（盤中閘 + 去抖提醒） ----------
def _patch_scan(monkeypatch, tmp_path, *, market_open, recs):
    """把 run_opportunity_scan 的外部相依換成臨時 SQLite + 假海選 + 攔截通知。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'scan.db'}")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    monkeypatch.setattr(opportunity_scan, "SessionLocal", TestingSession)
    monkeypatch.setattr(opportunity_scan.alpaca_client, "is_market_open", lambda: market_open)

    called = {"screen": 0}

    def _fake_screen(**kw):
        called["screen"] += 1
        return {"recommendations": recs}

    monkeypatch.setattr(opportunity_scan.screener, "screen_watchlist", _fake_screen)

    # step-03：run_opportunity_scan 會順手對 watchlist 各檔抓 K 線落因子表。
    # 這裡把 watchlist 縮成兩檔 + 餵假 K 線，讓掃描測試完全離線（不真的連網）。
    import pandas as pd
    monkeypatch.setattr(opportunity_scan.settings, "SCREENER_WATCHLIST", "AAPL,TSLA")
    _df = pd.DataFrame({
        "open": [100.0] * 30, "high": [101.0] * 30, "low": [99.0] * 30,
        "close": [100.0 + i for i in range(30)], "volume": [1000 + i for i in range(30)],
    })
    monkeypatch.setattr(opportunity_scan.market_data, "get_bars", lambda sym, days=60, source="alpaca": _df)

    notes = []
    monkeypatch.setattr(opportunity_scan.notifier, "notify", lambda msg: notes.append(msg))
    return TestingSession, called, notes


def test_scan_writes_and_notifies_new_above_threshold(monkeypatch, tmp_path):
    # 預設門檻 ev_threshold=150（settings.AUTO_DEPLOY_EV_THRESHOLD）。AAPL 300 超標、TSLA 50 未達。
    recs = [_rec("AAPL", "ma_crossover", 300.0), _rec("TSLA", "rsi", 50.0)]
    TestingSession, called, notes = _patch_scan(monkeypatch, tmp_path, market_open=True, recs=recs)

    run_opportunity_scan()

    assert called["screen"] == 1
    db = TestingSession()
    try:
        assert db.query(Opportunity).count() == 2
        aapl = db.query(Opportunity).filter_by(symbol="AAPL").first()
        tsla = db.query(Opportunity).filter_by(symbol="TSLA").first()
        # 超標的新候選 → 提醒後翻 seen（去抖）；未達標 → 維持 new
        assert aapl.status == "seen"
        assert tsla.status == "new"
    finally:
        db.close()
    assert len(notes) == 1 and "AAPL" in notes[0]

    # 再跑一次同樣結果：AAPL 已 seen、TSLA 仍未達標 → 不再提醒（去抖）
    run_opportunity_scan()
    assert len(notes) == 1


def test_scan_skips_when_market_closed(monkeypatch, tmp_path):
    recs = [_rec("AAPL", "ma_crossover", 300.0)]
    TestingSession, called, notes = _patch_scan(monkeypatch, tmp_path, market_open=False, recs=recs)

    run_opportunity_scan()

    # 收盤：不呼叫海選、不寫表、不提醒
    assert called["screen"] == 0
    db = TestingSession()
    try:
        assert db.query(Opportunity).count() == 0
    finally:
        db.close()
    assert notes == []


# ---------- 4. GET /opportunities（往返） ----------
@contextmanager
def _isolated_client(tmp_path):
    from backend.main import app

    engine = create_engine(
        f"sqlite:///{tmp_path / 'app_opp.db'}",
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


def test_get_opportunities_sorted_filtered(tmp_path):
    with _isolated_client(tmp_path) as (client, TestingSession):
        db = TestingSession()
        try:
            db.add_all([
                Opportunity(symbol="AAPL", strategy_key="ma_crossover", oos_expected_value=100.0, status="new"),
                Opportunity(symbol="TSLA", strategy_key="rsi", oos_expected_value=300.0, status="seen"),
                Opportunity(symbol="NVDA", strategy_key="macd", oos_expected_value=200.0, status="new"),
            ])
            db.commit()
        finally:
            db.close()

        # 依 OOS EV 由高到低
        rows = client.get("/opportunities").json()
        assert [r["symbol"] for r in rows] == ["TSLA", "NVDA", "AAPL"]

        # status 篩選
        new_only = client.get("/opportunities?status=new").json()
        assert {r["symbol"] for r in new_only} == {"AAPL", "NVDA"}

        # limit 夾取
        one = client.get("/opportunities?limit=1").json()
        assert len(one) == 1 and one[0]["symbol"] == "TSLA"
