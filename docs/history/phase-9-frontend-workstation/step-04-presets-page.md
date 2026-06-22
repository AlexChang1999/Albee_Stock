# 步驟 4 — 策略方案頁

> 開工前讀 [AI 實作護欄合約](../../ai-implementation-guardrails.md)。回到 [Phase 9 索引](README.md)。

## 目標

把右側工作台裡的策略方案，搬成獨立全頁 `/presets`：CRUD（新增 / 改名 / 調參 / 收藏 / 刪除）+ 一鍵跑回測。

## 改動（只做這些）

- 新增 `frontend/src/pages/PresetsPage.jsx`：方案清單 + 編輯 + 「跑回測」按鈕（打 `POST /presets/{id}/backtest`）。
- 掛路由 `/presets`。

## 重用既有

- `api.getPresets/createPreset/updatePreset/deletePreset/backtestPreset`（已存在）。
- `StrategyWorkbench` 既有方案 UI 邏輯——抽出共用，不重寫。
- `ConfirmDialog`（刪除確認）。

## 不要做（防 slop）

- **不要**為這頁自造一套表單 / 對話框風格——用既有元件。
- **不要**在這步動「組合策略 / 知識庫」（那是 Phase 8 + step-07）。

## 測試 / 完成定義

- CRUD 互動的 Vitest（monkeypatch api）。
- 既有測試全綠；`npm run build` 通過。
