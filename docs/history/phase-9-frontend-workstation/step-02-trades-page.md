# 步驟 2 — 交易紀錄頁

> 開工前讀 [AI 實作護欄合約](../../ai-implementation-guardrails.md)。回到 [Phase 9 索引](README.md)。

## 目標

把埋在儀表板的 `TradesTable` 升級成獨立頁 `/trades`，加上篩選（依 Bot / 標的 / 買賣別 / 日期）。

## 改動（只做這些）

- 新增 `frontend/src/pages/TradesPage.jsx`：用既有 `TradesTable` + 上方篩選列。
- 篩選為**前端純函式過濾**已抓回的 `/trades` 資料（資料量小，不需後端加參數）。
- 掛到 step-01 的路由 `/trades`。

## 重用既有

- `api.getTrades()`、既有 `TradesTable` 元件、`Stat` / 數字格式工具。

## 不要做（防 slop）

- **不要**為了篩選就改後端 `/trades` 端點（前端過濾就夠；改後端 = 範圍蔓延）。
- **不要**重寫一個新表格——擴充既有 `TradesTable`。

## 測試 / 完成定義

- `TradesPage` / 篩選純函式的 Vitest（依 bot/symbol/side 過濾正確、空結果）。
- 既有測試全綠；`npm run build` 通過。
