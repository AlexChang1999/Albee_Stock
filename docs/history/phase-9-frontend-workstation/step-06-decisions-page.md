# 步驟 6 — 決策審計頁

> 開工前讀 [AI 實作護欄合約](../../ai-implementation-guardrails.md)。回到 [Phase 9 索引](README.md)。
> **依賴 [Phase 6 step-08（決策審計軌跡）](../phase-6/step-08-decision-audit-log.md)——它沒做完，這步不要開始。**

## 目標

把每個 Bot 的決策軌跡（為何在某時點買 / 賣 / 觀望 / 跳過）做成可瀏覽的頁 `/decisions`。
這是「每一筆自動決策可追溯」（原目標核心信條）的前端呈現。

## 改動（只做這些）

- `api.js` 加 `getBotDecisions(botId)`（打 Phase 6 的 `GET /bots/{id}/decisions`）。
- 新增 `frontend/src/pages/DecisionsPage.jsx`：選 Bot → 時序列出決策（action / signal / reason / price / 時間），不同 action 配色。
- 掛路由 `/decisions`。

## 重用既有

- Phase 6 的 `GET /bots/{id}/decisions` 端點與 `DecisionLog` 欄位。
- `api.getBots()`（選 Bot 下拉）、`Stat` / 既有表格樣式。

## 不要做（防 slop / 防漂移）

- **不要**在 Phase 6 step-08 完成前硬做（前置未完成就停、就問）。
- **不要**這頁去重算決策——只顯示後端寫好的審計紀錄。

## 測試 / 完成定義

- 頁面渲染 / 選 Bot 切換的 Vitest（monkeypatch api）。
- 既有測試全綠；`npm run build` 通過。
