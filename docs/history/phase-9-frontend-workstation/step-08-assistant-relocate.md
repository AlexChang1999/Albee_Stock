# 步驟 8 — 思考助手改抽屜 / 獨立頁 + 拆 StrategyWorkbench

> 開工前讀 [AI 實作護欄合約](../../ai-implementation-guardrails.md)。回到 [Phase 9 索引](README.md)。

## 目標

右側 `StrategyWorkbench`（方案 / 回測歷史 / 助手聊天）的內容，在前面步驟已分別搬到 `/presets`、`/backtest-runs`。
這步收尾：把「思考助手聊天」改成全站可開的抽屜（或 `/assistant` 頁），並移除已被搬空的 `StrategyWorkbench` 外殼。

## 改動（只做這些）

- 新增 `frontend/src/components/AssistantDrawer.jsx`（或 `pages/AssistantPage.jsx`）：沿用既有聊天 + postmortem 邏輯。
- 從 `App.jsx` 移除右側 `StrategyWorkbench` 掛載；確認其功能已無遺漏地分散到各頁。
- 死碼清理：`StrategyWorkbench.jsx` 若整支無人引用則刪除（**刪，不要註解掉**）。

## 重用既有

- `api.sendChat` / `api.postmortem`、既有聊天 UI 與「總結這次錯在哪」按鈕邏輯。

## 不要做（防 slop / 防漂移）

- **不要**在功能還沒確認搬完前就刪 `StrategyWorkbench`（先確認 presets / 回測歷史 / 聊天都各有家）。
- **不要**留下註解掉的舊面板碼——無引用就整支刪。
- **不要**改助手的後端契約 / 鐵則（它仍只「思考」，不下單、不跑回測）。

## 測試 / 完成定義

- 聊天 / postmortem 互動的 Vitest 仍綠（搬家後）。
- 全站 grep 確認無殘留對已刪元件的 import；`npm run build` 通過。
- 既有測試全綠。
