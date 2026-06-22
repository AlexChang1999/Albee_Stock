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

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.database import Base, get_db
from backend.main import app
from backend.services import automation
from backend.services.alpaca_client import alpaca_client
from backend.services.automation import plan_deployments


# ---------- 共用：注入空 DB 的隔離 client ----------
@contextmanager
def _isolated_client(tmp_path):
    """
    用臨時 SQLite（Bot 表空）覆寫 get_db。

    為何需要：run_auto_deploy 會 db.query(Bot).all() 取 existing_symbols 去重。
    若走 dev DB，剛好有同名 Bot（如 AAPL）→ 候選被去重剔除 → planned 空、測試假性失敗。
    注入空表後 existing_symbols 為空，測試結果只取決於 stub 的海選/門檻，確定性。
    """
    engine = create_engine(
        f"sqlite:///{tmp_path / 'app_auto.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    def _override():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def _rec(symbol, ev, wr):
    """造一筆假推薦。

    Phase 6 step-04 後，自動部署門檻一律比對「樣本外（OOS）」指標，
    所以這裡的 ev / wr 放進 oos_* 欄位（門檻看的就是這組）。
    """
    return {
        "symbol": symbol,
        "strategy_key": "rsi",
        "params": {"period": 14},
        "metrics": {"oos_expected_value": ev, "oos_win_rate_pct": wr},
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


def test_run_dry_run(tmp_path, monkeypatch):
    """
    POST /automation/run?force=true&dry_run=true：
    用假海選餵兩檔，只有過雙門檻的應出現在 planned，且不寫 DB（dry_run）。

    三層隔離確保確定性（不依賴 dev DB / 真 Alpaca 帳戶）：
    - 規則：stub get_config 成固定門檻（不受 automation_config 列被別測改過影響）。
    - 海選：stub screen_watchlist 餵固定兩檔。
    - DB：_isolated_client 注入空 Bot 表（existing_symbols 空，候選不被同名 Bot 去重）。
    - 帳戶：stub get_account 丟例外 → available_cash=None、跳過資金閘（不看真帳戶餘額）。
    """
    class _Cfg:
        enabled = True
        ev_threshold = 150.0
        winrate_threshold = 55.0
        max_bots = 5
        cash_per_bot = 1000.0
        scan_hour = 8

    monkeypatch.setattr(automation, "get_config", lambda db: _Cfg())
    monkeypatch.setattr(
        automation.screener, "screen_watchlist",
        lambda **kwargs: {"recommendations": [
            _rec("AAPL", ev=200, wr=60),   # 過
            _rec("TSLA", ev=10, wr=51),    # EV 不過
        ]},
    )
    # 不連真 Alpaca：讓資金閘走「查不到帳戶 → 略過」分支，結果不依賴帳戶餘額
    def _boom():
        raise RuntimeError("no account in test")
    monkeypatch.setattr(alpaca_client, "get_account", _boom)

    with _isolated_client(tmp_path) as client:
        resp = client.post("/automation/run?force=true&dry_run=true")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["dry_run"] is True and body["deployed"] == [], body
        symbols = [p["symbol"] for p in body["planned"]]
        assert "AAPL" in symbols and "TSLA" not in symbols, body
    print("✅ POST /automation/run dry_run 通過")


if __name__ == "__main__":
    # 純函式 + GET 端點可直跑；test_run_dry_run 需 tmp_path / monkeypatch / DB 隔離，
    # 走 pytest 才能拿到那些 fixture，這裡不重覆它，請改用：
    #     venv\Scripts\python.exe -m pytest tests\test_automation.py -q
    test_plan_filters_by_thresholds()
    test_plan_skips_existing_and_respects_slots()
    test_plan_no_slots()
    test_get_automation()
    print("✅ 純函式 + GET /automation 通過")
    print("ℹ️  test_run_dry_run 請用 pytest 跑（需 fixture）：python -m pytest tests\\test_automation.py -q")
