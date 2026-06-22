"""
決策審計軌跡測試（Phase 6 step-08）
====================================
驗證 run_bot_once 各分支都寫對 DecisionLog（action / signal / reason），含「沒成交但有決策」：
休市跳過 / 空手觀望 / 續抱 / 購買力不足 / 熔斷 / 買進 / 風控賣出。
另測 GET /bots/{id}/decisions 往返（倒序、數量上限）。

不連網：臨時 SQLite + monkeypatch alpaca / 通知。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_decision_log.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.bots.bot_manager as bm
from backend.database import Base
from backend.models import Bot, DecisionLog
from backend.models.decision_log import (
    ACTION_BOUGHT, ACTION_SOLD, ACTION_HOLD,
    ACTION_SKIPPED_MARKET_CLOSED, ACTION_SKIPPED_NO_BUYING_POWER,
    ACTION_SKIPPED_CIRCUIT_BREAKER,
)
from backend.strategies import Signal


class FakePosition:
    def __init__(self, avg_entry_price, qty):
        self.avg_entry_price = avg_entry_price
        self.qty = qty


def _setup_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'dec.db'}")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    monkeypatch.setattr(bm, "SessionLocal", TestSession)
    return TestSession


def _create_bot(TestSession, **risk) -> int:
    s = TestSession()
    bot = Bot(name="決策Bot", strategy="ma_crossover", symbol="TEST", params={},
              trade_amount=1000.0,
              stop_loss_pct=risk.get("stop_loss_pct"))
    s.add(bot)
    s.commit()
    bot_id = bot.id
    s.close()
    return bot_id


def _patch(monkeypatch, position, price):
    """真寫 DecisionLog（不 monkeypatch _record_decision），其餘 IO 全假。"""
    monkeypatch.setattr(bm.alpaca_client, "is_market_open", lambda: True)
    monkeypatch.setattr(bm.alpaca_client, "get_position", lambda s: position)
    monkeypatch.setattr(bm.alpaca_client, "get_latest_price", lambda s: price)
    monkeypatch.setattr(bm.alpaca_client, "submit_market_order", lambda *a, **k: "fake_order")
    monkeypatch.setattr(bm, "_record_and_notify", lambda *a, **k: None)
    monkeypatch.setattr(bm, "_mark_checked", lambda bot: None)
    monkeypatch.setattr(bm, "_persist_peak", lambda bot, peak: setattr(bot, "peak_price", peak))
    # 守門預設放行；個別測試再覆寫
    monkeypatch.setattr(bm, "check_breaker", lambda db=None: {"tripped": False})
    monkeypatch.setattr(bm, "_available_buying_power", lambda: None)


def _last_decision(TestSession, bot_id) -> DecisionLog:
    s = TestSession()
    row = (s.query(DecisionLog).filter(DecisionLog.bot_id == bot_id)
           .order_by(DecisionLog.id.desc()).first())
    s.close()
    return row


def test_bought_decision(tmp_path, monkeypatch):
    TestSession = _setup_db(tmp_path, monkeypatch)
    _patch(monkeypatch, position=None, price=50)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.BUY, "黃金交叉"))
    bid = _create_bot(TestSession)
    bm.run_bot_once(bid)
    d = _last_decision(TestSession, bid)
    assert d.action == ACTION_BOUGHT and d.signal == "buy" and d.reason == "黃金交叉", d


def test_flat_hold_decision(tmp_path, monkeypatch):
    TestSession = _setup_db(tmp_path, monkeypatch)
    _patch(monkeypatch, position=None, price=50)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.HOLD, "觀望中"))
    bid = _create_bot(TestSession)
    bm.run_bot_once(bid)
    d = _last_decision(TestSession, bid)
    assert d.action == ACTION_HOLD and d.signal == "hold", d


def test_no_buying_power_decision(tmp_path, monkeypatch):
    TestSession = _setup_db(tmp_path, monkeypatch)
    _patch(monkeypatch, position=None, price=50)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.BUY, "黃金交叉"))
    monkeypatch.setattr(bm, "_available_buying_power", lambda: 100.0)  # 需 1000 > 可用 100
    bid = _create_bot(TestSession)
    bm.run_bot_once(bid)
    d = _last_decision(TestSession, bid)
    assert d.action == ACTION_SKIPPED_NO_BUYING_POWER, d
    assert "購買力不足" in d.reason, d


def test_circuit_breaker_decision(tmp_path, monkeypatch):
    TestSession = _setup_db(tmp_path, monkeypatch)
    _patch(monkeypatch, position=None, price=50)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.BUY, "黃金交叉"))
    monkeypatch.setattr(bm, "check_breaker", lambda db=None: {"tripped": True})
    bid = _create_bot(TestSession)
    bm.run_bot_once(bid)
    d = _last_decision(TestSession, bid)
    assert d.action == ACTION_SKIPPED_CIRCUIT_BREAKER, d


def test_market_closed_decision(tmp_path, monkeypatch):
    TestSession = _setup_db(tmp_path, monkeypatch)
    _patch(monkeypatch, position=None, price=50)
    monkeypatch.setattr(bm.alpaca_client, "is_market_open", lambda: False)
    bid = _create_bot(TestSession)
    bm.run_bot_once(bid)  # 預設遵守開市
    d = _last_decision(TestSession, bid)
    assert d.action == ACTION_SKIPPED_MARKET_CLOSED and d.signal == "hold", d


def test_risk_sold_decision(tmp_path, monkeypatch):
    TestSession = _setup_db(tmp_path, monkeypatch)
    _patch(monkeypatch, position=FakePosition(avg_entry_price=100, qty=10), price=94)
    # 策略不該被問（止損先觸發）；設成被呼叫就爆
    monkeypatch.setattr(bm, "_run_strategy",
                        lambda bot: (_ for _ in ()).throw(AssertionError("止損時不該問策略")))
    bid = _create_bot(TestSession, stop_loss_pct=0.05)
    bm.run_bot_once(bid)
    d = _last_decision(TestSession, bid)
    assert d.action == ACTION_SOLD and d.signal == "sell", d
    print("✅ 各分支決策審計寫入測試通過")


def test_decision_records_volume_qty_indicators(tmp_path, monkeypatch):
    """Phase 15：買進決策要落 量(volume)/股數(qty)/指標快照(indicators)。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    _patch(monkeypatch, position=None, price=50)
    ctx = {"volume": 123456.0, "indicators": {"ma_short": 231.2, "ma_long": 228.4}}
    # 真實路徑回 3-tuple（signal, reason, ctx）
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.BUY, "黃金交叉", ctx))
    bid = _create_bot(TestSession)
    bm.run_bot_once(bid)
    d = _last_decision(TestSession, bid)
    assert d.action == ACTION_BOUGHT
    assert d.volume == 123456.0
    assert d.qty == 20.0  # round(1000 / 50, 4)
    assert d.indicators == {"ma_short": 231.2, "ma_long": 228.4}


def test_run_strategy_returns_ctx_with_volume_and_indicators(monkeypatch):
    """_run_strategy 回 (signal, reason, ctx)；ctx 帶 df 末根量 + compute_overlays 指標快照。"""
    import pandas as pd
    from types import SimpleNamespace

    n = 40
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="D"),
        "open": [100.0] * n, "high": [101.0] * n, "low": [99.0] * n,
        "close": [100.0] * n,                       # 平盤 → ma_crossover 觀望，不觸發 meta 路徑
        "volume": [1000.0 + i for i in range(n)],
    })
    monkeypatch.setattr(bm.market_data, "get_bars", lambda *a, **k: df)
    bot = SimpleNamespace(symbol="TEST", strategy="ma_crossover",
                          params={"short_window": 5, "long_window": 20}, adaptive=False)
    signal, reason, ctx = bm._run_strategy(bot)
    assert ctx["volume"] == 1039.0                  # 末根 1000+39
    assert ctx["indicators"] and "ma_short" in ctx["indicators"]  # 指標快照有值


def test_decisions_endpoint_roundtrip(tmp_path, monkeypatch):
    """GET /bots/{id}/decisions：建幾筆 → 查回來，依時間倒序、受 limit 上限。"""
    from fastapi.testclient import TestClient
    import backend.routers.bots as bots_router
    from backend.database import get_db
    from backend.main import app

    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    # 路由用 get_db；覆寫成測試 DB
    def _override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = _override_get_db

    s = TestSession()
    bot = Bot(name="ep", strategy="rsi", symbol="AAPL")
    s.add(bot)
    s.commit()
    bid = bot.id
    for i in range(3):
        s.add(DecisionLog(bot_id=bid, symbol="AAPL", signal="hold",
                          reason=f"r{i}", price=10.0 + i, action=ACTION_HOLD))
    s.commit()
    s.close()

    try:
        with TestClient(app) as client:
            resp = client.get(f"/bots/{bid}/decisions?limit=2")
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert len(body) == 2, body                 # 受 limit 上限
            assert body[0]["reason"] == "r2", body      # 倒序：最新在前
    finally:
        app.dependency_overrides.pop(get_db, None)
    print("✅ GET /bots/{id}/decisions 往返測試通過")


def test_recent_decisions_endpoint_cross_bot(tmp_path, monkeypatch):
    """GET /bots/decisions/recent：跨 Bot 倒序合流 + 帶 bot_name +
    路由不被 /{bot_id} 吃掉（"decisions" 不是合法 bot_id）。"""
    from fastapi.testclient import TestClient
    from backend.database import get_db
    from backend.main import app

    engine = create_engine(f"sqlite:///{tmp_path / 'recent.db'}")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    def _override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = _override_get_db

    s = TestSession()
    a = Bot(name="甲", strategy="rsi", symbol="AAPL")
    b = Bot(name="乙", strategy="macd", symbol="TSLA")
    s.add_all([a, b])
    s.commit()
    s.add(DecisionLog(bot_id=a.id, symbol="AAPL", signal="hold",
                      reason="甲的觀望", price=10.0, action=ACTION_HOLD))
    s.add(DecisionLog(bot_id=b.id, symbol="TSLA", signal="buy",
                      reason="乙的買進", price=20.0, action=ACTION_BOUGHT))
    s.commit()
    s.close()

    try:
        with TestClient(app) as client:
            resp = client.get("/bots/decisions/recent?limit=10")
            assert resp.status_code == 200, resp.text  # 沒被 /{bot_id} 路由吃掉而 422
            body = resp.json()
            assert len(body) == 2, body
            names = {row["bot_name"] for row in body}
            assert names == {"甲", "乙"}, names          # 跨 Bot 合流 + 帶名字
            assert body[0]["reason"] == "乙的買進", body  # 倒序：最新在前
    finally:
        app.dependency_overrides.pop(get_db, None)
    print("✅ GET /bots/decisions/recent 跨 Bot 合流測試通過")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
