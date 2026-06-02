"""
實盤交易安全閥測試
==================
這是跟「真錢」有關的防線，務必測到位。
驗證 submit_market_order 的安全閥行為：

- 連到實盤(真錢) 且 ALLOW_LIVE_TRADING 關 → 拒絕下單（丟 RuntimeError）。
- 連到實盤 且 ALLOW_LIVE_TRADING 開 → 放行。
- Paper(模擬) → 不受安全閥影響，直接放行。

用 monkeypatch 改設定、並把底層交易 client 換成假的，
所以不需真金鑰、不會真的下單。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_safety_valve.py
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

from backend.config import settings
from backend.services.alpaca_client import alpaca_client


class FakeTrading:
    """假的交易 client，只記錄有沒有真的被叫到 submit_order。"""
    def __init__(self):
        self.called = False

    def submit_order(self, order_request):
        self.called = True
        return "fake_order"


def test_live_without_flag_is_blocked(monkeypatch):
    """實盤 + 安全閥關 → 拒絕下單，且底層 client 完全不該被呼叫。"""
    monkeypatch.setattr(settings, "IS_PAPER", False)
    monkeypatch.setattr(settings, "ALLOW_LIVE_TRADING", False)
    fake = FakeTrading()
    monkeypatch.setattr(alpaca_client, "_trading", fake)

    with pytest.raises(RuntimeError, match="拒絕下單"):
        alpaca_client.submit_market_order("AAPL", 1, "buy")

    assert fake.called is False, "安全閥沒擋住，竟然真的送出下單！"
    print("✅ 實盤未開閘 → 拒絕下單測試通過")


def test_live_with_flag_is_allowed(monkeypatch):
    """實盤 + 安全閥開 → 放行（兩道閘都開）。"""
    monkeypatch.setattr(settings, "IS_PAPER", False)
    monkeypatch.setattr(settings, "ALLOW_LIVE_TRADING", True)
    fake = FakeTrading()
    monkeypatch.setattr(alpaca_client, "_trading", fake)

    result = alpaca_client.submit_market_order("AAPL", 1, "buy")

    assert result == "fake_order", result
    assert fake.called is True
    print("✅ 實盤已開閘 → 放行測試通過")


def test_paper_is_allowed(monkeypatch):
    """Paper(模擬) → 不受安全閥影響，直接放行。"""
    monkeypatch.setattr(settings, "IS_PAPER", True)
    monkeypatch.setattr(settings, "ALLOW_LIVE_TRADING", False)
    fake = FakeTrading()
    monkeypatch.setattr(alpaca_client, "_trading", fake)

    result = alpaca_client.submit_market_order("AAPL", 1, "buy")

    assert result == "fake_order", result
    assert fake.called is True
    print("✅ Paper 模式放行測試通過")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
