"""
模式 B 自動駕駛（autopilot）單元測試
=====================================
驗證 services/autopilot.py 的護欄邏輯，完全不連網、不動正式資料庫
（用 in-memory SQLite + monkeypatch 掉 screener 與 bot_manager.start_bot）：

1. 總開關關閉 + force=False → 不執行（ran=False）。
2. EV 與勝率「同時達標」才自動部署；勝率不足被擋下。
3. 同標的已有自動 Bot → 去重跳過。
4. 達數量上限 → 停止再部署（cap_reached）。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_autopilot.py
"""

import sys
from pathlib import Path

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
from backend.models import Bot
from backend.services import autopilot


@pytest.fixture
def memdb(monkeypatch):
    """造一個 in-memory SQLite，把 autopilot 用的 SessionLocal 換成它，測完即丟。"""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    monkeypatch.setattr(autopilot, "SessionLocal", TestSession)
    return TestSession


@pytest.fixture(autouse=True)
def no_op_scheduler(monkeypatch):
    """把真正掛排程的 start_bot 換成 no-op，測試不啟動 APScheduler、不下單。"""
    from backend.bots.bot_manager import bot_manager
    monkeypatch.setattr(bot_manager, "start_bot", lambda *a, **k: None)


def _fake_screen(recs):
    """回一個假的 screener.screen：忽略參數，固定回給定的推薦清單。"""
    def _screen(*args, **kwargs):
        return {
            "universe_size": 10,
            "layer1_passed": [r["symbol"] for r in recs],
            "recommendations": recs,
        }
    return _screen


def _rec(symbol, ev, win_rate, strategy_key="rsi"):
    return {
        "symbol": symbol,
        "strategy_key": strategy_key,
        "params": {},
        "metrics": {"expected_value": ev, "win_rate_pct": win_rate},
    }


def _set_rules(monkeypatch, **kw):
    """覆寫 autopilot.settings 上的門檻設定。"""
    defaults = {
        "AUTO_PILOT_ENABLED": True,
        "AUTO_PILOT_MIN_EV": 150.0,
        "AUTO_PILOT_MIN_WIN_RATE": 55.0,
        "AUTO_PILOT_MAX_BOTS": 5,
        "AUTO_PILOT_TRADE_AMOUNT": 1000.0,
        "IS_PAPER": True,
        "ALLOW_LIVE_TRADING": False,
    }
    defaults.update(kw)
    for k, v in defaults.items():
        monkeypatch.setattr(autopilot.settings, k, v)


def test_disabled_and_not_forced_does_nothing(memdb, monkeypatch):
    """總開關關 + force=False → 不執行、不部署。"""
    _set_rules(monkeypatch, AUTO_PILOT_ENABLED=False)
    monkeypatch.setattr(autopilot.screener, "screen", _fake_screen([_rec("AAPL", 200, 60)]))
    result = autopilot.run_autopilot_scan(force=False)
    assert result["ran"] is False
    assert result["deployed"] == []


def test_deploy_when_ev_and_winrate_pass(memdb, monkeypatch):
    """EV≥門檻且勝率≥門檻 → 自動部署，且 DB 真的多一筆 auto_created Bot。"""
    _set_rules(monkeypatch)
    monkeypatch.setattr(autopilot.screener, "screen", _fake_screen([_rec("NVDA", 300, 70)]))
    result = autopilot.run_autopilot_scan(force=True)
    assert len(result["deployed"]) == 1
    assert result["deployed"][0]["symbol"] == "NVDA"

    db = memdb()
    try:
        bots = db.query(Bot).filter(Bot.auto_created.is_(True)).all()
        assert len(bots) == 1
        assert bots[0].symbol == "NVDA"
        assert bots[0].is_active is True
    finally:
        db.close()


def test_reject_low_win_rate(memdb, monkeypatch):
    """EV 夠高但勝率不足 → 被擋下、不部署。"""
    _set_rules(monkeypatch)
    monkeypatch.setattr(autopilot.screener, "screen", _fake_screen([_rec("TSLA", 500, 40)]))
    result = autopilot.run_autopilot_scan(force=True)
    assert result["deployed"] == []
    assert len(result["rejected_low_win_rate"]) == 1
    assert result["rejected_low_win_rate"][0]["symbol"] == "TSLA"


def test_dedup_existing_symbol(memdb, monkeypatch):
    """同標的已有自動 Bot → 去重跳過，不重複建。"""
    _set_rules(monkeypatch)
    # 先塞一個既有的自動 AAPL Bot
    db = memdb()
    try:
        db.add(Bot(name="🤖 AAPL", strategy="rsi", symbol="AAPL", auto_created=True, is_active=True))
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(autopilot.screener, "screen", _fake_screen([_rec("AAPL", 300, 70)]))
    result = autopilot.run_autopilot_scan(force=True)
    assert result["deployed"] == []
    assert "AAPL" in result["skipped_existing"]


def test_cap_reached(memdb, monkeypatch):
    """達數量上限 → 不再部署、cap_reached=True。"""
    _set_rules(monkeypatch, AUTO_PILOT_MAX_BOTS=1)
    # 先塞滿 1 個既有自動 Bot（不同標的，不觸發去重）
    db = memdb()
    try:
        db.add(Bot(name="🤖 MSFT", strategy="rsi", symbol="MSFT", auto_created=True, is_active=True))
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(autopilot.screener, "screen", _fake_screen([_rec("NVDA", 300, 70)]))
    result = autopilot.run_autopilot_scan(force=True)
    assert result["deployed"] == []
    assert result["cap_reached"] is True
