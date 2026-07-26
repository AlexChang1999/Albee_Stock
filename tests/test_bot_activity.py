"""
Bot 活動事件中樞測試
====================
驗證「可視化事件管線」的三條鐵則：
1. thread→asyncio 橋安全且保序（APScheduler 執行緒 publish → 迴圈上依序扇出）。
2. 沒有事件迴圈（測試環境 / 啟動早期）publish 是安靜的 no-op，不炸。
3. 可視化絕不影響交易主流程：hub 炸掉，run_bot_once 照常完成下單。

另驗證：新連線回放 ring buffer、run_bot_once 插樁後事件序列正確。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_bot_activity.py
"""

import asyncio
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.bots.bot_manager as bm
import backend.services.bot_activity as ba
from backend.database import Base
from backend.models import Bot
from backend.strategies import Signal


class FakeWS:
    """假 WebSocket：只記錄收到的事件。"""

    def __init__(self):
        self.received = []

    async def accept(self):
        pass

    async def send_json(self, data):
        self.received.append(data)


# ====================================================================
# Hub 本體（thread 橋 + 保序 + 回放）
# ====================================================================

def test_publish_from_thread_keeps_order():
    """從另一條執行緒連發多則事件 → 迴圈上的連線依序收齊（順序就是語義）。"""

    async def scenario():
        hub = ba.BotActivityHub()
        hub.attach_loop()
        ws = FakeWS()
        await hub.connect(ws)

        def worker():
            for i in range(5):
                hub.publish({"seq": i})

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        await asyncio.sleep(0.1)  # 給 forwarder 時間消化佇列
        return ws.received

    received = asyncio.run(scenario())
    assert [e["seq"] for e in received] == [0, 1, 2, 3, 4], received
    print("✅ 跨執行緒 publish 保序測試通過")


def test_publish_without_loop_is_noop():
    """還沒 attach_loop（測試環境 / 啟動早期）→ publish 不炸、事件進 ring buffer。"""
    hub = ba.BotActivityHub()
    hub.publish({"seq": 1})  # 不該拋任何例外
    assert list(hub._recent) == [{"seq": 1}]
    print("✅ 無迴圈 publish no-op 測試通過")


def test_new_connection_replays_recent():
    """新連線先收到 ring buffer 回放（feed 開頁不空白），之後照常收新事件。"""

    async def scenario():
        hub = ba.BotActivityHub()
        hub.attach_loop()
        hub.publish({"seq": "old-1"})
        hub.publish({"seq": "old-2"})
        await asyncio.sleep(0.05)  # 舊事件先被 forwarder 消化（沒人連線、丟掉）

        ws = FakeWS()
        await hub.connect(ws)  # 連上即回放
        hub.publish({"seq": "new"})
        await asyncio.sleep(0.05)
        return ws.received

    received = asyncio.run(scenario())
    assert [e["seq"] for e in received] == ["old-1", "old-2", "new"], received
    print("✅ 新連線回放 ring buffer 測試通過")


def test_dead_client_gets_kicked():
    """推送失敗的連線被踢掉，不影響其他連線繼續收。"""

    class DeadWS(FakeWS):
        async def send_json(self, data):
            raise RuntimeError("connection lost")

    async def scenario():
        hub = ba.BotActivityHub()
        hub.attach_loop()
        dead, alive = DeadWS(), FakeWS()
        await hub.connect(dead)
        await hub.connect(alive)
        hub.publish({"seq": 1})
        await asyncio.sleep(0.05)
        return hub._clients, alive.received

    clients, received = asyncio.run(scenario())
    assert all(not isinstance(c, DeadWS) for c in clients)
    assert [e["seq"] for e in received] == [1], received
    print("✅ 死連線自動踢除測試通過")


# ====================================================================
# emit 防呆
# ====================================================================

def test_emit_swallows_all_errors(monkeypatch):
    """emit 內任何爆炸（hub 壞掉）都被吞掉——可視化絕不影響呼叫端。"""
    monkeypatch.setattr(
        ba.hub, "publish",
        lambda event: (_ for _ in ()).throw(RuntimeError("hub 壞了")),
    )
    ba.emit(SimpleNamespace(id=1, name="x", symbol="T"), "cycle_start")  # 不該拋
    print("✅ emit 吞例外測試通過")


def test_safe_float():
    """safe_float：數字正常轉、None / 不可轉物件回 None，絕不拋。"""
    assert ba.safe_float("3.5") == 3.5
    assert ba.safe_float(None) is None
    assert ba.safe_float(object()) is None
    print("✅ safe_float 防呆測試通過")


# ====================================================================
# run_bot_once 插樁（事件序列 + 不影響交易）
# ====================================================================

def _setup_db(tmp_path, monkeypatch):
    """臨時 SQLite 測試 DB（同 test_bot_manager 的做法）。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    monkeypatch.setattr(bm, "SessionLocal", TestSession)
    return TestSession


def _create_bot(TestSession) -> int:
    s = TestSession()
    bot = Bot(name="事件測試Bot", strategy="ma_crossover", symbol="TEST",
              params={}, trade_amount=1000.0, is_active=True, check_interval_sec=30)
    s.add(bot)
    s.commit()
    bot_id = bot.id
    s.close()
    return bot_id


def _patch_trading(monkeypatch, position, price, orders):
    """把交易相關外部呼叫換成假的（決策審計 _record_decision 保留真的，事件才會發）。"""
    monkeypatch.setattr(bm.alpaca_client, "is_market_open", lambda: True)
    monkeypatch.setattr(bm.alpaca_client, "get_position", lambda s: position)
    monkeypatch.setattr(bm.alpaca_client, "get_latest_price", lambda s: price)
    monkeypatch.setattr(
        bm.alpaca_client, "submit_market_order",
        lambda symbol, qty, side: orders.append((symbol, qty, side)) or "fake_order",
    )
    monkeypatch.setattr(bm, "notify", lambda *a, **k: None)
    monkeypatch.setattr(bm, "check_breaker", lambda db=None: {"tripped": False})
    monkeypatch.setattr(bm, "_available_buying_power", lambda: None)


def _collect_events(monkeypatch):
    """攔截 hub.publish 收集事件（不需要事件迴圈）。"""
    events = []
    monkeypatch.setattr(ba.hub, "publish", lambda event: events.append(event))
    return events


def test_flat_hold_emits_full_sequence(tmp_path, monkeypatch):
    """空手觀望一輪 → cycle_start → fetch → fetch(K線) → compute → decision → cycle_end。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders = []
    _patch_trading(monkeypatch, position=None, price=50.0, orders=orders)
    events = _collect_events(monkeypatch)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot, market_is_open: (Signal.HOLD, "無交叉訊號"))

    bm.run_bot_once(_create_bot(TestSession))

    phases = [e["phase"] for e in events]
    # _run_strategy 被換成假的 → 沒有抓 K 線/算訊號那兩則，但主幹序列必須在且有序
    assert phases == ["cycle_start", "fetch_data", "decision", "cycle_end"], phases
    decision = next(e for e in events if e["phase"] == "decision")
    assert decision["decision"]["action"] == bm.ACTION_HOLD
    assert decision["decision"]["reason"] == "無交叉訊號"
    end = events[-1]
    assert end["status"] == "ok"
    assert end["next_run_in_sec"] == 30  # 吃 bot.check_interval_sec
    assert end["is_active"] is True
    print("✅ 空手觀望事件序列測試通過")


def test_buy_emits_order_event(tmp_path, monkeypatch):
    """空手買進 → 多一則 order_submitted（在 decision 前，因 _record_and_notify 先跑）。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders = []
    _patch_trading(monkeypatch, position=None, price=50.0, orders=orders)
    events = _collect_events(monkeypatch)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot, market_is_open: (Signal.BUY, "黃金交叉"))

    bm.run_bot_once(_create_bot(TestSession))

    assert len(orders) == 1 and orders[0][2] == "buy", orders
    phases = [e["phase"] for e in events]
    assert "order_submitted" in phases, phases
    order_event = next(e for e in events if e["phase"] == "order_submitted")
    assert order_event["order"]["side"] == "buy"
    print("✅ 買進發 order_submitted 事件測試通過")


def test_market_closed_emits_skipped_cycle_end(tmp_path, monkeypatch):
    """休市一輪 → decision(action=skipped_market_closed) + cycle_end(status 同)。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders = []
    _patch_trading(monkeypatch, position=None, price=50.0, orders=orders)
    monkeypatch.setattr(bm.alpaca_client, "is_market_open", lambda: False)
    events = _collect_events(monkeypatch)

    bm.run_bot_once(_create_bot(TestSession))

    decision = next(e for e in events if e["phase"] == "decision")
    assert decision["decision"]["action"] == bm.ACTION_SKIPPED_MARKET_CLOSED
    assert events[-1]["phase"] == "cycle_end"
    assert events[-1]["status"] == "skipped_market_closed"
    print("✅ 休市事件測試通過")


def test_error_emits_cycle_end_error(tmp_path, monkeypatch):
    """執行中爆炸 → cycle_end(status=error) 仍會發（前端看得到這輪掛了）。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders = []
    _patch_trading(monkeypatch, position=None, price=50.0, orders=orders)
    monkeypatch.setattr(
        bm.alpaca_client, "get_latest_price",
        lambda s: (_ for _ in ()).throw(RuntimeError("API 掛了")),
    )
    events = _collect_events(monkeypatch)

    bm.run_bot_once(_create_bot(TestSession))  # 不該拋（既有行為：接住並通知）

    assert events[-1]["phase"] == "cycle_end"
    assert events[-1]["status"] == "error"
    assert "API 掛了" in events[-1]["detail"]
    print("✅ 錯誤輪 cycle_end(error) 測試通過")


def test_broken_hub_does_not_break_trading(tmp_path, monkeypatch):
    """鐵則：hub.publish 永遠爆炸 → 交易照常完成（買單照下）。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders = []
    _patch_trading(monkeypatch, position=None, price=50.0, orders=orders)
    monkeypatch.setattr(
        ba.hub, "publish",
        lambda event: (_ for _ in ()).throw(RuntimeError("可視化壞了")),
    )
    monkeypatch.setattr(bm, "_run_strategy", lambda bot, market_is_open: (Signal.BUY, "黃金交叉"))

    bm.run_bot_once(_create_bot(TestSession))

    assert len(orders) == 1 and orders[0][2] == "buy", orders
    print("✅ 可視化壞掉不影響交易測試通過")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
