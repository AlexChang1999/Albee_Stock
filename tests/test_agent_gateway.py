"""
Agent Gateway 測試（採納自 QuantDinger 的 Agent Gateway + MCP）
===============================================================
驗證 /api/agent/v1/* 的三道安全閘與審計：
- 未設 AGENT_API_TOKEN → 503（Gateway 整組關）。
- token 不符 → 401。
- token 正確 → 端點可用，且呼叫有落審計。
- 實盤環境 + agent 未授權 → 下單回 403（不送單）。

刻意不觸發 app lifespan（不開排程 / 不連 Alpaca），並把會連外的部分 monkeypatch 掉，
讓測試純本機、快、可離線跑。

執行：venv\\Scripts\\python.exe -m pytest tests\\test_agent_gateway.py -q
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

from backend.config import settings
from backend.main import app
from backend.routers import agent

# 不用 with：避免觸發 lifespan（排程 / Alpaca 連線）。路由仍可直接呼叫。
client = TestClient(app)

TOKEN = "test-agent-token-123"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture(autouse=True)
def _no_audit_no_network(monkeypatch):
    """每個測試：把審計改成記憶體計數、把回測改成 stub，避免連 DB / 資料源。"""
    calls = []
    monkeypatch.setattr(agent, "_audit",
                        lambda db, endpoint, params, status, detail="": calls.append((endpoint, status)))
    agent._test_audit_calls = calls  # 讓測試讀得到
    yield


def test_gateway_disabled_returns_503(monkeypatch):
    """未設 AGENT_API_TOKEN → 整組 Gateway 關閉，回 503。"""
    monkeypatch.setattr(settings, "AGENT_API_TOKEN", "")
    r = client.get("/api/agent/v1/strategies")
    assert r.status_code == 503, r.text


def test_missing_or_wrong_token_returns_401(monkeypatch):
    """有設 token 但呼叫不帶 / 帶錯 → 401。"""
    monkeypatch.setattr(settings, "AGENT_API_TOKEN", TOKEN)
    assert client.get("/api/agent/v1/strategies").status_code == 401
    assert client.get("/api/agent/v1/strategies",
                      headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_strategies_ok_with_token(monkeypatch):
    """token 正確 → /strategies 回 200，含策略清單 + 參數 schema，且有落審計。"""
    monkeypatch.setattr(settings, "AGENT_API_TOKEN", TOKEN)
    r = client.get("/api/agent/v1/strategies", headers=AUTH)
    assert r.status_code == 200, r.text
    body = r.json()
    assert any(s["value"] == "script_breakout" for s in body["strategies"])
    assert "rsi" in body["param_specs"]
    assert ("/api/agent/v1/strategies", "ok") in agent._test_audit_calls


def test_backtest_runs_and_audits(monkeypatch):
    """token 正確 → POST /backtest 回 EV 結構，並落一筆審計（回測本身 stub 掉、不連資料源）。"""
    monkeypatch.setattr(settings, "AGENT_API_TOKEN", TOKEN)
    monkeypatch.setattr(agent, "run_backtest",
                        lambda **kw: {"expected_value": 42.0, "num_trades": 3, "strategy": kw["strategy_name"]})
    r = client.post("/api/agent/v1/backtest",
                    headers=AUTH, json={"strategy": "rsi", "symbol": "aapl", "days": 365})
    assert r.status_code == 200, r.text
    assert r.json()["expected_value"] == 42.0
    assert ("/api/agent/v1/backtest", "ok") in agent._test_audit_calls


def test_live_order_rejected_when_not_authorized(monkeypatch):
    """實盤環境 + agent 未獲授權 → 下單回 403（被擋，根本不送 alpaca）。"""
    monkeypatch.setattr(settings, "AGENT_API_TOKEN", TOKEN)
    monkeypatch.setattr(settings, "IS_PAPER", False)
    monkeypatch.setattr(settings, "AGENT_LIVE_TRADING_ENABLED", False)
    r = client.post("/api/agent/v1/orders",
                    headers=AUTH, json={"symbol": "AAPL", "qty": 1, "side": "buy"})
    assert r.status_code == 403, r.text
    assert ("/api/agent/v1/orders", "rejected") in agent._test_audit_calls


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
