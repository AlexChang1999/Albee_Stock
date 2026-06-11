"""
開機補跑 + 每日領導股回測測試
================================
涵蓋：
1. has_run_today / record_run：今天有記=True、昨天的紀錄不算今天。
2. make_daily_idempotent：同日第二次呼叫跳過（底層 fn 只跑一次）；
   fn 拋例外不落紀錄（之後可重試）。
3. run_catchup：CATCHUP_ON_BOOT=false 全跳；「開關關 / 時刻未到 / 已跑過」各自跳過；
   時刻已過且沒跑 → 補跑；一步失敗不中斷後續；順序 = 管線順序。
4. run_leader_backtest：各檔冠軍各存一筆 BacktestRun（is_good=False）；
   單檔失敗不擋其他檔；全數失敗拋例外（不落成功紀錄 → 之後重試）。

全離線：臨時 SQLite + monkeypatch settings 與各 job 函式。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_catchup.py -q
"""

import sys
from datetime import datetime
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

from backend.config import settings
from backend.database import Base
from backend.models import BacktestRun, JobRunLog
from backend.services import catchup, daily_watch
from backend.services.catchup import (
    has_run_today,
    record_run,
    make_daily_idempotent,
    run_catchup,
)
from backend.services.daily_watch import run_leader_backtest


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'catchup.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def db_factory(tmp_path, monkeypatch):
    """臨時 DB 的 session 工廠，並把 catchup/daily_watch 的 SessionLocal 換成它。"""
    factory = _session_factory(tmp_path)
    monkeypatch.setattr(catchup, "SessionLocal", factory)
    monkeypatch.setattr(daily_watch, "SessionLocal", factory)
    return factory


# ---------- 1. has_run_today / record_run ----------
def test_has_run_today_basic(db_factory):
    db = db_factory()
    assert has_run_today(db, "discovery_bridge") is False
    record_run(db, "discovery_bridge", detail="ok")
    assert has_run_today(db, "discovery_bridge") is True
    # 不同 job 互不影響
    assert has_run_today(db, "auto_validate") is False
    db.close()


def test_yesterday_record_not_today(db_factory):
    """昨天的成功紀錄不算今天——隔天要重新跑。"""
    db = db_factory()
    record_run(db, "heartbeat_daily", now=datetime(2026, 6, 10, 8, 0))
    assert has_run_today(db, "heartbeat_daily", now=datetime(2026, 6, 11, 9, 0)) is False
    assert has_run_today(db, "heartbeat_daily", now=datetime(2026, 6, 10, 23, 0)) is True
    db.close()


# ---------- 2. make_daily_idempotent ----------
def test_idempotent_runs_once_per_day(db_factory):
    calls = []
    wrapped = make_daily_idempotent("job_x", lambda: calls.append(1) or {"ok": True})
    assert wrapped() == {"ok": True}
    assert wrapped() is None  # 同日第二次：跳過
    assert len(calls) == 1

    db = db_factory()
    rows = db.query(JobRunLog).filter(JobRunLog.job_name == "job_x").all()
    assert len(rows) == 1
    assert "ok" in (rows[0].detail or "")
    db.close()


def test_idempotent_failure_not_recorded(db_factory):
    """fn 拋例外 → 不落紀錄 → 再呼叫會真的重跑（可重試）。"""
    calls = []

    def _boom():
        calls.append(1)
        raise RuntimeError("斷網")

    wrapped = make_daily_idempotent("job_y", _boom)
    with pytest.raises(RuntimeError):
        wrapped()
    db = db_factory()
    assert db.query(JobRunLog).filter(JobRunLog.job_name == "job_y").count() == 0
    db.close()
    with pytest.raises(RuntimeError):
        wrapped()  # 沒被「已跑過」擋住
    assert len(calls) == 2


# ---------- 3. run_catchup ----------
def _patch_jobs(monkeypatch, order):
    """把五個每日 job 函式都換成只記順序的 stub。"""
    def _stub(name):
        return lambda *a, **k: order.append(name)

    monkeypatch.setattr("backend.services.discovery.run_discovery_batch", _stub("discovery"))
    monkeypatch.setattr("backend.services.auto_validate.run_auto_validate", _stub("auto_validate"))
    monkeypatch.setattr("backend.services.daily_watch.run_leader_backtest", _stub("leader"))
    monkeypatch.setattr("backend.services.heartbeat.run_daily_heartbeat", _stub("heartbeat"))
    monkeypatch.setattr("backend.services.tracking.run_tracking_check", _stub("tracking"))


def _patch_settings(monkeypatch, **overrides):
    defaults = dict(
        CATCHUP_ON_BOOT=True,
        COLLECTOR_INTERVAL_MIN=0,  # 預設關 collector，個別測試再開
        DISCOVERY_ENABLED=True, DISCOVERY_HOUR=7,
        AUTO_VALIDATE_ENABLED=True, AUTO_VALIDATE_HOUR=8,
        LEADER_BACKTEST_ENABLED=True, LEADER_BACKTEST_HOUR=10,
        HEARTBEAT_HOUR=8,
        TRACKING_CHECK_HOUR=9,
    )
    defaults.update(overrides)
    for key, value in defaults.items():
        monkeypatch.setattr(settings, key, value)


def test_catchup_disabled(monkeypatch, db_factory):
    _patch_settings(monkeypatch, CATCHUP_ON_BOOT=False)
    assert run_catchup() == {"skipped": "CATCHUP_ON_BOOT=false"}


def test_catchup_runs_due_jobs_in_order(monkeypatch, db_factory):
    """時刻全過 + 都沒跑過 → 全補跑，且依管線順序。"""
    order = []
    _patch_jobs(monkeypatch, order)
    _patch_settings(monkeypatch)
    summary = run_catchup(now=datetime(2026, 6, 11, 23, 0))
    assert order == ["discovery", "auto_validate", "leader", "heartbeat", "tracking"]
    assert summary["discovery_bridge"] == "ran"
    assert summary["collector_scan"] == "disabled"


def test_catchup_skips_not_due_disabled_and_already_ran(monkeypatch, db_factory):
    """三種跳過：開關關 / 時刻未到 / 今天已跑過。"""
    order = []
    _patch_jobs(monkeypatch, order)
    _patch_settings(monkeypatch, DISCOVERY_ENABLED=False, LEADER_BACKTEST_HOUR=22)
    db = db_factory()
    record_run(db, "heartbeat_daily", now=datetime(2026, 6, 11, 8, 5))
    db.close()

    summary = run_catchup(now=datetime(2026, 6, 11, 12, 0))
    assert summary["discovery_bridge"] == "disabled"
    assert summary["leader_backtest"] == "not_due"     # 22 點還沒到
    assert summary["heartbeat_daily"] == "already_ran"
    assert summary["auto_validate"] == "ran"
    assert summary["tracking_check"] == "ran"
    assert order == ["auto_validate", "tracking"]


def test_catchup_one_failure_does_not_block_rest(monkeypatch, db_factory):
    """discovery 炸掉 → 後面照跑、summary 記 failed。"""
    order = []
    _patch_jobs(monkeypatch, order)

    def _boom(*a, **k):
        raise RuntimeError("LLM 連不上")

    monkeypatch.setattr("backend.services.discovery.run_discovery_batch", _boom)
    _patch_settings(monkeypatch)
    summary = run_catchup(now=datetime(2026, 6, 11, 23, 0))
    assert summary["discovery_bridge"].startswith("failed")
    assert order == ["auto_validate", "leader", "heartbeat", "tracking"]
    # 失敗的不落紀錄（之後可重試）
    db = db_factory()
    assert db.query(JobRunLog).filter(JobRunLog.job_name == "discovery_bridge").count() == 0
    db.close()


# ---------- 4. run_leader_backtest ----------
def _fake_scan(symbol, days=365, **kwargs):
    if symbol == "BAD":
        raise RuntimeError("抓不到資料")
    return {
        "symbol": symbol,
        "days": days,
        "best": {
            "strategy_key": "rsi",
            "params": {"period": 14},
            "metrics": {"oos_expected_value": 123.0},
        },
    }


def test_leader_backtest_stores_champion_per_symbol(monkeypatch, db_factory):
    monkeypatch.setattr(settings, "LEADER_BACKTEST_ENABLED", True)
    monkeypatch.setattr(settings, "LEADER_BACKTEST_SYMBOLS", "AAPL,BAD,NVDA")
    monkeypatch.setattr(settings, "LEADER_BACKTEST_DAYS", 365)
    monkeypatch.setattr("backend.services.optimizer.run_auto_backtest", _fake_scan)
    # 跑回測前的批次暖快取換掉（避免真打網路）
    monkeypatch.setattr("backend.services.bar_cache.get_bars_cached_multi", lambda *a, **k: {})

    db = db_factory()
    result = run_leader_backtest(db=db)
    assert result["stored"] == ["AAPL", "NVDA"]
    assert result["failed"] == ["BAD"]  # 單檔失敗不擋其他檔

    runs = db.query(BacktestRun).all()
    assert {r.symbol for r in runs} == {"AAPL", "NVDA"}
    assert all(r.is_good is False for r in runs)       # 例行紀錄不自動進好策略榜
    assert all(r.preset_id is None for r in runs)
    assert runs[0].metrics["oos_expected_value"] == 123.0
    db.close()


def test_leader_backtest_all_failed_raises(monkeypatch, db_factory):
    """全數失敗（斷網）→ 拋例外，讓排程/補跑不落成功紀錄、之後重試。"""
    monkeypatch.setattr(settings, "LEADER_BACKTEST_ENABLED", True)
    monkeypatch.setattr(settings, "LEADER_BACKTEST_SYMBOLS", "BAD")
    monkeypatch.setattr("backend.services.optimizer.run_auto_backtest", _fake_scan)
    monkeypatch.setattr("backend.services.bar_cache.get_bars_cached_multi", lambda *a, **k: {})
    db = db_factory()
    with pytest.raises(RuntimeError):
        run_leader_backtest(db=db)
    db.close()


def test_leader_backtest_disabled(monkeypatch, db_factory):
    monkeypatch.setattr(settings, "LEADER_BACKTEST_ENABLED", False)
    assert run_leader_backtest() == {"skipped": "LEADER_BACKTEST_ENABLED=false"}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
