"""
即時報價測試
============
兩部分：
1. QuoteHub 的「訂閱簿記」純邏輯（不碰網路/async）
2. WebSocket /ws/quotes 整合測試（用 TestClient，拉價函式換成假資料，免連 Alpaca）

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe tests\\test_quotes.py
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.quote_stream import QuoteHub, hub


# ---------- 1. 純邏輯：訂閱簿記 ----------
def test_subscribed_symbols_union():
    """多個前端的訂閱合併後應去重。"""
    h = QuoteHub()
    h.subscribe("client_A", ["AAPL", "TSLA"])
    h.subscribe("client_B", ["AAPL"])
    assert h.subscribed_symbols() == {"AAPL", "TSLA"}
    print("✅ 訂閱合併去重通過")


def test_clients_for_symbol():
    """clients_for 應只回傳有訂閱該股票的前端。"""
    h = QuoteHub()
    h.subscribe("client_A", ["AAPL", "TSLA"])
    h.subscribe("client_B", ["AAPL"])
    assert set(h.clients_for("AAPL")) == {"client_A", "client_B"}
    assert set(h.clients_for("TSLA")) == {"client_A"}
    print("✅ 依股票挑訂閱者通過")


def test_unsubscribe_and_disconnect():
    """退訂與斷線應正確更新簿記。"""
    h = QuoteHub()
    h.subscribe("client_A", ["AAPL", "TSLA"])
    h.unsubscribe("client_A", ["TSLA"])
    assert h.subscribed_symbols() == {"AAPL"}
    h.disconnect("client_A")
    assert h.subscribed_symbols() == set()
    print("✅ 退訂/斷線簿記通過")


# ---------- 2. WebSocket 整合 ----------
def test_websocket_pushes_price(monkeypatch):
    """
    前端訂閱後，應在短時間內收到後端推來的價格。
    把拉價函式換成固定假價、輪詢間隔縮短，避免連網與等待。
    """
    # 換掉全域 hub 的拉價來源與輪詢間隔（測試專用；批次版：吃 list、回 dict）
    monkeypatch.setattr(hub, "_fetch_prices", lambda symbols: {s: 123.45 for s in symbols})
    monkeypatch.setattr(hub, "poll_interval", 0.05)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/quotes") as ws:
            ws.send_json({"action": "subscribe", "symbols": ["AAPL"]})
            msg = ws.receive_json()  # 應很快收到第一筆推送
            assert msg["symbol"] == "AAPL", msg
            assert msg["price"] == 123.45, msg
            assert "ts" in msg, msg
    print("✅ WebSocket 即時推送通過：", "AAPL = 123.45")


if __name__ == "__main__":
    test_subscribed_symbols_union()
    test_clients_for_symbol()
    test_unsubscribe_and_disconnect()
    # __main__ 直接跑時沒有 pytest 的 monkeypatch，這裡手動替換再還原
    _orig_fetch, _orig_interval = hub._fetch_prices, hub.poll_interval
    hub._fetch_prices = lambda symbols: {s: 123.45 for s in symbols}
    hub.poll_interval = 0.05
    try:
        with TestClient(app) as client:
            with client.websocket_connect("/ws/quotes") as ws:
                ws.send_json({"action": "subscribe", "symbols": ["AAPL"]})
                msg = ws.receive_json()
                assert msg["symbol"] == "AAPL" and msg["price"] == 123.45, msg
        print("✅ WebSocket 即時推送通過：AAPL = 123.45")
    finally:
        hub._fetch_prices, hub.poll_interval = _orig_fetch, _orig_interval
    print("\n🎉 全部即時報價測試通過！")
