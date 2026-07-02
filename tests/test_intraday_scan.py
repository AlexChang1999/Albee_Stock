# -*- coding: utf-8 -*-
"""
日內單一掃描迴圈（Phase 16 M8）測試
====================================
- run_intraday_scan：批次抓一次（每 timeframe 一桶）→ 只派發日內 Bot；休市直接返回
- 預取快取：新鮮才命中、過期退回單檔 REST 路徑；positions=None 視為不可信
- run_bot_once 吃快取：命中時不打單檔 get_position / get_latest_price
- start_bot 分流：日內 Bot 併入掃描迴圈（不掛 per-bot job）；1Day Bot / 掃描關閉時照舊

比照 test_bot_manager：臨時 SQLite 當測試 DB、外部呼叫全 monkeypatch，不連網。
"""

import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.bots.bot_manager as bm
from backend.config import settings
from backend.database import Base
from backend.models import Bot
from backend.strategies import Signal


def _setup_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    monkeypatch.setattr(bm, "SessionLocal", TestSession)
    return TestSession


def _create_bot(TestSession, symbol="TEST", timeframe="5Min", active=True) -> int:
    s = TestSession()
    bot = Bot(name=f"測試{symbol}", strategy="ma_crossover", symbol=symbol, params={},
              trade_amount=1000.0, is_active=active, timeframe=timeframe)
    s.add(bot)
    s.commit()
    bot_id = bot.id
    s.close()
    return bot_id


def _reset_prefetch():
    """清空預取快取（模組層狀態，測試間不可互染）。"""
    bm._scan_prefetch.update({"bars": {}, "prices": {}, "positions": None, "at": 0.0})


@pytest.fixture(autouse=True)
def _clean_prefetch():
    """前後都清：留下「新鮮」快取會污染同行程跑的 test_bot_manager（實測踩過）。"""
    _reset_prefetch()
    yield
    _reset_prefetch()


def _df(n=30):
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-07-01 09:30", periods=n, freq="5min").astype(str),
        "open": [100.0] * n, "high": [101.0] * n, "low": [99.0] * n,
        "close": [100.0] * n, "volume": [1000.0] * n,
    })


# ---------- run_intraday_scan ----------
def test_scan_batches_once_and_dispatches_only_intraday(tmp_path, monkeypatch):
    _reset_prefetch()
    TestSession = _setup_db(tmp_path, monkeypatch)
    id_a = _create_bot(TestSession, "AAA", "5Min")
    id_b = _create_bot(TestSession, "BBB", "5Min")
    id_daily = _create_bot(TestSession, "CCC", "1Day")
    _create_bot(TestSession, "DDD", "5Min", active=False)  # 停用不掃

    monkeypatch.setattr(settings, "INTRADAY_SCAN_INTERVAL_SEC", 30)
    monkeypatch.setattr(bm.alpaca_client, "is_market_open", lambda: True)
    multi_calls = []
    monkeypatch.setattr(
        bm.market_data, "get_bars_multi",
        lambda symbols, days, source, timeframe:
            multi_calls.append((tuple(symbols), timeframe)) or {s: _df() for s in symbols},
    )
    monkeypatch.setattr(bm.alpaca_client, "get_latest_prices",
                        lambda symbols: {s: 100.0 for s in symbols})
    monkeypatch.setattr(bm.alpaca_client, "list_positions", lambda: [])
    dispatched = []
    monkeypatch.setattr(bm, "run_bot_once", lambda bot_id: dispatched.append(bot_id))
    monkeypatch.setattr(bm, "notify", lambda msg: None)

    bm.run_intraday_scan()

    assert len(multi_calls) == 1                       # 同 timeframe 一桶＝一次批次抓
    assert multi_calls[0] == (("AAA", "BBB"), "5Min")  # 停用 / 1Day 不進桶
    assert sorted(dispatched) == sorted([id_a, id_b])  # 只派發日內 Bot
    assert id_daily not in dispatched
    assert bm._prefetched_bars("AAA", "5Min") is not None  # 快取已填
    assert bm._prefetched_price("BBB") == 100.0


def test_scan_returns_early_when_market_closed(tmp_path, monkeypatch):
    _reset_prefetch()
    TestSession = _setup_db(tmp_path, monkeypatch)
    _create_bot(TestSession, "AAA", "5Min")
    monkeypatch.setattr(bm.alpaca_client, "is_market_open", lambda: False)
    called = []
    monkeypatch.setattr(bm.market_data, "get_bars_multi",
                        lambda *a, **k: called.append(1) or {})
    monkeypatch.setattr(bm, "run_bot_once", lambda bot_id: called.append(bot_id))
    bm.run_intraday_scan()
    assert called == []  # 休市：不抓、不派發（也不逐 bot 灌 DecisionLog）


# ---------- 預取快取語意 ----------
def test_prefetch_expires_and_positions_none_untrusted(monkeypatch):
    _reset_prefetch()
    monkeypatch.setattr(settings, "INTRADAY_SCAN_INTERVAL_SEC", 30)
    bm._scan_prefetch.update({
        "bars": {("AAA", "5Min"): _df()}, "prices": {"AAA": 99.0},
        "positions": None, "at": time.monotonic(),
    })
    assert bm._prefetched_bars("AAA", "5Min") is not None
    assert bm._prefetched_price("AAA") == 99.0
    hit, _ = bm._prefetched_position("AAA")
    assert hit is False  # positions=None＝整包不可信 → 未命中（退回單檔查）

    bm._scan_prefetch["at"] = time.monotonic() - 61  # 過期（30×2 秒外）
    assert bm._prefetched_bars("AAA", "5Min") is None
    assert bm._prefetched_price("AAA") is None

    monkeypatch.setattr(settings, "INTRADAY_SCAN_INTERVAL_SEC", 0)  # 掃描關閉恆不命中
    bm._scan_prefetch["at"] = time.monotonic()
    assert bm._prefetched_bars("AAA", "5Min") is None


def test_prefetch_position_hit_none_means_truly_flat(monkeypatch):
    _reset_prefetch()
    monkeypatch.setattr(settings, "INTRADAY_SCAN_INTERVAL_SEC", 30)
    pos = SimpleNamespace(symbol="AAA", avg_entry_price=100.0, qty=1)
    bm._scan_prefetch.update({"bars": {}, "prices": {},
                              "positions": {"AAA": pos}, "at": time.monotonic()})
    hit, got = bm._prefetched_position("AAA")
    assert hit and got is pos
    hit, got = bm._prefetched_position("BBB")
    assert hit and got is None  # 整包快照查無此檔＝真的空手（有效答案）


# ---------- run_bot_once 吃快取 ----------
def test_run_bot_once_uses_prefetch_not_single_rest(tmp_path, monkeypatch):
    _reset_prefetch()
    TestSession = _setup_db(tmp_path, monkeypatch)
    bot_id = _create_bot(TestSession, "TEST", "5Min")
    monkeypatch.setattr(settings, "INTRADAY_SCAN_INTERVAL_SEC", 30)
    bm._scan_prefetch.update({"bars": {}, "prices": {"TEST": 123.0},
                              "positions": {}, "at": time.monotonic()})

    def _boom(*a, **k):
        raise AssertionError("快取命中時不應打單檔 REST")

    monkeypatch.setattr(bm.alpaca_client, "is_market_open", lambda: True)
    monkeypatch.setattr(bm.alpaca_client, "get_position", _boom)
    monkeypatch.setattr(bm.alpaca_client, "get_latest_price", _boom)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot, open_: (Signal.HOLD, "觀望"))
    monkeypatch.setattr(bm, "notify", lambda msg: None)
    monkeypatch.setattr(bm, "emit_activity", lambda *a, **k: None)

    bm.run_bot_once(bot_id)  # 沒炸 = 持倉/現價都吃快取（空手觀望走完整輪）


# ---------- start_bot 分流 ----------
def test_start_bot_intraday_joins_scan_loop(monkeypatch):
    monkeypatch.setattr(settings, "INTRADAY_SCAN_INTERVAL_SEC", 30)
    monkeypatch.setattr(bm, "notify", lambda msg: None)
    fake = SimpleNamespace(id=99901, name="日內Bot", timeframe="5Min")
    bm.bot_manager.start_bot(fake, interval_seconds=30)
    assert bm.bot_manager.scheduler.get_job("bot_99901") is None  # 不掛 per-bot job


def test_start_bot_daily_or_scan_disabled_keeps_per_bot_job(monkeypatch):
    monkeypatch.setattr(bm, "notify", lambda msg: None)
    # 1Day Bot：照舊掛 per-bot job
    monkeypatch.setattr(settings, "INTRADAY_SCAN_INTERVAL_SEC", 30)
    daily = SimpleNamespace(id=99902, name="日K Bot", timeframe="1Day")
    bm.bot_manager.start_bot(daily, interval_seconds=300)
    assert bm.bot_manager.scheduler.get_job("bot_99902") is not None
    bm.bot_manager.stop_bot(99902)
    # 掃描關閉：日內 Bot 退回 per-bot job（與 M8 之前行為一致）
    monkeypatch.setattr(settings, "INTRADAY_SCAN_INTERVAL_SEC", 0)
    intraday = SimpleNamespace(id=99903, name="日內Bot", timeframe="5Min")
    bm.bot_manager.start_bot(intraday, interval_seconds=30)
    assert bm.bot_manager.scheduler.get_job("bot_99903") is not None
    bm.bot_manager.stop_bot(99903)
