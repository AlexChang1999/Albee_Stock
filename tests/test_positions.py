"""
持倉 API 測試
=============
驗 GET /positions：把 alpaca_client.list_positions 換成假持倉，確認端點回傳的
形狀 / 欄位 / 數字型別正確，且不連網。另驗無持倉時回空清單。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_positions.py -q
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
from backend.routers import positions


class _FakePosition:
    """模仿 alpaca-py Position：數字以字串回傳（與真 API 一致，驗 router 有轉 float）。"""

    def __init__(self, symbol, qty, avg, cur, mv, pl, plpc):
        self.symbol = symbol
        self.qty = qty
        self.avg_entry_price = avg
        self.current_price = cur
        self.market_value = mv
        self.unrealized_pl = pl
        self.unrealized_plpc = plpc


def test_positions_shape_and_types(monkeypatch):
    """有持倉時：回各欄位、數字轉成 float。"""
    fake = [
        _FakePosition("AAPL", "10", "150.0", "160.5", "1605.0", "105.0", "0.07"),
        _FakePosition("TSLA", "5", "200.0", "190.0", "950.0", "-50.0", "-0.05"),
    ]
    monkeypatch.setattr(positions.alpaca_client, "list_positions", lambda: fake)

    with TestClient(app) as client:
        r = client.get("/positions")
        assert r.status_code == 200, r.text
        body = r.json()

    assert [p["symbol"] for p in body] == ["AAPL", "TSLA"]
    aapl = body[0]
    # 欄位齊全
    for key in ("symbol", "qty", "avg_entry_price", "current_price",
                "market_value", "unrealized_pl", "unrealized_plpc"):
        assert key in aapl, aapl
    # 字串數字應被轉成 float
    assert isinstance(aapl["qty"], float) and aapl["qty"] == 10.0
    assert isinstance(aapl["unrealized_pl"], float) and aapl["unrealized_pl"] == 105.0
    assert body[1]["unrealized_pl"] == -50.0  # 浮虧保留負號


def test_positions_empty_on_failure(monkeypatch):
    """無金鑰 / 失敗時 list_positions 回 []，端點照樣回空清單、不丟錯。"""
    monkeypatch.setattr(positions.alpaca_client, "list_positions", lambda: [])
    with TestClient(app) as client:
        r = client.get("/positions")
        assert r.status_code == 200, r.text
        assert r.json() == []
