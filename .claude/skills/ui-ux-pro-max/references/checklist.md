# 交付前 UX Checklist（Albee Stock 前端）

> 每次改 UI 交付前，從頭到尾勾一遍。**順序即優先序**。

## Pri 1 — 無障礙（CRITICAL）

- [ ] 所有圖示鈕都有 `aria-label`（不只 `Tooltip`）
- [ ] 圖示鈕 `aria-label` 含 Bot 名稱或方案名（動態的也要動態帶入）
- [ ] `focus-visible` 在自訂可互動元件上可見（`theme.js` 預設已處理 MUI 元件）
- [ ] 漲跌/損益/EV 數字帶 `+/-` 號（用 `signOf` / `signedMoney` / `formatPercent`）
- [ ] 動畫尊重 `prefers-reduced-motion`（`index.css` 已全域，新 keyframes 自行補）

## Pri 2 — 互動/回饋

- [ ] 載入中有 spinner 或 skeleton（不是無回應的空白）
- [ ] 危險動作（停 Bot / 刪方案 / 刪 Bot）走 `ConfirmDialog`
- [ ] 危險確認鈕用 `color="error"` 或 `color="warning"`
- [ ] 無 `window.confirm` / `window.prompt`（改站內 Dialog）

## Pri 4 — 風格/一致

- [ ] 無 emoji 當結構圖示（改 `@mui/icons-material`）
- [ ] 標題列敘述性 emoji（📋📊）屬內文，允許保留
- [ ] 視覺風格與現有頁面一致（顏色、間距、卡片圓角）

## Pri 6 — 字體/色

- [ ] 顏色不寫死 hex，用 `theme.palette` 或 `NEON` 變數
- [ ] 數字欄位用 `fontVariantNumeric: 'tabular-nums'`
- [ ] 深色背景上文字對比目視 OK（次要文字用 `text.secondary`）

## Pri 7 — 動畫

- [ ] 動畫時長 150–300ms
- [ ] 只用 `transform` / `opacity`（不 animate layout 屬性）

## Pri 8 — 表單/回饋

- [ ] `<TextField>` 有 `label`（非 placeholder-only）
- [ ] 必填欄加 `required` prop
- [ ] 送出前有欄位級驗證（`error` + `helperText`）
- [ ] 無效時送出鈕 `disabled`
- [ ] 送出中按鈕 `loading` 或 spinner
- [ ] 成功訊息用 `Snackbar`（`autoHideDuration={4000}`、`role="status"`）
- [ ] 錯誤訊息用常駐 `Alert`（需要用戶看清楚才消失）

## Pri 9 — 導覽

- [ ] 當前頁面在 sidebar 有高亮
- [ ] 返回/取消行為可預期

## Pri 10 — 圖表

- [ ] 載入中有 overlay 提示
- [ ] 查無資料有 empty state 提示（不是空白畫布）
- [ ] 有錯誤態提示
- [ ] tooltip 可讀取具體數值
- [ ] 不只靠顏色傳達資訊（e.g. 漲跌線條粗細或標記）

## 驗證指令

```powershell
npm --prefix frontend run test
npm --prefix frontend run lint
npm --prefix frontend run build
```

全過才算交付完成。
