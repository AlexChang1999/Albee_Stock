# Phase 2 — AI 推薦資料流（模式 A 海選）

> 目標：實作漏斗式篩選（量價篩 → Ollama 情緒打分），新增 `GET /ai-recommendations`，前端做
> 「AI 策略探勘」分頁卡片 + 一鍵 Deploy 建 Bot。
> 為何此階段：這是「雙軌 AI」模式 A 的本體，把人從繁瑣海選解放，是整個改版的價值核心。
> 回到總藍圖：[README.md](README.md)
>
> **狀態：✅ 已完成（2026-06-03）**。落地檔案：`backend/services/llm.py`（共用 LLM 低階工具 + 外送閘）、
> `backend/services/screener.py`（三層漏斗：量能→情緒→EV 海選，純函式好測）、
> `backend/routers/recommendations.py`（`GET /ai-recommendations` + 5 分鐘記憶體快取）、
> `config.py`/`.env.example` 加 `SCREENER_WATCHLIST`/`SCREENER_VOLUME_RATIO`/`SCREENER_TOP_N`；
> 前端 `components/RecommendationsPanel.jsx`（卡片 + 一鍵 Deploy）、`api.getRecommendations`、
> `App.jsx` 新增「AI 探勘」分頁。測試後端 88 綠、前端 31 綠。詳見 `CHANGELOG.md`。

---

## 一、現況

- 已有 EV 海選引擎：`backend/services/optimizer.py`（`run_auto_backtest()` 8 策略 × 參數網格，
  資料只抓一次共用 df，依 EV 排名）、`POST /auto-backtest`（`backend/routers/backtest.py`，
  每策略最佳組合各存一筆 `BacktestRun`、冠軍標 `is_good=True`）。
- 已有素材源：`backend/services/fundamentals.py`（新聞/財報）、`market_data.get_bars`（量價）。
- 已有 LLM 呼叫慣例：`backend/routers/chat.py`（讀 `LLM_BASE_URL`/`LLM_MODEL`、`LLM_ALLOW_CLOUD`
  外送閘把關）、`backend/services/explorations.py`（檔案記憶）。
- APScheduler：`backend/bots/bot_manager.py`（目前只排 Bot 定時檢查）。

## 二、缺口

1. **無漏斗第一層**：`auto-backtest` 是「給定一檔股票掃所有策略」，沒有「先用量價從一籃股票
   篩出候選」這層。需求要 `Volume > MA(20) × 2.5` 之類的技術 + 量能初篩。
2. **無漏斗第二層**：沒有把候選的新聞/財報交 Ollama 做情緒打分的邏輯。
3. **無 `GET /ai-recommendations` 端點**：海選結果目前綁在 `POST /auto-backtest`，非推薦清單。
4. **無「AI 策略探勘」獨立分頁**：現功能藏在 `AutoBacktestPanel`（單檔）與 `StrategyWorkbench`。
5. **無一鍵 Deploy**：目前要手動 `POST /bots`。

---

## 三、要做的事

### 3.1 後端漏斗式篩選（核心，算力優化）
新增 `backend/services/screener.py`（或擴 `optimizer.py`）：

- **第一層（低算力，純 pandas）**：對一籃 watchlist（可 `.env` 或常數定義候選股池），用
  `market_data.get_bars` 抓量價，篩出 `Volume > MA(20) × 2.5`（門檻可設定）等技術條件，
  收斂到 5~10 檔。
- **第二層（高算力，Ollama）**：只對第一層結果，取 `fundamentals.get_news` / `get_financials`
  摘要，沿用 `chat.py` 的 LLM 呼叫慣例做情緒打分（看多/看空/中性 + 分數）。受 `LLM_ALLOW_CLOUD`
  外送閘保護。
- **再對候選跑 EV 海選**：重用 `optimizer.run_auto_backtest`，得每檔最佳策略 + EV。

### 3.2 後端 API
- 新增 `backend/routers/recommendations.py`：`GET /ai-recommendations` 回 EV > 0 的建議清單
  （每筆：symbol、最佳策略 + 參數、EV/勝率/回撤等指標、情緒分數、建議配資）。
- 因屬高算力，建議結果**快取**（盤前掃描一次存起來；或排程預算，見 Phase 4）。

### 3.3 前端「AI 策略探勘」分頁
- `App.jsx` 新增分頁；新元件 `frontend/src/components/RecommendationsPanel.jsx`。
- 以卡片渲染建議：每張卡顯示標的 + 策略 + EV（大字）+ 勝率/回撤 + 情緒燈號。
- `api.js` 新增 `getRecommendations()`。

### 3.4 一鍵 Deploy
- 卡片上「一鍵部署」鈕 → 用該建議的策略/參數/標的/配資呼叫既有 `POST /bots`（`createBot`）
  → 自動 `POST /bots/{id}/start` 掛排程。
- 重用既有建立流程，不另造 Bot 建立邏輯。

---

## 四、接點（重用既有）

- EV 海選：`backend/services/optimizer.run_auto_backtest`。
- 量價：`backend/services/market_data.get_bars`。
- 情緒素材：`backend/services/fundamentals.py`。
- LLM 呼叫 + 外送閘：`backend/routers/chat.py` 慣例、`config.py` 的 `LLM_*`。
- 建 Bot + 掛排程：`backend/routers/bots.py`、`frontend/src/api.js` 的 `createBot`/`startBot`。

## 五、驗證

1. `GET /ai-recommendations` 回 EV > 0 卡片清單；第一層確實收斂到 5~10 檔（log 印篩選漏斗各層數量）。
2. Ollama 未啟動時優雅降級（回提示，不整支掛掉，比照 `chat.py`）。
3. 前端探勘分頁正確渲染卡片；點 Deploy 後 `GET /bots` 出現新 Bot 且已啟動排程。
4. 後端 pytest 綠（補 `tests/test_screener.py` 等）、前端 `npm test` 綠。

## 六、完成後

更新 `CHANGELOG.md`「未發布」`### 新增`：漏斗式篩選 + `/ai-recommendations` + 探勘分頁 + Deploy
（附改動檔名、測試數）。
