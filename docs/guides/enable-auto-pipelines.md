# 開啟自動管線 runbook（自動選標的 / 策略點子探勘）

> 兩條自動管線**程式都已實作、但開關預設全關**（避免家用機亂跑、耗 CPU、外送資料）。
> 這份說明「想開的時候改哪幾個 `.env` 開關、怎麼驗證有跑起來」。
> **預設 OFF 是有意的**——你決定何時開。晉升 curated 策略、自動部署 Bot 上真錢仍須人工，
> 安全雙閘（`ALLOW_LIVE_TRADING`）一律不動。

---

## 先搞懂：有兩條不同的管線

很多人把「市場蒐集員」想成「蒐集完就自動回測選標的」，其實是**兩條獨立的線**：

| 線 | 在做什麼 | 產出 | 餵給誰 |
|----|----------|------|--------|
| **A. 自動選標的**（screener / opportunity_scan） | 盤中對 watchlist 逐檔跑回測，挑最佳策略+標的 | `opportunities` 表（機會清單） | 你看戰情頁 → 決定要不要建 Bot |
| **B. 策略點子探勘**（collector → discovery → auto_validate） | RSS 收策略點子 → LLM 產候選參數 → 自動 OOS 驗證 | `strategy_knowledge` 知識庫（candidate→validated） | 你審核 → 人工晉升 curated |

**你說的「蒐集後自動回測+選標的」＝線 A**。線 B 是「找新策略想法」，不是選標的。

---

## 線 A：開「自動選標的」（screener / opportunity_scan）

對 `SCREENER_WATCHLIST` 裡每檔股票，盤中每隔幾分鐘自動跑回測、挑 OOS EV 最高的策略，
寫進 `opportunities` 表，超過門檻提醒一次。

### 開啟步驟

1. `.env` 確認 watchlist 非空（預設已有幾檔）：
   ```
   SCREENER_WATCHLIST=AAPL,MSFT,NVDA,TSLA,AMD,GOOGL
   ```
2. 掃描間隔由 **DB 的 `automation_config.scan_interval_min`** 決定（不是 `.env`）。
   要 > 0 才會掛排程。可在戰情頁/自動化面板設定，或保持預設 30 分鐘。
3. 重啟後端。`main.py` 啟動時讀 `automation_config` 掛 `schedule_opportunity_scan`。

### 驗證有跑起來

- **盤中**（美股開盤時段）才會真的掃；收盤直接跳過、不空轉。
- 查 `opportunities` 表有沒有新列（或戰情頁「常駐機會」清單）。
- 後端 log 應有掃描紀錄；`job_run_logs` 表記每次排程執行。

> 注意：line A 已經是「自動回測 + 自選標的」。它**不會自動建 Bot 下單**——
> 自動部署是另一個開關（`AUTO_DEPLOY_ENABLED`，預設 false，建議維持人工核准）。

---

## 線 B：開「策略點子探勘」（collector → discovery → auto_validate）

RSS 收策略文章 → 本機 Ollama LLM 判讀「在講哪種策略、建議什麼參數」→ 自動跑 OOS 驗證 →
流轉成 validated / rejected。需要本機 Ollama。

### 開啟步驟

1. 先備好 LLM：`ollama serve` + `ollama pull llama3.1`（或 `.env` 指向雲端 LLM 並設
   `LLM_ALLOW_CLOUD=true`）。
2. `.env` 設四個開關：
   ```
   COLLECTOR_RSS_FEEDS=https://feed1...,https://feed2...   # 來源清單見 collector-feeds-guide.md
   COLLECTOR_INTERVAL_MIN=180        # 收料間隔（分鐘），0=關
   DISCOVERY_ENABLED=true            # 開 LLM triage（每日 DISCOVERY_HOUR=7 跑一批）
   AUTO_VALIDATE_ENABLED=true        # 開自動 OOS 驗證（每日 AUTO_VALIDATE_HOUR=8 跑一批）
   ```
3. 重啟後端。`schedule_collector_scan` / `schedule_discovery` / `schedule_auto_validate`
   只在對應開關開啟時才掛排程。

### 驗證有跑起來

- `raw_strategy_finds` 表有沒有新素材（收料成功）。
- 隔天 7 點後 `strategy_knowledge` 有沒有 `status=candidate` 的新列（discovery 成功）。
- 隔天 8 點後 candidate 有沒有流轉成 `validated` / `rejected`（auto_validate 成功）。
- 戰情頁的「探勘漏斗」卡 + 心跳「待審」行會反映進度。

### 鐵則（不會自動跨過的線）

- **晉升 curated 只能由人觸發**。自動管線最多把候選驗到 `validated`，curated（正式策略庫）
  必須你在知識庫頁手動晉升。
- LLM 預設本機 Ollama、外送閘 `LLM_ALLOW_CLOUD=false`，防策略資料外洩。

---

## 一張表：要開什麼

| 想要 | 改哪 | 預設 |
|------|------|------|
| 自動回測選標的（線 A） | `SCREENER_WATCHLIST` 非空 + DB `scan_interval_min > 0` | watchlist 有值、間隔 30 |
| 自動找新策略點子（線 B） | `COLLECTOR_RSS_FEEDS` + `COLLECTOR_INTERVAL_MIN` + `DISCOVERY_ENABLED` + `AUTO_VALIDATE_ENABLED` | 全關 |
| 自動建 Bot 下單 | `AUTO_DEPLOY_ENABLED=true`（**高風險，建議不開**） | false |
| 真錢下單 | `ALPACA_BASE_URL` 實盤網址 + `ALLOW_LIVE_TRADING=true`（雙閘，**勿手滑**） | Paper |

## 相關文件

- [`collector-feeds-guide.md`](collector-feeds-guide.md)：RSS feed 來源怎麼挑、robots 檢查。
- [`cloud-local-division.md`](cloud-local-division.md)：雲端／地端誰跑排程的紅線（**勿雙開**）。
- [`../reference/human-vs-ai-operation.md`](../reference/human-vs-ai-operation.md)：跑真錢前必讀。
