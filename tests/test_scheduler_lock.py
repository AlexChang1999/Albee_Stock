"""
排程器選主鎖（租約制）測試
==========================
用 SQLite 直接跑底層租約函式（_try_acquire / _renew / _release），
模擬兩個實例（兩個 holder_id）互搶，驗證：

1. SQLite 單機恆為 leader（行為與舊版一致）
2. 先到先得：A 搶到後，B 在租約有效期內搶不到
3. 續約：持有者續約成功；非持有者續約失敗（= 失鎖訊號）
4. 過期接手：租約過期後 B 能接手
5. 正常讓位：A release 後 B 立刻接手（不用等 TTL）
6. 第三閘：非 leader 呼叫 assert_leader / submit_market_order 直接被拒
7. 升降級：守護 job tick 的 promote / demote 流程

不依賴 PostgreSQL——租約 SQL 是 DB 無關的（SQLAlchemy Core），
SQLite 上照樣原子（單檔寫入序列化）。
"""

import datetime as dt

import pytest
from sqlalchemy import update

from backend.database import SessionLocal, init_db
from backend.models.scheduler_lease import SchedulerLease
from backend.services import scheduler_lock as sl


@pytest.fixture(autouse=True)
def _fresh_lease():
    """每個測試前：建表 + 清空租約 + 重設模組旗標。"""
    init_db()
    db = SessionLocal()
    try:
        db.query(SchedulerLease).delete()
        db.commit()
    finally:
        db.close()
    sl._leader_flag = False
    sl._renew_failures = 0
    yield
    sl._leader_flag = False


def _expire_lease_now():
    """把租約的到期時間改成過去（模擬 leader 失聯超過 TTL）。"""
    db = SessionLocal()
    try:
        db.execute(
            update(SchedulerLease)
            .where(SchedulerLease.id == 1)
            .values(expires_at=dt.datetime(2000, 1, 1))
        )
        db.commit()
    finally:
        db.close()


def test_sqlite_always_leader(monkeypatch):
    """非 PostgreSQL（SQLite / 留空退回本機）→ 永遠是 leader，行為與舊版一致。"""
    monkeypatch.setattr(sl, "_is_postgres", lambda: False)
    assert sl.acquire_scheduler_lock() is True
    assert sl.is_leader() is True
    sl.assert_leader()  # 不應拋例外


def test_release_is_safe_when_no_lease():
    """沒持有租約時呼叫 release 不應拋例外（關機路徑要穩）。"""
    sl.release_scheduler_lock()  # 不該炸


def test_first_acquirer_wins_and_second_is_blocked():
    """先到先得：A 搶到後，B 在租約有效期內搶不到。"""
    assert sl._try_acquire("holder_A") is True
    assert sl._try_acquire("holder_B") is False
    # A 重複搶（等同續約）仍成功——冪等
    assert sl._try_acquire("holder_A") is True


def test_renew_only_works_for_current_holder():
    """續約：持有者成功；非持有者失敗（呼叫端據此判定「失鎖」）。"""
    assert sl._try_acquire("holder_A") is True
    assert sl._renew("holder_A") is True
    assert sl._renew("holder_B") is False


def test_expired_lease_can_be_taken_over():
    """過期接手：租約過期後另一實例能搶走，原持有者續約失敗。"""
    assert sl._try_acquire("holder_A") is True
    _expire_lease_now()
    assert sl._try_acquire("holder_B") is True
    # A 的租約已被 B 拿走 → A 續約必須失敗（這就是「發現已有新 leader」的訊號）
    assert sl._renew("holder_A") is False


def test_release_lets_next_instance_take_over_immediately():
    """正常讓位：release 後租約清空，另一實例立刻接手（不用等 TTL）。"""
    assert sl._try_acquire("holder_A") is True
    sl._release("holder_A")
    assert sl._try_acquire("holder_B") is True


def test_assert_leader_blocks_non_leader(monkeypatch):
    """第三閘：非 leader（PostgreSQL 模式下旗標 False）呼叫 assert_leader 直接被拒。"""
    # 模擬 PostgreSQL 環境（SQLite 下 is_leader 恆 True 是刻意設計，單機無競爭）
    monkeypatch.setattr(sl, "_is_postgres", lambda: True)
    sl._leader_flag = False
    with pytest.raises(RuntimeError, match="不是排程 leader"):
        sl.assert_leader()
    # 是 leader → 放行
    sl._leader_flag = True
    sl.assert_leader()  # 不應拋例外


def test_order_gate_blocks_non_leader(monkeypatch):
    """整合：非 leader 時 submit_market_order 在送單前就被第三閘擋下。"""
    from backend.config import settings
    from backend.services.alpaca_client import alpaca_client

    class FakeTrading:
        called = False

        def submit_order(self, req):
            self.called = True
            return "fake_order"

    fake = FakeTrading()
    monkeypatch.setattr(settings, "IS_PAPER", True)  # paper：雙閘放行，考驗第三閘
    monkeypatch.setattr(alpaca_client, "_trading", fake)
    monkeypatch.setattr(sl, "_is_postgres", lambda: True)
    sl._leader_flag = False

    with pytest.raises(RuntimeError, match="不是排程 leader"):
        alpaca_client.submit_market_order("AAPL", 1, "buy")
    assert fake.called is False, "第三閘沒擋住，非 leader 竟然送出訂單！"

    # 升回 leader → 放行
    sl._leader_flag = True
    assert alpaca_client.submit_market_order("AAPL", 1, "buy") == "fake_order"


def test_demote_sets_flag_before_unschedule(monkeypatch):
    """降級：先立旗（擋單）再卸排程；on_demote 炸掉也不影響旗標。"""
    monkeypatch.setattr(sl, "_is_postgres", lambda: True)
    sl._leader_flag = True
    seen = {}

    def on_demote():
        # 卸排程當下，旗標必須「已經」是 False（下單已被擋住）
        seen["flag_during_demote"] = sl._leader_flag
        raise RuntimeError("卸排程時炸掉")

    sl._demote(on_demote, reason="測試")
    assert seen["flag_during_demote"] is False
    assert sl.is_leader() is False


class _FakeScheduler:
    """抓住 daemon tick 函式，讓測試手動觸發（不真的起 APScheduler）。"""

    def add_job(self, func, *a, **k):
        self.tick = func


def test_lease_daemon_tick_promotes_follower(monkeypatch):
    """守護 job：follower 在租約空缺時自動升級，並呼叫 on_promote。"""
    monkeypatch.setattr(sl, "_is_postgres", lambda: True)
    calls = {"promote": 0}
    sched = _FakeScheduler()
    sl.start_lease_daemon(
        sched,
        on_promote=lambda: calls.__setitem__("promote", calls["promote"] + 1),
        on_demote=lambda: None,
    )

    sl._leader_flag = False
    sched.tick()  # 租約空缺 → 應搶到並升級
    assert sl.is_leader() is True
    assert calls["promote"] == 1


def test_lease_daemon_tick_demotes_when_lease_stolen(monkeypatch):
    """守護 job：leader 續約發現租約被搶（影響 0 列）→ 立即降級並呼叫 on_demote。"""
    monkeypatch.setattr(sl, "_is_postgres", lambda: True)
    calls = {"demote": 0}
    sched = _FakeScheduler()
    sl.start_lease_daemon(
        sched,
        on_promote=lambda: None,
        on_demote=lambda: calls.__setitem__("demote", calls["demote"] + 1),
    )

    # 我自以為是 leader，但租約其實在別人手上（模擬 Neon 掐線後被接手）
    assert sl._try_acquire("someone_else") is True
    sl._leader_flag = True
    sched.tick()
    assert sl.is_leader() is False
    assert calls["demote"] == 1
