"""
探討讀取 API 測試 ── Phase 9 step-05
====================================
驗證 GET /explorations（列路標）、GET /explorations/{name}（讀內容）的往返、
404、以及**防路徑穿越**（../ 之類被擋）。純檔案 IO，不需 LLM/連線。

執行（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_explorations_api.py -q
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

import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import app
from backend.services import explorations

client = TestClient(app)


def _make_run(rid, strategy="williams_r", symbol="AAPL", ev=-3.2):
    return SimpleNamespace(
        id=rid,
        strategy_key=strategy,
        symbol=symbol,
        params={"period": 14},
        metrics={"expected_value": ev, "profit_factor": 0.7, "win_rate_pct": 80.0},
    )


@pytest.fixture
def expdir(tmp_path, monkeypatch):
    """把探討資料夾指到暫存目錄，測試彼此隔離。"""
    monkeypatch.setattr(settings, "EXPLORATIONS_DIR", str(tmp_path))
    return tmp_path


def test_list_explorations(expdir):
    """寫兩筆檢討 → GET /explorations 回兩筆路標。"""
    explorations.write_exploration(_make_run(12), "EV 為負，疑似過擬合。")
    explorations.write_exploration(_make_run(13, strategy="rsi"), "RSI 在盤整期假訊號多。")

    r = client.get("/explorations")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    run_ids = {e["run_id"] for e in data}
    assert run_ids == {12, 13}


def test_read_exploration_roundtrip(expdir):
    """寫一筆 → GET /explorations/{name} 讀回內容（含內文）。"""
    fname = explorations.write_exploration(_make_run(12), "建議放寬參數區間。")
    r = client.get(f"/explorations/{fname}")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == fname
    assert "建議放寬參數區間" in body["content"]


def test_read_missing_returns_404(expdir):
    """讀不存在的檔 → 404。"""
    r = client.get("/explorations/run-9999-nope-zzz.md")
    assert r.status_code == 404


def test_path_traversal_blocked(expdir, tmp_path):
    """防穿越：嘗試用 ../ 讀資料夾外的檔 → 一律 404（不外洩）。"""
    # 在探討資料夾的上一層放一個機密檔
    secret = tmp_path.parent / "secret.md"
    secret.write_text("TOP SECRET", encoding="utf-8")

    # 用編碼過的 ../ 試著穿越（FastAPI 會解碼路徑參數）
    r = client.get("/explorations/..%2Fsecret.md")
    assert r.status_code == 404
    # 非 .md 也擋
    r2 = client.get("/explorations/run-0012-williams_r-aapl.txt")
    assert r2.status_code == 404
