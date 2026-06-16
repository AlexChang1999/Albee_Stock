"""
煙霧測試（Smoke Test）
======================
驗「整台機器開得起來、核心端點真的回得了話」——不是驗每個零件的細部邏輯
（那是其他 test_*.py 單元測試的事），而是當作**上線前/部署後的最後一道關卡**：

  - L1：FastAPI 起得來（lifespan 觸發 init_db + scheduler 掛載不爆）、
        核心健康端點與「不需金鑰的讀端點」都回 200。
  - L4：缺 Alpaca 金鑰時優雅降級（/positions 回 [] 而非 500）。

用法（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest -m smoke -q          # 只跑煙霧測試
    venv\\Scripts\\python.exe -m pytest tests/ -q            # 全套（含煙霧）

整合層（需真金鑰/真網路）的測試預設**跳過**，要驗才開：
    set RUN_INTEGRATION_SMOKE=1 && pytest -m smoke -q        # Windows
    RUN_INTEGRATION_SMOKE=1 pytest -m smoke -q               # bash

備註：本檔沿用 tests/conftest.py 的 _disable_boot_side_effects fixture
（自動關開機補跑），所以不會真打網路 / 發通知 / 跑回測。
"""

import os

import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.smoke  # 整檔標記 smoke，可用 pytest -m smoke 單獨跑


@pytest.fixture(scope="module")
def client():
    """起一個 TestClient。

    with 區塊會觸發 app 的 lifespan：init_db（建表）→ acquire_scheduler_lock（leader 選舉）
    → _resume_active_bots → 掛各排程 job。光是能順利進出這個 with，就驗了「啟動階段不爆」。
    scope="module"：整個檔案共用一個 client，省去每個測試重啟 app 的成本。
    """
    with TestClient(app) as c:
        yield c


# ---------- L1：核心健康端點 ----------
def test_root_health(client):
    """GET / 是 deploy.sh 健檢打的同一個端點——服務活著的最低標準。"""
    r = client.get("/")
    assert r.status_code == 200, r.text
    assert "paper_trading" in r.json()  # 確認回的是預期的健康 JSON


def test_status(client):
    """GET /status 回交易環境三旗標——驗設定讀得到、實盤雙閘狀態看得見。"""
    r = client.get("/status")
    assert r.status_code == 200, r.text
    assert {"is_paper", "allow_live", "live_armed"} <= r.json().keys()


# ---------- L1：不需外部金鑰的讀端點都應回 200 ----------
# 這些端點要嘛純讀 DB、要嘛設計成無金鑰時優雅降級。任何一個回非 200，
# 代表該 router 掛了 / DB 連不上 / 設定爆了——正是煙霧測試要抓的「啟動級故障」。
#
# 刻意**不放**的端點：
#   /account、/quotes/{symbol}、/bars/{symbol} —— 需真 Alpaca 金鑰且失敗回 400（見整合層）。
#   /ai-recommendations —— 會真跑一輪海選回測（重、慢、依資料源），不適合當煙霧。
READ_ENDPOINTS = [
    "/bots",
    "/trades",
    "/presets",
    "/backtest-runs",
    "/strategies",
    "/positions",  # 無 Alpaca 金鑰 → 優雅回 []（同時也是 L4 降級點）
    "/reminders",
    "/automation",
    "/factors",
    "/company/overview",
    "/explorations",
    "/knowledge",
    "/opportunities",
    "/promotions",
    "/political/events",
    "/political/risk",
    "/macro/series-list",
    "/collector/finds",
]


@pytest.mark.parametrize("path", READ_ENDPOINTS)
def test_read_endpoints_respond(client, path):
    r = client.get(path)
    assert r.status_code == 200, f"{path} → {r.status_code}: {r.text[:200]}"


# ---------- L4：缺金鑰優雅降級 ----------
def test_positions_degrades_without_key(client):
    """無 Alpaca 金鑰時 /positions 應回空 list 而非爆 500（alpaca_client 內部吞例外）。"""
    r = client.get("/positions")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


# ---------- 整合層：需真金鑰 / 真網路，預設跳過 ----------
_INTEGRATION = pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_SMOKE"),
    reason="需真外部服務；設 RUN_INTEGRATION_SMOKE=1 才跑",
)


@_INTEGRATION
def test_account_reachable(client):
    """有真 Alpaca 金鑰時，/account 應連得上並回 200（含 cash 欄位）。"""
    r = client.get("/account")
    assert r.status_code == 200, r.text
    assert "cash" in r.json()


@_INTEGRATION
def test_quote_reachable(client):
    """有真金鑰時，/quotes/AAPL 應回得了即時報價。"""
    r = client.get("/quotes/AAPL")
    assert r.status_code == 200, r.text
