"""
Albee Stock — 自家 MCP server（採納自 QuantDinger 的 quantdinger-mcp）
=====================================================================
一支 stdio MCP server，把後端的 Agent Gateway（/api/agent/v1/*）包成 MCP 工具，
讓 Claude Code / Cursor 等能用自然語言驅動我們的回測 / 策略 / 知識庫查詢與 paper 下單。

定位（與既有 Alpaca 官方 MCP 區分）：
- Alpaca MCP＝直接操作券商帳戶（查帳戶、下測試單）。
- 本 MCP＝操作「我們自己的研究系統」（跑我們的策略回測、讀我們的知識庫 / 機會清單）。

設計刻意「薄」：工具只轉發 HTTP 給 Gateway，所有業務邏輯與安全閘都在後端
（token 驗證、預設 paper、審計）。MCP 這層不重寫任何規則，只負責把參數帶過去。

環境變數：
- ALBEE_API_URL：後端網址（預設 http://127.0.0.1:8000）。
- ALBEE_AGENT_TOKEN：對應後端 .env 的 AGENT_API_TOKEN（沒設則所有工具回 Gateway 503 提示）。

啟動 / 註冊（見 mcp_server/README.md）：
    claude mcp add albee --scope local \
      --env ALBEE_API_URL=http://127.0.0.1:8000 \
      --env ALBEE_AGENT_TOKEN=你的token \
      -- python mcp_server/server.py
"""

import os

import requests
from mcp.server.fastmcp import FastMCP

API_URL = os.getenv("ALBEE_API_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.getenv("ALBEE_AGENT_TOKEN", "")
BASE = f"{API_URL}/api/agent/v1"
TIMEOUT = 120  # 回測可能跑數十秒，給寬一點

mcp = FastMCP("albee-stock")


def _headers() -> dict:
    return {"Authorization": f"Bearer {TOKEN}"}


def _get(path: str, params: dict | None = None) -> dict | list:
    r = requests.get(f"{BASE}{path}", headers=_headers(), params=params or {}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    r = requests.post(f"{BASE}{path}", headers=_headers(), json=body, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


@mcp.tool()
def list_strategies() -> dict:
    """列出 Albee Stock 可用的交易策略（代號 + 中文名）與各策略的合法參數 schema。"""
    return _get("/strategies")


@mcp.tool()
def run_backtest(
    strategy: str,
    symbol: str,
    params: dict | None = None,
    days: int = 365,
    initial_cash: float = 10000.0,
) -> dict:
    """
    用 Albee Stock 的回測引擎跑一次回測（含成本 + 隔日成交 + 樣本外，回測=實盤同路徑）。

    :param strategy: 策略代號（先用 list_strategies 取），例如 "rsi" / "ma_crossover"。
    :param symbol: 美股代號，例如 "AAPL"。
    :param params: 策略參數（依 list_strategies 的 param_specs 填），例如 {"period":14}。
    :param days: 回看天數。
    :param initial_cash: 初始資金。
    """
    return _post("/backtest", {
        "strategy": strategy, "symbol": symbol, "params": params or {},
        "days": days, "initial_cash": initial_cash,
    })


@mcp.tool()
def backtest_history(limit: int = 20) -> list:
    """列出最近的回測歷史，依期望值 EV 由高到低。"""
    return _get("/backtest/history", {"limit": limit})


@mcp.tool()
def get_account() -> dict:
    """查 Alpaca 帳戶（現金 / 購買力 / 組合淨值；標示 paper 還是真錢環境）。"""
    return _get("/account")


@mcp.tool()
def list_bots() -> list:
    """列出所有交易 Bot（代號 / 策略 / 標的 / 啟用狀態）。"""
    return _get("/bots")


@mcp.tool()
def list_opportunities(limit: int = 50) -> list:
    """列出常駐探勘的機會清單（依樣本外 EV 由高到低）。"""
    return _get("/opportunities", {"limit": limit})


@mcp.tool()
def list_knowledge(limit: int = 50) -> list:
    """列出策略知識庫（已驗證 / 策展過的策略）。"""
    return _get("/knowledge", {"limit": limit})


@mcp.tool()
def submit_order(symbol: str, qty: float, side: str) -> dict:
    """
    送市價單（預設 paper）。要碰真錢須後端三道閘齊開
    （實盤網址 + ALLOW_LIVE_TRADING + AGENT_LIVE_TRADING_ENABLED），否則伺服端回 403 拒絕。

    :param symbol: 美股代號。
    :param qty: 股數。
    :param side: "buy" 或 "sell"。
    """
    return _post("/orders", {"symbol": symbol, "qty": qty, "side": side})


if __name__ == "__main__":
    mcp.run()  # 預設 stdio transport
