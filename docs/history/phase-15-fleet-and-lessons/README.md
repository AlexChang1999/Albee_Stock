# Phase 15 — 每股多策略艦隊落地 + 決策教訓 Log

> 狀態：✅ 已落地（2026-06-23）。承 Phase 14（公司可操作化）。全程 paper、不開任何排程旗標、不碰真錢雙閘。

## 原目標（使用者三訴求）

1. **「每檔股票各一個 bot」不是要的** —— 想要每股用 **5+ 已驗證策略**並存虛擬交易，找最佳模型。
2. **決策要記「為何買/賣 + 價格 + 量」**，下次能**讀懂教訓**。
3. **「300 秒輪詢是不是太久？」**

## 診斷（為什麼之前沒發生）

- **多策略能力早就有，只差一個批次入口**：`Bot` 模型無 symbol 唯一限制（同股可掛 N 個不同策略 bot），
  `StockArenaPage` 也能部署——但只能逐列點一次建一個；現在在跑的 bot 是當初一檔一檔手建的，所以維持 1/股。
- **決策 Log 缺脈絡**：`DecisionLog` 已存 `signal/reason/price/action`，但**沒有量、沒有股數、沒有指標快照**，
  看不到觸發當下的數字。
- **300 秒不是給手動 bot 用的**：`AUTO_DEPLOY_KNOWLEDGE_CHECK_INTERVAL=300` 只用於大型自動艦隊
  （5 策略 × 38 檔 = 190 bot）防 Alpaca 免費 200/min 限流；手動部署的 bot 本來就 60 秒。

## 做了什麼

### A. 每股多策略艦隊（訴求 1 + 3）
- `frontend/src/pages/StockArenaPage.jsx`：排行榜上方加批次列 `部署前 N 名`（預設 5）／`每單金額`／`輪詢秒數`（預設 60）。
- `deployTopN()`：取排行榜前 N，逐筆 `createBot({..., check_interval_sec})` + `startBot`；
  **去重**——先 `getBots()` 比對同 `symbol+strategy` 已存在就跳過，回報「N 建立 / M 跳過」。複用既有 API，零新後端。
- **300 秒結論**：維持（只自動艦隊用），改為部署時可自選輪詢秒數；止損是券商端 GTC 即時成交、不受輪詢延遲影響
  （`BROKER_STOP_ENABLED=true`）。

### B. 決策教訓 Log（訴求 2，最深層）
- `backend/models/decision_log.py`：加 `volume` / `qty` / `indicators`（JSON）三欄。Alembic `4810c1ec25d9`（已套 Neon）。
- `backend/bots/bot_manager.py`：`_run_strategy`/`_run_adaptive_strategy` 改回 `(signal, reason, ctx)`；
  ctx 帶 df 末根 `volume` + 指標快照（**複用 `services.indicator_overlays.compute_overlays` 取各序列末根**，零策略改寫）。
  `_record_decision` 加 `volume/qty/indicators`，各分支補傳（買進帶 qty、風控賣出帶 qty、券商端回填帶 qty）。
  *容錯*：call site 用 `signal, reason, *rest` 解包——舊測試 monkeypatch 回 2-tuple 仍相容。
- `backend/routers/bots.py`：`get_bot_decisions` 序列化補三鍵。
- `backend/routers/chat.py`：新端點 `POST /chat/bot-lessons`——撈該 Bot 決策史（含量/股數/指標）請本機 LLM 產覆盤教訓；
  複用既有 `_get_client`/`_cloud_blocked`（**雲端外送閘**）/`_complete`/`_friendly_err`，只讀資料不下單。
- `frontend/src/pages/DecisionsPage.jsx`：表格加「量／股數」欄 + 指標 tooltip + 頭部「📖 讀教訓」鈕（`api.getBotLessons`）。

## 驗收

- 後端：`tests/test_bot_lessons.py`（端點閘 400/404 + stub 成功）、擴 `tests/test_decision_log.py`
  （寫入量/股數/指標、`_run_strategy` 回 3-tuple）；全套件 pytest 綠。
- 前端：`StockArenaPage.test.jsx`（批次部署 + 去重）、`DecisionsPage.test.jsx`（量欄 + 讀教訓）；vitest 全綠、`npm run build` 過。
- Live：個股擂台「部署前 5 名」→ Dashboard 出現 5 個同股 paper bot（去重生效）；對 bot 跑一輪 → 決策審計頁顯示量/股數/指標；
  「讀教訓」回 LLM 摘要。

## 誠實邊界
- 指標快照只在「有 df 的策略決策」時有值；風控出場（止損/追蹤止損）無 df → volume/indicators 為 None，reason 已說明風控規則。
- 「讀教訓」需本機 Ollama 在線；連不上時端點優雅回提示（`_friendly_err`），不誤殺。
- 不改任何 `*_ENABLED` 預設；批次部署一律 paper bot。
