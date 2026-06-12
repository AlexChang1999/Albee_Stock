# 步驟 8 — 決策審計軌跡

> 修 **P8**（無決策審計軌跡）。回到 [Phase 6 索引](README.md)。

## 目標

讓每一次 Bot 檢查都留下「**為何在這個時點買 / 賣 / 不動**」的持久紀錄。自動跑真錢的系統，
必須能事後查驗每個決定；這份紀錄也是日後餵 LLM 做檢討的素材。

## 問題（現況）

執行流程全靠 `print()` + `notify()`，只有 `last_checked_at` 一個時間戳。
`TradeLog` 只在「真的成交」時才寫——**「觀望、續抱、休市跳過、購買力不足」這些「沒成交但有決策」的時點完全沒紀錄**。
無法回答「昨天 10:35 為什麼沒進場」這種關鍵問題，也無法量化策略在實盤的訊號分布。

## 改動

1. 新增 model **`DecisionLog`**（`backend/models/decision_log.py`）：
   - 欄位：`id`、`bot_id`、`symbol`、`signal`（buy/sell/hold）、`reason`（策略 / 風控原因字串）、
     `price`（當下參考價）、`action`、`created_at`。
   - `action` 列舉：`bought` / `sold` / `hold` / `skipped_market_closed` / `skipped_no_buying_power` / `skipped_circuit_breaker`。
   - 走 **Alembic** 遷移（`render_as_batch=True`，沿用既有慣例）。
2. **`backend/bots/bot_manager.py`** 的 `run_bot_once` 各分支都寫一筆 `DecisionLog`：
   休市跳過、購買力不足（步驟 5）、熔斷（步驟 9）、買進、出場（風控 / 策略賣）、續抱、空手觀望。
3. 新增 **`GET /bots/{id}/decisions`**（`backend/routers/bots.py`，回最近 N 筆，預設 50）。
4. （本步只建表 + 寫入 + 端點；把 decisions 餵進 `chat` / `postmortem` 讓 LLM 讀，留待後續，不在本步。）

## 重用既有

- `TradeLog` 的 model / 寫入慣例（`_record_and_notify` 同款寫法）。
- 既有 Alembic batch 遷移範例（`alembic/versions/` 內現成的 add-column 遷移）。

## 測試

- `tests/test_decision_log.py`（新）：跑 `run_bot_once` 各分支，驗證寫對 `action` / `signal` / `reason`。
- `GET /bots/{id}/decisions` 往返（建幾筆 → 查回來、依時間倒序、數量上限）。

## 驗收

- 啟動 Bot 跑幾輪後，`GET /bots/{id}/decisions` 能看到每個時點的決策與原因（含沒成交的觀望 / 跳過）。
- 搭配 [步驟 6](step-06-scheduler-refetch.md)：改風控後，下一筆 decision 的 `reason` 反映新門檻。
