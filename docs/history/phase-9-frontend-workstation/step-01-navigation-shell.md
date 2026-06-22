# 步驟 1 — 導覽重構 + Dashboard 瘦身

> 開工前讀 [AI 實作護欄合約](../../ai-implementation-guardrails.md)。回到 [Phase 9 索引](README.md)。

## 目標

把上方 4 個 Tabs 換成左側 sidebar + 路由的多頁面骨架，並把儀表板瘦身回「純監控中心」。
這步定下後續所有頁面的外殼，**一次定案、後面照長**。

## 改動（只做這些）

- 技術選型（step-01 一次決定）：引入 `react-router-dom`（多頁路由）。評估 Windows / Vite 安裝（低風險）。
- 新增 `frontend/src/components/SidebarLayout.jsx`：左側導覽 + 右側 `<Outlet>`（路由內容）。
- `App.jsx` 從「tab 狀態切換」改為「路由切換」；既有四塊（儀表板 / AI 探勘 / K 線圖 / 基本面）先搬成路由頁，**行為不變**。
- Dashboard 瘦身：把 `AutoBacktestPanel` / `BacktestPanel` / `TradesTable` 移出儀表板（搬到各自頁，後續步驟接手），儀表板只留 AccountCard + AI 燈號 + BotList。

## 重用既有

- 既有元件（`Header`、`AccountCard`、`BotList`、`RecommendationsPanel`、`FundamentalsPanel`、圖表 lazy 載入）原樣掛到路由。
- `theme.js` 色票 / `index.css`（sidebar 沿用深藍主題，不另立配色）。

## 不要做（防 slop / 防漂移）

- **不要**在這步加任何新功能頁——這步只做「外殼 + 把既有搬進去、行為不變」。
- **不要**重畫既有元件的內部；只動「它們被掛在哪」。
- **不要**自寫路由系統（用 react-router）。

## 測試 / 完成定義

- 既有 Vitest 全綠（必要時更新 render 包 router 的測試 util）。
- 手動驗收：四個既有頁面經 sidebar 都到得了、長相行為不變；儀表板不再有回測 / 交易表。
- `npm run build` 通過。
