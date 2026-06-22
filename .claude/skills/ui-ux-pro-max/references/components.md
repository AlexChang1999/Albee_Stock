# 可複用元件清單（Albee Stock 前端）

> 改 UI 前先查此表，優先複用現有元件，避免重複造輪子。

## 通用 UI 元件（`frontend/src/components/`）

| 元件 | 路徑 | 用途 |
|------|------|------|
| `ConfirmDialog` | `components/ConfirmDialog` | 危險動作二次確認（停 Bot、刪除等）；prop: `open`, `onConfirm`, `onCancel`, `title`, `description`, `confirmColor` |
| `Stat` | `components/Stat` | 單一指標卡片（數字 + 標籤）；吃主題色，勿寫死 hex |
| `Header` | `components/Header` | 頁首 |
| `AccountCard` | `components/AccountCard` | 帳戶餘額/購買力展示 |
| `BotList` | `components/BotList` | Bot 列表（含啟停、刪除） |
| `BotAvatar` | `BotAvatar.jsx` | Bot 頭像（深藍發光徽章） |
| `SidebarLayout` | `components/SidebarLayout` | 左側導覽外殼（全站 layout） |
| `AssistantDrawer` | `components/AssistantDrawer` | 思考助手全站抽屜（右下浮動鈕） |
| `BacktestPanel` | `components/BacktestPanel` | 回測參數表單 + 結果展示 |
| `BacktestResultCard` | `components/BacktestResultCard` | 單筆回測結果卡片 |
| `TradesTable` | `components/TradesTable` | 交易紀錄表（stickyHeader、數字右對齊） |
| `EditBotDialog` | `components/EditBotDialog` | 編輯 Bot 彈窗（含 inline 驗證） |
| `LightweightChart` | `LightweightChart.jsx` | 原生 K 線圖（含載入/空/錯誤態） |
| `LiveQuote` | `components/LiveQuote` | 即時報價（tabular-nums） |
| `EquitySparkline` | `components/EquitySparkline` | 小型資產曲線 |
| `ChartGrid` | `components/ChartGrid` | 多圖表格狀排版 |
| `RecommendationsPanel` | `components/RecommendationsPanel` | AI 海選推薦 |
| `AutomationPanel` | `components/AutomationPanel` | 模式 B 自動化規則 |
| `KnowledgeCard` | `components/KnowledgeCard` | 知識庫條目卡片 |

## 工具函式（`frontend/src/utils/`）

| 函式 | 用途 |
|------|------|
| `signOf(v)` | 數字正負符號（`+` / `-` / ``） |
| `signedMoney(v)` | 帶符號金額字串（`+$1,234.56`） |
| `formatPercent(v)` | 百分比帶符號（`+12.34%`） |
| `formatCompact(v)` | 大數壓縮（`1.2M`） |

**漲跌數字必用以上函式**，不要只靠紅綠顏色。

## 自訂 Hook（`frontend/src/hooks/`）

| Hook | 用途 |
|------|------|
| `useDashboardData` | 一次載入 account / bots / trades |

## 常數（`frontend/src/constants.js`）

| 常數 | 內容 |
|------|------|
| `STRATEGIES` | 策略清單（單一來源） |

## 新增元件時的規則

1. 顏色吃主題，不寫死 hex
2. 圖示鈕補 `aria-label`
3. 危險動作一律走 `ConfirmDialog`
4. 純函式工具放 `utils/`（方便寫測試）
5. 新元件加測試（`*.test.jsx`，Vitest + RTL）
