"""
通知服務測試
============
驗證 notify() 的多管道行為，重點：
- Discord 有設定 webhook → 會 POST 正確的 payload。
- 沒設定 → 完全不發。
- 一個管道丟例外 → 不影響另一個、也不讓 notify 崩潰。

全程 mock requests.post，不真的對外連線。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_notifier.py
"""

import sys
from pathlib import Path
from types import SimpleNamespace

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import backend.services.notifier as nt


def test_discord_sends_when_configured(monkeypatch):
    """有設定 webhook → POST 到該網址，content 為訊息文字。"""
    calls = []
    monkeypatch.setattr(nt, "DISCORD_WEBHOOK_URL", "https://discord.test/webhook")
    monkeypatch.setattr(
        nt.requests, "post",
        lambda url, **kw: calls.append((url, kw)) or SimpleNamespace(status_code=204, text=""),
    )

    nt.notify("測試訊息")

    assert len(calls) == 1, calls
    url, kw = calls[0]
    assert url == "https://discord.test/webhook"
    assert kw["json"] == {"content": "測試訊息"}
    print("✅ Discord 有設定就推播測試通過")


def test_discord_skipped_when_not_configured(monkeypatch):
    """沒設定 webhook → 完全不呼叫 requests.post。"""
    calls = []
    monkeypatch.setattr(nt, "DISCORD_WEBHOOK_URL", "")
    monkeypatch.setattr(nt.requests, "post", lambda url, **kw: calls.append(url))

    nt.notify("測試訊息")

    assert calls == [], calls
    print("✅ Discord 未設定不推播測試通過")


def test_discord_failure_does_not_crash(monkeypatch):
    """Discord 推播丟例外 → notify 不崩潰（吞掉並印警告）。"""
    monkeypatch.setattr(nt, "DISCORD_WEBHOOK_URL", "https://discord.test/webhook")

    def boom(url, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(nt.requests, "post", boom)

    # 不該丟例外
    nt.notify("測試訊息")
    print("✅ Discord 失敗不崩潰測試通過")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
