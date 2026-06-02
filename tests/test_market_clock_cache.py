"""
開市狀態快取測試
================
驗證 AlpacaClient.is_market_open() 的 TTL 快取：
- 短時間內多次呼叫（模擬多個 Bot 同一輪）只真的問 Alpaca 一次。
- 超過 TTL 後會重新問一次。

不連網：把底層 trading client 換成假的、用假時鐘控制時間流逝。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_market_clock_cache.py
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

import backend.services.alpaca_client as ac_mod
from backend.services.alpaca_client import AlpacaClient


class FakeClock:
    """假的 Alpaca trading client，記錄 get_clock 被叫幾次。"""
    def __init__(self, is_open=True):
        self.calls = 0
        self._is_open = is_open

    def get_clock(self):
        self.calls += 1
        return SimpleNamespace(is_open=self._is_open)


def test_clock_cached_within_ttl(monkeypatch):
    """TTL 內多次呼叫 → 底層只問一次。"""
    client = AlpacaClient()
    fake = FakeClock(is_open=True)
    client._trading = fake  # 直接塞進去，跳過真的建立 client

    # 假時鐘：固定在 t=1000，不前進
    monkeypatch.setattr(ac_mod.time, "monotonic", lambda: 1000.0)

    assert client.is_market_open() is True
    assert client.is_market_open() is True
    assert client.is_market_open() is True
    assert fake.calls == 1, f"TTL 內應只問一次，實際 {fake.calls}"
    print("✅ TTL 內共用快取測試通過")


def test_clock_refreshes_after_ttl(monkeypatch):
    """超過 TTL → 重新問一次。"""
    client = AlpacaClient()
    fake = FakeClock(is_open=True)
    client._trading = fake

    now = {"t": 1000.0}
    monkeypatch.setattr(ac_mod.time, "monotonic", lambda: now["t"])

    client.is_market_open()                       # 第一次，問一次
    now["t"] += AlpacaClient.CLOCK_CACHE_TTL_SEC + 1  # 時間跳過 TTL
    client.is_market_open()                       # 過期，再問一次

    assert fake.calls == 2, f"過 TTL 應重新問，實際 {fake.calls}"
    print("✅ 過 TTL 重新查詢測試通過")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
