# UX 稽核報告（2026-06）

> 工具：`.claude/skills/ui-ux-pro-max`（UI/UX Pro Max，99 條規則、優先序 1→10）。
> 對象：`frontend/`（React 19 + MUI v9，深色單一主題、分頁式**桌面**交易儀表板）。
> 情境決策：**桌面為主** → §2 觸控 44px / 手勢、§5 行動版響應式**降權**（只求不破版）；
> 重點放 §1 無障礙、§6 字體/色、§7 動畫、§8 表單與回饋、§9 導覽、§10 圖表。
> 落地流程見 [`ux-workflow.md`](ux-workflow.md)。

## 既有優點（保留、勿誤改）

- 圖示鈕都有 `Tooltip`；輸入框用 MUI `label`（非 placeholder-only）。
- 空狀態齊全（Bot 列表 / 交易表 / 方案 / 回測歷史 / AI 推薦）。
- `theme.js` 內建輸入框 focus 圈；卡片/按鈕/表格/彈窗樣式集中於主題（一致）。
- 圖表 `React.lazy` 延遲載入；`LiveQuote` 已用 `tabular-nums`。
- 刪除 Bot 已走站內 `ConfirmDialog`（非 `window.confirm`）。

## 發現與處置（依優先序）

| Pri | 規則 | 發現 | 證據 | 處置 |
|----|------|------|------|------|
| 1 | `aria-labels` | 圖示鈕只有 Tooltip，無 `aria-label`；Tooltip 僅在 hover/focus 提供可存取名稱，平時報讀讀成「button」 | `BotList`、`StrategyWorkbench` | ✅ 已修：圖示鈕補 `aria-label`（含 Bot/方案名） |
| 1 | `color-not-only` | 損益/EV 只靠綠/紅顏色表意，色盲或單色失效 | `BotList`、`BacktestPanel`、`AutoBacktestPanel`、`StrategyWorkbench` | ✅ 已修：新增 `signOf`/`signedMoney`（`utils/number.js`），漲跌數字一律補 `+/-` 號 |
| 1/7 | `reduced-motion` | 進場 `albeeFadeUp` 與卡片 transition 未尊重系統「減少動態」 | `App.jsx`、`theme.js`、`index.css` | ✅ 已修：`index.css` 加 `@media (prefers-reduced-motion: reduce)` 全域弱化動畫 |
| 2/8 | `confirmation-dialogs` | 停用（停 Bot）無二次確認，停實盤 Bot 風險高；刪方案用 `window.confirm`（與站內不一致） | `App.handleToggleActive`、`StrategyWorkbench` | ✅ 已修：停 Bot 走 `ConfirmDialog`（實盤文案加強）；刪方案改 `ConfirmDialog` |
| 4 | `no-emoji-icons` | emoji 當結構圖示（★☆✎🗑▶📊💬◀），跨平台不一致、不可主題化 | `StrategyWorkbench` 動作鈕 | ✅ 已修：動作鈕改 `@mui/icons-material`；標題列敘述性 emoji（📋📊💰📰）屬內文，不動 |
| 8 | `toast-dismiss` / `toast-accessibility` | 成功訊息是頁內 Alert，不自動消失、無 `aria-live`、不浮層 | `App.jsx` | ✅ 已修：成功訊息改 `Snackbar`（4s 自動消失、`role="status"` polite、不偷焦點）；錯誤維持常駐 |
| 8 | `required-indicators` / `inline-validation` / `error-placement` | 表單無必填標記、無欄位級驗證/錯誤態 | `EditBotDialog`、`BacktestPanel` | ✅ 已修：必填欄加 `required`、即時驗證 + `error`/`helperText`、無效時停用送出鈕 |
| 6/10 | `number-tabular` | 交易表非 sticky header、數字未右對齊/非等寬 | `TradesTable` | ✅ 已修：`stickyHeader` + `maxHeight` 捲動、數字欄右對齊 + `tabular-nums` |
| 10 | `loading-chart` / `empty-data-state` | K 線圖載入/查無資料時是空白畫布 | `LightweightChart` | ✅ 已修：疊載入中/查無資料/錯誤覆蓋提示（`status` 狀態機） |
| 1 | `focus-states` | 自訂可點元件（工作台 resize 把手）未保證 focus-visible | `StrategyWorkbench` resize 把手 | ⚠️ 記錄：滑鼠拖曳為主、低風險，未改 |
| 8 | `progressive-disclosure` | 改名/JSON 參數用 `window.prompt` | `StrategyWorkbench.handleEditPreset` | ⏭ 延後：改專屬 Dialog（中度，列後續） |
| 3/5 | 效能/響應式 | lazy-load 已有；桌面為主 | `App.jsx` | ⏭ 降權：僅確認不破版 |

## 延後/未做（加分項）

- `window.prompt` 改名/調參 → 專屬 Dialog。
- 表格欄位排序（`TableSortLabel` + `aria-sort`）。
- 全元件測試覆蓋（目前 `ConfirmDialog` + 純函式工具有測）。
- 骨架屏（Skeleton）全面化、`sortable-table`、行動版完整響應式/觸控 44px。

## 驗證

- `npm --prefix frontend run test` → **41 passed**。
- `npm --prefix frontend run lint` → 0 error。
- `npm --prefix frontend run build` → 成功。
