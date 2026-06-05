"""
風控水位線端點測試 ── PUT /bots/{id}/risk
================================================
給圖表「拖曳止損/止盈水位線」即時連動後端用。重點驗：
  1. 只更新「有帶」的欄位（exclude_unset）：拖一條線不會把其他風控清掉。
  2. 百分比邊界檢查（0 < x < 1），擋掉拖過頭的離譜值 → 400。
  3. 帶 null 可關閉某機制。

不碰 Alpaca：POST /bots 與 PUT /bots/{id}/risk 都不連線；用 PUT 回應驗證即可
（不呼叫 GET /bots，因為那會去 Alpaca 查持倉均價）。

執行（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_bot_risk.py -q
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
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


@pytest.fixture
def bot_id():
    """建一個帶止損的 Bot，測完刪掉。"""
    payload = {
        "name": "測試-風控水位線",
        "strategy": "ma_crossover",
        "symbol": "AAPL",
        "params": {},
        "trade_amount": 1000,
        "stop_loss_pct": 0.05,
    }
    r = client.post("/bots", json=payload)
    assert r.status_code == 200, r.text
    bid = r.json()["id"]
    yield bid
    client.delete(f"/bots/{bid}")


def test_partial_update_keeps_other_fields(bot_id):
    """只送 stop_loss_pct，trailing 不該被動到（exclude_unset）。"""
    r = client.put(f"/bots/{bot_id}/risk", json={"stop_loss_pct": 0.08})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stop_loss_pct"] == 0.08
    assert body["trailing_stop_pct"] is None  # 沒帶 → 維持原本的 None

    # 再只送 trailing，stop 應保持 0.08 不被洗掉
    r = client.put(f"/bots/{bot_id}/risk", json={"trailing_stop_pct": 0.03})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["trailing_stop_pct"] == 0.03
    assert body["stop_loss_pct"] == 0.08  # 上一步設的值還在


def test_out_of_range_rejected(bot_id):
    """百分比超出 (0,1) → 400，且不改到資料。"""
    for bad in (1.5, -0.1, 0, 1):
        r = client.put(f"/bots/{bot_id}/risk", json={"stop_loss_pct": bad})
        assert r.status_code == 400, f"{bad} 應被擋下，得到 {r.status_code}"


def test_null_disables(bot_id):
    """帶 null → 關閉該機制（設回 None）。"""
    r = client.put(f"/bots/{bot_id}/risk", json={"stop_loss_pct": None})
    assert r.status_code == 200, r.text
    assert r.json()["stop_loss_pct"] is None


def test_unknown_bot_404():
    r = client.put("/bots/999999/risk", json={"stop_loss_pct": 0.05})
    assert r.status_code == 404
