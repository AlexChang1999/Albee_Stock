# 步驟 7 — 進化實驗室 + 策略知識庫頁

> 開工前讀 [AI 實作護欄合約](../ai-implementation-guardrails.md)。回到 [Phase 9 索引](README.md)。
> **依賴 [Phase 8](../phase-8-strategy-evolution/README.md)——它沒做完，這步不要開始。**

## 目標

把 Phase 8 的「策略知識庫 + 組合進化」呈現成兩個頁：
- `/library` 策略知識庫：理論 / 場景 / 使用時機 / OOS 指標 / 狀態親和性。
- `/evolution` 進化實驗室：候選策略、驗證狀態、組合操作、**人在迴路晉升 / 退回**。

## 改動（只做這些）

- `api.js` 加 Phase 8 端點呼叫（`/knowledge`、`/knowledge/ranking`、`/knowledge/{id}/validate|promote|reject`、`/knowledge/propose`）。
- 新增 `frontend/src/pages/LibraryPage.jsx`（唯讀策展庫 + 排行）與 `EvolutionPage.jsx`（候選審核 + 晉升按鈕）。
- 掛路由 `/library`、`/evolution`。

## 重用既有

- Phase 8 既有端點（不另造前端邏輯重算）。
- 既有 EV 顯示卡 / 表格樣式（與回測歷史頁共用元件）。

## 不要做（防 slop / 防漂移）

- **不要**在 Phase 8 後端完成前硬做。
- **不要**在前端做「自動晉升」——晉升一律由使用者點按觸發（呼應 Phase 8 人在迴路）。
- **不要**在前端重算驗證 / EV——只顯示後端結果。

## 測試 / 完成定義

- 兩頁渲染 + 晉升 / 退回互動的 Vitest（monkeypatch api）。
- 既有測試全綠；`npm run build` 通過。
