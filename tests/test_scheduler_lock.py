"""
排程器選主鎖測試
================
重點驗證：SQLite 單機環境永遠是 leader（無競爭、不碰 DB advisory lock）。
PostgreSQL 的真正互搶行為需要真連線，留給整合環境驗，不在單元測試做。
"""

from backend.services import scheduler_lock


def test_sqlite_always_leader(monkeypatch):
    """非 PostgreSQL（SQLite / 留空退回本機）→ acquire 一定回 True。"""
    monkeypatch.setattr(scheduler_lock, "_is_postgres", lambda: False)
    assert scheduler_lock.acquire_scheduler_lock() is True


def test_release_is_safe_when_no_lock():
    """沒持有鎖時呼叫 release 不應拋例外（關機路徑要穩）。"""
    scheduler_lock._lock_conn = None
    scheduler_lock.release_scheduler_lock()  # 不該炸


if __name__ == "__main__":
    test_sqlite_always_leader(type("M", (), {"setattr": staticmethod(setattr)})())
    test_release_is_safe_when_no_lock()
    print("scheduler_lock 測試通過")
