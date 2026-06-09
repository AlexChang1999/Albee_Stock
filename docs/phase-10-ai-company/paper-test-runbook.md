# Phase 10 — 正式 Paper 測試 Runbook（全公司端到端）

> 目標：在**模擬交易（Paper）**下，把「AI 交易公司」整條鏈跑一遍——常駐探勘 → 機會清單 →
> （收集員收料 / 政治員煞車）→ 建 Bot 監聽 → Paper 下單 → 決策審計 → 熔斷 → 董事會核准。
> 這是**上真錢前的最後驗證**。全程 `ALLOW_LIVE_TRADING=false`、`ALPACA_BASE_URL` 為 paper。
>
> 節奏：**先本地 smoke（階段 0，不等開盤）→ 擇日跨夜跨整場（階段 1~3，美股開盤＝台灣深夜）。**
> 跑真錢前另讀 [`../human-vs-ai-operation.md`](../human-vs-ai-operation.md)。

---

## 前置（一次性）

`.env`（不進 git）至少要有：

```
ALPACA_API_KEY=PK...            # Paper 金鑰，PK 開頭、約 20 碼
ALPACA_SECRET_KEY=...           # 約 40 碼
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALLOW_LIVE_TRADING=false        # ★ 保持 false（真錢防線）

# LLM（情緒 / 政治判讀要用；不裝則該層自動跳過、不阻斷）
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.1
LLM_ALLOW_CLOUD=false

# 全公司端到端才需要：
SCAN_INTERVAL_MIN=30            # 常駐探勘間隔
COLLECTOR_RSS_FEEDS=https://www.reddit.com/r/algotrading/.rss   # 想開收集員才填
COLLECTOR_INTERVAL_MIN=60       # 0=關
POLITICAL_ENABLED=false         # 政治員 bridge 預設關（先別接進下單）
# 政治員連真資料才需要（沒有就留空，runner 會印指引後結束）：
POLITICAL_DISCORD_TOKEN=
POLITICAL_CHANNEL_ID=
```

新 Phase 10 設定的完整說明見 `.env.example` 的「AI 交易公司（Phase 10）」段。

---

## 階段 0｜起飛前檢查（不需開盤，現在就能做）

| # | 檢查項 | 指令 / 動作 | 通過標準 |
|---|--------|-------------|----------|
| 0.1 | 依賴齊全 | `venv\Scripts\python.exe -m pip install -r requirements.txt` | 無錯（含 beautifulsoup4 / discord.py） |
| 0.2 | DB schema 最新 | `venv\Scripts\alembic.exe upgrade head` | head = `f2a3b4c5d6e7`（political_events） |
| 0.3 | 全測試綠 | `venv\Scripts\python.exe -m pytest tests\ -q` | 全 pass（目前 322） |
| 0.4 | 前端測試綠 | `cd frontend && npm run test` | 全 pass（目前 89） |
| 0.5 | Alpaca Paper 通 | `venv\Scripts\python.exe backend\test_connection.py` | 印出帳戶 status / 購買力 |
| 0.6 | Ollama 通（選） | `ollama serve` 後另開窗 `ollama run llama3.1 hi` | 有回應；連不上則情緒/政治層會自動跳過 |
| 0.7 | 後端起得來 | `start_backend.bat`（或 `uvicorn backend.main:app --reload`） | 看到「🚀 啟動完成（模擬交易模式：True）」 |
| 0.8 | 戰情 / 新頁打得開 | 開前端，點 公司戰情 / 因子報表 / 市場蒐集員 / 政治專討員 / 董事會核准 | 各頁有載入、無紅色錯誤 |
| 0.9 | 安全標示正確 | 看 Header / `/status` | `is_paper=true`、`live_armed=false`（沒有實盤紅橫幅） |

> 階段 0 的 endpoint smoke 也可不真的掛 Bot：`/status`、`/company/overview`、`/opportunities`、
> `/collector/finds`、`/political/events`、`/political/risk` 都該回 200 且不下任何單。

---

## 階段 1｜核心交易迴路（擇日跨開盤場）

1. **建 1~2 個 Paper Bot**：前端 監控中心 / AI 探勘 一鍵部署，或 `POST /bots`。標的選 watchlist 內、流動性好的。
2. **掛監聽**：啟動 Bot（每 N 秒檢查）。確認 `is_active=true`、排程有掛上。
3. **盤中觀察**（美股開盤後）：
   - `決策審計` 頁應持續長出 DecisionLog（**含沒成交的觀望/跳過**，不是只有成交才有紀錄）。
   - 觸發進場 → `交易紀錄` 出現 Paper 成交；出場（止盈/止損/追蹤止損）也要看得到。
4. **熔斷驗證**（選）：把 `PORTFOLIO_MAX_DRAWDOWN_PCT` 暫時調小，確認回撤超標時**擋新買進、但既有持倉出場照常**。

**通過標準**：Bot 能在 Paper 自動下單、每個決策都有審計軌跡、止盈止損會出場、熔斷只擋進不擋出。

---

## 階段 2｜新前台端到端（與階段 1 同場）

- **常駐探勘（step-02）**：盤中每 `SCAN_INTERVAL_MIN` 分鐘，`機會清單`/`公司戰情` 會更新候選（OOS EV 排序）；超門檻發一次通知後翻 seen（不洗頻）。
- **因子報表（step-03）**：`因子報表` 頁累積 watchlist 各檔的 7 因子 + regime 快照；可匯出 CSV。
- **市場蒐集員（step-04）**：設了 `COLLECTOR_RSS_FEEDS` + `COLLECTOR_INTERVAL_MIN>0` 後，`市場蒐集員` 收件匣會進新料；標記 triaged/built/discarded 流轉正常。**收回來的點子不會自動上線**。
- **政治專討員（step-05）**：`POLITICAL_ENABLED=false` 時 `/political/risk` 一律 `size_factor=1.0`（放行、不影響下單）——先這樣。要連真資料需先有 Discord 鏡像頻道（見下「待辦」）。

**通過標準**：四個前台都有真資料流動、且**都沒有繞過 OOS 閘 / 人工核准 / 實盤雙閘**。

---

## 階段 3｜複盤 + 董事會核准（收盤後）

1. **對帳**：抽幾筆 Paper 成交，對回 `決策審計` 的 signal/reason/price——確認「回測看到的 EV」與「Paper 實況」沒明顯分岔（同資料源 + 含成本 + 隔日成交）。
2. **董事會核准（step-06）演練**：對表現好的 Bot 走 `董事會核准` 頁 propose→approve 流程。
   ⚠️ **核准只是多一道人工閘，UI 不放行真錢**；真錢仍須改 `.env`（實盤網址 + `ALLOW_LIVE_TRADING=true`）由 alpaca 雙閘把關。本次 paper 測試**不**開真錢。

**通過標準**：EV ≈ Paper 實況、核准流程走得通、且確認沒有任何路徑能繞過真錢雙閘。

---

## 已知前提 / 風險

- **政治員真資料來源**：Discord bot 只能讀「它所在的頻道」，不會自己去 Truth Social / X 抓川普。
  要連真資料，需先有一個「把川普貼文同步進來的鏡像頻道」（RSS→webhook / 鏡像 bot），再設 token。
  沒有就維持 `POLITICAL_ENABLED=false` + skeleton，不影響其餘測試。
- **政治「貼文 → 漲跌」非可驗證**：只當煞車（縮部位/不開新倉），永遠不當主進場訊號、不放大部位。
- **收集員**：尊重 robots / rate limit / ToS；best-effort 連不上不阻斷其他功能。
