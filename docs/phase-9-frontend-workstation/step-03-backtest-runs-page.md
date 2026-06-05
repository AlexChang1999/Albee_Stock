# 步驟 3 — 回測歷史 / EV 榜頁

> 開工前讀 [AI 實作護欄合約](../ai-implementation-guardrails.md)。回到 [Phase 9 索引](README.md)。

## 目標

把右側工作台裡的回測歷史，搬成獨立全頁 `/backtest-runs`：依 EV 排序的榜、收藏標星、看 equity 曲線、比較數筆。

## 改動（只做這些）

- 新增 `frontend/src/pages/BacktestRunsPage.jsx`：EV 榜表格 + 點一筆看 metrics / equity_curve。
- equity 曲線用既有圖表庫（`lightweight-charts`）或輕量 sparkline；不另引新圖表依賴。
- 掛路由 `/backtest-runs`。

## 重用既有

- `api.getBacktestRuns()` / `getBacktestRun()` / `favoriteBacktestRun()`（已存在）。
- `StrategyWorkbench` 裡既有的回測結果卡 / EV 顯示邏輯——抽出共用，不重寫。

## 不要做（防 slop / 防漂移）

- **不要**引入新圖表庫畫 equity（已有 lightweight-charts）。
- **不要**改 `/backtest-runs` 後端排序語意（已是依 EV）；Phase 6 後它會是 OOS EV，前端照顯示即可。
- **不要**把比較功能做成複雜分析套件——先做「並排看數筆 metrics」。

## 測試 / 完成定義

- 頁面渲染 / 收藏切換的 Vitest（monkeypatch api）。
- 既有測試全綠；`npm run build` 通過。
