# Step 04 — 漏斗報表 + 待審提醒（人在迴路收口）

## 原目標錨點
README 貳：管線自動化後，人只剩一道閘（晉升 curated）。本步讓人「看得到漏斗、收得到提醒」，
免得 validated 堆著沒人理（自動化最常見的死法：沒人看）。

## 涉及檔
- `backend/routers/company.py`：overview 聚合加 `discovery_funnel` 區塊
  （raw new/triaged/built/discarded 計數 + knowledge candidate/validated/rejected/curated 計數 + 淘汰率）
- `backend/services/heartbeat.py`：每日心跳日報加一行「探勘漏斗：candidate X｜validated 待審 Y」
  （沿用 H2 既有日報，**不另開通知管道**）
- `frontend/src/pages/CompanyPage.jsx`：戰情頁加漏斗卡（吃 theme 色，不寫死 hex）
- 測試：`tests/test_company.py`（或既有戰情測試檔）+ 前端漏斗卡 Vitest

## Step
1. 後端：純查詢聚合（count by status 兩張表），無新 model、無遷移。
2. heartbeat 訊息函式加漏斗行（查詢失敗以 '?' 帶過——心跳永不崩鐵則）。
3. 前端漏斗卡：raw → candidate → validated → curated 四段 + 各段計數 + validated 待審徽章，
   點擊跳 LibraryPage（既有 promote/reject UI，不重做審核介面）。
4. 測試：聚合計數正確（空庫全 0）；前端卡 render + 跳轉。

## DoD
- 戰情頁一眼看到漏斗與待審數；日報含待審提醒。
- 晉升/退回仍走既有 LibraryPage——本步零新增審核入口。

## 邊界
- 不做新通知管道、不做 email、不做自動晉升。
- 漏斗只讀不寫（純報表）。
