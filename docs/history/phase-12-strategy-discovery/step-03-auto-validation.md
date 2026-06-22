# Step 03 — 候選自動批次驗證（OOS 閘排程化）

## 原目標錨點
README 壹「候選 → 驗證：有管線、要人逐筆按」。把 `evolution.validate_candidate`
（walk-forward OOS → validated/rejected）排程化：candidate 自動進閘，不等人按。

## 涉及檔
- 新 `backend/services/auto_validate.py`（薄薄一層批次器，**不准改 evolution 的判準**）
- `backend/config.py`：`AUTO_VALIDATE_ENABLED`（預設 false）、`AUTO_VALIDATE_BATCH_SIZE`（預設 3）、
  `AUTO_VALIDATE_HOUR`（預設 8，discovery 之後）
- 排程掛載（同 step-02 體例）
- 新 `tests/test_auto_validate.py`

## Step
1. `run_auto_validate(db)`：取 `status=candidate` 的 StrategyKnowledge 至多 BATCH_SIZE 筆，
   逐筆呼叫**既有** `evolution.validate_candidate`（含其 OOS 判準與 `is_layer_worth_it` verdict），
   結果自然流轉 validated/rejected。
2. 失敗隔離：單筆炸（資料抓不到/回測例外）→ 標記 skip 原因、繼續下一筆，**不放行也不誤殺**
   （維持 candidate，下批重試；連續 3 次失敗才標 rejected + reason）。
3. 排程：每日 `AUTO_VALIDATE_HOUR`；開關預設關。
4. 測試：monkeypatch validate_candidate —— 通過/拒絕/丟例外 三情境；批次上限生效；
   連續失敗 3 次才 rejected；重跑不重複驗證已 validated/rejected 的。

## DoD
- 全測綠；關閉時行為不變。
- candidate 隔日自動變 validated 或 rejected，LibraryPage 看得到。
- 回測批次跑在排程時段內結束（BATCH_SIZE 控制），不影響白天操作。

## 邊界
- **判準零修改**：通過門檻全在 evolution/validation 既有程式，本步只做排程與失敗隔離。
- 不自動晉升 curated（人在迴路鐵則）。
- 驗證用資料走 `market_data`（鐵則：同資料源同回看）。
