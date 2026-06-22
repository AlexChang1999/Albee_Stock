# Step 01 — collector 通電 + 禮貌驗收

## 原目標錨點
README 壹「收料段：程式在、開關預設關、半手動」。本步**不寫新功能**，是把 Phase 10 step-04
已蓋好的蒐集員正式通電並驗收行為（之前從未在真 feed 上長跑過）。

## 涉及檔
- `.env`（使用者自填，不進 git）：`COLLECTOR_RSS_FEEDS`、`COLLECTOR_INTERVAL_MIN`
- `backend/services/collector.py`（只准修 bug，不准加 feature）
- `docs/guides/`：新增 `collector-feeds-guide.md`（推薦 feed 清單 + 禮貌守則）
- `tests/test_collector.py`（補缺的邊界測試，若有）

## Step
1. 挑 2~3 個量化/交易策略 RSS 來源（公開、有 RSS、robots 允許），寫進 guide 文件
   （附「怎麼確認 robots.txt 允許」的檢查步驟）。
2. 本機 `.env` 填 feeds + `COLLECTOR_INTERVAL_MIN=60`，跑一輪 `run_collector_scan()`，
   驗：有入庫、`dedup_rows` 防重複生效、再跑一輪 upsert 不重複。
3. 觀察 3~7 天：收件匣（CollectorPage）素材量、垃圾率（廣告/無關文）。
4. 發現 parser 壞掉/編碼炸/來源改版 → 修 bug + 補測試（一 bug 一 commit）。

## DoD
- 真 feed 連跑 3 天無未捕捉例外；同一文章不重複入庫。
- guide 文件含：推薦來源、robots 檢查步驟、`.env` 設定範例、「關掉就回到全關」說明。
- `docs/README.md` 索引補 guide 那列。

## 邊界
- 不加新 parser 類型、不加新來源型態（HTML 爬蟲擴充屬 scope creep）。
- 來源打不到 = 跳過 + log，不重試轟炸。
