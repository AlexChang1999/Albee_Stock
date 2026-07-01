# Albee Stock — 自家 MCP server

把後端的 **Agent Gateway**（`/api/agent/v1/*`）包成 MCP 工具，讓 Claude Code / Cursor
能用自然語言驅動我們自己的研究系統：跑回測、查策略 / 知識庫 / 機會清單、下 paper 單。

> 採納自 [QuantDinger](https://github.com/brokermr810/QuantDinger) 的 Agent Gateway + MCP 設計。
> 與既有的 **Alpaca 官方 MCP** 分工：Alpaca MCP 直接操作券商帳戶；本 MCP 操作「我們自己的系統」
> （我們的策略回測、我們的知識庫）。

## 前置

1. 後端 `.env` 設好 `AGENT_API_TOKEN`（產一把）：
   ```
   python -c "import secrets;print(secrets.token_urlsafe(32))"
   ```
   貼進 `.env` 的 `AGENT_API_TOKEN=`。**絕不 commit。**
2. 裝依賴並啟動後端：
   ```powershell
   venv\Scripts\python.exe -m pip install -r requirements.txt
   venv\Scripts\uvicorn.exe backend.main:app --reload
   ```

## 註冊到 Claude Code

```
claude mcp add albee --scope local \
  --env ALBEE_API_URL=http://127.0.0.1:8000 \
  --env ALBEE_AGENT_TOKEN=你剛產的token \
  -- python mcp_server/server.py
```

> Windows 上 `python` 請指到 venv：可改用 `venv\Scripts\python.exe`。
> `ALBEE_AGENT_TOKEN` 必須等於後端 `.env` 的 `AGENT_API_TOKEN`，否則工具會收到 401。

## 工具一覽

| 工具 | 作用 |
|------|------|
| `list_strategies` | 列可用策略 + 合法參數 schema |
| `run_backtest` | 跑一次回測（含成本 + 隔日成交 + OOS） |
| `backtest_history` | 最近回測歷史，依 EV 排序 |
| `get_account` | Alpaca 帳戶（現金 / 購買力 / paper 或真錢） |
| `list_bots` | 所有交易 Bot（唯讀） |
| `list_opportunities` | 常駐探勘機會清單 |
| `list_knowledge` | 策略知識庫 |
| `submit_order` | 送市價單（**預設 paper**） |

## 安全

- 所有業務邏輯與安全閘都在後端，MCP 這層只轉發 HTTP、不重寫規則。
- `submit_order` 預設只能下 paper 單。要碰真錢須後端三道閘齊開：實盤網址 +
  `ALLOW_LIVE_TRADING=true` + `AGENT_LIVE_TRADING_ENABLED=true`，否則伺服端回 403。
- 每筆呼叫都落後端 `agent_audits` 審計表（append-only）。
