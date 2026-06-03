"""
全自動護欄 / 模式 B 自動部署測試
================================
兩部分：
1. 純函式 plan_deployments：EV/勝率雙門檻 + 去重 + 名額上限
2. API：GET /automation（看規則）、POST /automation/run?dry_run（預覽不寫 DB）

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe tests\\test_automation.py
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
from backend.services import automation
from backend.services.automation import plan_deployments


def _rec(symbol, ev, wr):
    """造一筆假推薦。"""
    return {
        "symbol": symbol,
        "strategy_key": "rsi",
        "params": {"period": 14},
        "metrics": {"expected_value": ev, "win_rate_pct": wr},
    }


# ---------- 1. 純函式 ----------
def test_plan_filters_by_thresholds():
    """EV 或勝率任一不過 → 不部署。"""
    recs = [
        _rec("AAPL", ev=200, wr=60),  # 兩個都過 → 入選
        _rec("TSLA", ev=100, wr=80),  # EV 不過
        _rec("NVDA", ev=300, wr=40),  # 勝率不過
    ]
    planned = plan_deployments(
        recs, ev_threshold=150, winrate_threshold=55,
        max_bots=5, existing_symbols=set(), active_count=0,
    )
    assert [r["symbol"] for r in planned] == ["AAPL"], planned


def test_plan_skips_existing_and_respects_slots():
    """已有 Bot 的標的略過；名額（max−active）用完就停。"""
    recs = [_rec("AAPL", 200, 60), _rec("TSLA", 200, 60), _rec("NVDA", 200, 60)]
    # 已有 AAPL，且 max=3、已啟用 1 → 只剩 2 名額；AAPL 略過，挑 TSLA、NVDA
    planned = plan_deployments(
        recs, ev_threshold=150, winrate_threshold=55,
        max_bots=3, existing_symbols={"AAPL"}, active_count=1,
    )
    assert [r["symbol"] for r in planned] == ["TSLA", "NVDA"], planned


def test_plan_no_slots():
    """名額為 0（已達上限）→ 一個都不部署。"""
    recs = [_rec("AAPL", 999, 99)]
    planned = plan_deployments(
        recs, ev_threshold=150, winrate_threshold=55,
        max_bots=2, existing_symbols=set(), active_count=2,
    )
    assert planned == []
    print("✅ plan_deployments 純函式全通過")


# ---------- 2. API ----------
def test_get_automation():
    """GET /automation 應回規則與名額狀態。"""
    with TestClient(app) as client:
        resp = client.get("/automation")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # 預設總開關關閉
        assert body["enabled"] is False, body
        assert "ev_threshold" in body and "slots_left" in body, body
    print("✅ GET /automation 通過")


def test_run_dry_run(monkeypatch):
    """
    POST /automation/run?force=true&dry_run=true：
    用假海選餵兩檔，只有過雙門檻的應出現在 planned，且不寫 DB（dry_run）。
    """
    monkeypatch.setattr(
        automation.screener, "screen_watchlist",
        lambda **kwargs: {"recommendations": [
            _rec("AAPL", ev=200, wr=60),   # 過
            _rec("TSLA", ev=10, wr=51),    # EV 不過
        ]},
    )
    with TestClient(app) as client:
        resp = client.post("/automation/run?force=true&dry_run=true")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["dry_run"] is True and body["deployed"] == [], body
        symbols = [p["symbol"] for p in body["planned"]]
        assert "AAPL" in symbols and "TSLA" not in symbols, body
    print("✅ POST /automation/run dry_run 通過")


if __name__ == "__main__":
    test_plan_filters_by_thresholds()
    test_plan_skips_existing_and_respects_slots()
    test_plan_no_slots()
    test_get_automation()
    # __main__ 直跑：手動替換海選再還原
    _orig = automation.screener.screen_watchlist
    automation.screener.screen_watchlist = lambda **kwargs: {"recommendations": [
        _rec("AAPL", 200, 60), _rec("TSLA", 10, 51)]}
    try:
        with TestClient(app) as client:
            resp = client.post("/automation/run?force=true&dry_run=true")
            body = resp.json()
            assert body["dry_run"] is True and "AAPL" in [p["symbol"] for p in body["planned"]], body
        print("✅ POST /automation/run dry_run 通過")
    finally:
        automation.screener.screen_watchlist = _orig
    print("\n🎉 全部自動部署測試通過！")
