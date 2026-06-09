"""
公司戰情聚合端點測試（Phase 10 step-01）
==========================================
涵蓋：
1. GET /company/overview 聚合鍵齊全（account / bots / automation / circuit_breaker / decisions）。
2. 離線降級：get_account 丟例外時 account=None，整頁不崩、其餘區塊照常。
3. Bot 艦隊 total/active 計數、決策倒序。

不連網：用臨時 SQLite 覆寫 get_db，避免污染 dev DB；get_account 用 monkeypatch。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_company.py -q
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

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastapi.testclient import TestClient

from backend.database import Base, get_db
from backend.models import Bot, DecisionLog
from backend.models.decision_log import ACTION_BOUGHT, ACTION_HOLD


@contextmanager
def _client_with_db(tmp_path):
    """
    開一個 TestClient，把 get_db 覆寫成臨時 SQLite，並回傳該 DB 的 sessionmaker
    供測試自行 seed。lifespan 仍走真 DB 但只排程、無破壞性副作用。
    """
    from backend.main import app

    engine = create_engine(
        f"sqlite:///{tmp_path / 'company.db'}",
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
            yield client, TestingSession
    finally:
        app.dependency_overrides.pop(get_db, None)


def _seed(TestingSession):
    """種 2 個 Bot（1 啟用）+ 2 筆決策。"""
    db = TestingSession()
    try:
        db.add_all([
            Bot(name="均線 Bot", strategy="ma_crossover", symbol="AAPL", is_active=True),
            Bot(name="RSI Bot", strategy="rsi", symbol="TSLA", is_active=False),
        ])
        db.add_all([
            DecisionLog(bot_id=1, symbol="AAPL", signal="buy", reason="黃金交叉",
                        price=190.0, action=ACTION_BOUGHT),
            DecisionLog(bot_id=2, symbol="TSLA", signal="hold", reason="觀望",
                        price=240.0, action=ACTION_HOLD),
        ])
        db.commit()
    finally:
        db.close()


def test_overview_keys_and_offline_account(monkeypatch, tmp_path):
    """get_account 丟例外 → account=None；其餘聚合鍵齊全、計數正確。"""
    import backend.routers.company as company_mod

    def _boom():
        raise RuntimeError("離線：沒設金鑰")

    monkeypatch.setattr(company_mod.alpaca_client, "get_account", _boom)

    with _client_with_db(tmp_path) as (client, TestingSession):
        _seed(TestingSession)
        resp = client.get("/company/overview")
        assert resp.status_code == 200, resp.text
        body = resp.json()

        # 聚合鍵齊全
        for key in ("account", "bots", "automation", "circuit_breaker", "decisions"):
            assert key in body, f"缺少聚合鍵 {key}：{body}"

        # 離線降級：帳戶 None 但整頁不崩
        assert body["account"] is None

        # Bot 艦隊計數
        assert body["bots"]["total"] == 2
        assert body["bots"]["active"] == 1
        assert len(body["bots"]["list"]) == 2

        # 自動化規則鍵齊全
        for k in ("enabled", "ev_threshold", "winrate_threshold", "max_bots",
                  "cash_per_bot", "scan_hour"):
            assert k in body["automation"], body["automation"]

        # 熔斷區塊鍵齊全（離線時 best-effort 給 None，但鍵要在）
        assert "tripped" in body["circuit_breaker"]

        # 決策倒序（後種的 id=2 在前）
        assert len(body["decisions"]) == 2
        assert body["decisions"][0]["id"] == 2


def test_overview_account_present_when_online(monkeypatch, tmp_path):
    """get_account 正常 → account 帶現金等欄位。"""
    import backend.routers.company as company_mod

    fake = SimpleNamespace(status="ACTIVE", cash="1000", buying_power="2000",
                           portfolio_value="3000")
    monkeypatch.setattr(company_mod.alpaca_client, "get_account", lambda: fake)

    with _client_with_db(tmp_path) as (client, TestingSession):
        resp = client.get("/company/overview")
        assert resp.status_code == 200, resp.text
        acc = resp.json()["account"]
        assert acc is not None
        assert acc["cash"] == "1000"
        assert acc["portfolio_value"] == "3000"
