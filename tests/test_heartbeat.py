"""
心跳 + dead-man switch 測試（維運安全軌 H2 Step 4）
====================================================
驗證 heartbeat 服務的關鍵性質：
- build_heartbeat_message 純函式格式（含 None → "?" 降級顯示）。
- run_daily_heartbeat 一定會發通知——就算所有查詢都炸掉（心跳永不崩）。
- ping_deadman：URL 留空不打；有 URL 打對網址；失敗不丟例外。

全程 monkeypatch，不連網、不碰真資料庫。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_heartbeat.py -q
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

import backend.services.heartbeat as hb
from backend.config import settings


# ---------- build_heartbeat_message ----------

def test_message_contains_all_numbers():
    """正常情況：訊息含所有數字與權益格式。"""
    msg = hb.build_heartbeat_message(
        positions_count=3, active_bots=2, decisions_today=15,
        equity=12345.6, now=datetime(2026, 6, 11, 8, 0),
    )
    assert "2026-06-11 08:00" in msg
    assert "持倉 3 檔" in msg
    assert "啟用 Bot 2 個" in msg
    assert "今日決策 15 筆" in msg
    assert "$12,345.60" in msg
    print("✅ 心跳訊息格式測試通過")


def test_message_degrades_to_question_marks():
    """查不到的數字以 ? 顯示——缺資料也要發，發不出去才是事故。"""
    msg = hb.build_heartbeat_message(
        positions_count=None, active_bots=None, decisions_today=None,
        equity=None, now=datetime(2026, 6, 11, 8, 0),
    )
    assert "持倉 ? 檔" in msg and "權益 ?" in msg
    print("✅ 心跳訊息缺值降級測試通過")


def test_message_contains_funnel_line():
    """探勘漏斗待審提醒（Phase 12 step-04）：有數字時日報含漏斗行。"""
    msg = hb.build_heartbeat_message(
        positions_count=3, active_bots=2, decisions_today=15,
        equity=12345.6, now=datetime(2026, 6, 11, 8, 0),
        candidate_count=4, validated_pending=2,
    )
    assert "探勘漏斗：candidate 4｜validated 待審 2" in msg
    print("✅ 心跳漏斗行測試通過")


def test_message_funnel_degrades_to_question_marks():
    """漏斗數查不到（或舊呼叫端沒傳）→ ? 帶過，心跳照發。"""
    msg = hb.build_heartbeat_message(
        positions_count=None, active_bots=None, decisions_today=None,
        equity=None, now=datetime(2026, 6, 11, 8, 0),
    )
    assert "探勘漏斗：candidate ?｜validated 待審 ?" in msg
    print("✅ 心跳漏斗缺值降級測試通過")


# ---------- run_daily_heartbeat ----------

def test_daily_heartbeat_sends_notification(monkeypatch):
    """正常路徑：有發通知，且內容帶到查回來的數字。"""
    sent = []
    monkeypatch.setattr(hb, "notify", lambda msg: sent.append(msg))
    monkeypatch.setattr(hb.alpaca_client, "list_positions", lambda: ["p1", "p2"])

    class FakeAccount:
        portfolio_value = "10000.5"

    monkeypatch.setattr(hb.alpaca_client, "get_account", lambda: FakeAccount())

    # DB 查詢換成假的（query 鏈最後 .count() 回固定值）
    class FakeQuery:
        def __init__(self, n):
            self.n = n
        def filter(self, *a, **k):
            return self
        def count(self):
            return self.n

    class FakeSession:
        def query(self, model):
            return FakeQuery(4)
        def close(self):
            pass

    monkeypatch.setattr(hb, "SessionLocal", lambda: FakeSession())

    hb.run_daily_heartbeat()

    assert len(sent) == 1, sent
    assert "持倉 2 檔" in sent[0]
    assert "$10,000.50" in sent[0]
    print("✅ 心跳日報發送測試通過")


def test_daily_heartbeat_never_crashes(monkeypatch):
    """心跳永不崩：所有查詢都炸掉，仍然要發出（內容全 ?）。"""
    sent = []
    monkeypatch.setattr(hb, "notify", lambda msg: sent.append(msg))
    monkeypatch.setattr(
        hb.alpaca_client, "list_positions",
        lambda: (_ for _ in ()).throw(RuntimeError("離線")),
    )
    monkeypatch.setattr(
        hb.alpaca_client, "get_account",
        lambda: (_ for _ in ()).throw(RuntimeError("無金鑰")),
    )
    monkeypatch.setattr(
        hb, "SessionLocal",
        lambda: (_ for _ in ()).throw(RuntimeError("DB 壞了")),
    )

    hb.run_daily_heartbeat()  # 不該丟例外

    assert len(sent) == 1, sent
    assert "持倉 ? 檔" in sent[0]
    print("✅ 心跳永不崩測試通過")


# ---------- ping_deadman ----------

def test_ping_skipped_when_url_empty(monkeypatch):
    """URL 留空 = dead-man 功能關，完全不打網路。"""
    monkeypatch.setattr(settings, "HEARTBEAT_PING_URL", "")
    monkeypatch.setattr(
        hb.requests, "get",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("URL 空時不該打網路")),
    )
    hb.ping_deadman()
    print("✅ URL 空不 ping 測試通過")


def test_ping_hits_configured_url(monkeypatch):
    """有 URL → GET 打到設定的網址（timeout 有帶）。"""
    monkeypatch.setattr(settings, "HEARTBEAT_PING_URL", "https://hc-ping.com/fake-uuid")
    calls = []
    monkeypatch.setattr(hb.requests, "get", lambda url, timeout: calls.append((url, timeout)))

    hb.ping_deadman()

    assert calls == [("https://hc-ping.com/fake-uuid", 10)], calls
    print("✅ ping 打對網址測試通過")


def test_ping_failure_does_not_raise(monkeypatch):
    """ping 失敗（斷網）不丟例外——外側沒收到 ping 會發警報，正是它的工作。"""
    monkeypatch.setattr(settings, "HEARTBEAT_PING_URL", "https://hc-ping.com/fake-uuid")
    monkeypatch.setattr(
        hb.requests, "get",
        lambda url, timeout: (_ for _ in ()).throw(ConnectionError("斷網")),
    )
    hb.ping_deadman()  # 不該丟例外
    print("✅ ping 失敗不丟例外測試通過")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
