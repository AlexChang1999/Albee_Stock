# UX 工作流（Albee Stock 前端）

> 目的：每次動到 UI 都有一條固定路徑可走，確保「每一步 UX 都正確好用」。
> 規則庫＝ [`.claude/skills/ui-ux-pro-max/SKILL.md`](../../.claude/skills/ui-ux-pro-max/SKILL.md)
> （已裝進專案；含 Web/MUI 適配註記）。本專案＝ React 19 + MUI v9、深色單一主題、
> **桌面為主**的交易儀表板。對應一次性稽核見 [`ux-audit-2026-06.md`](ux-audit-2026-06.md)。

## 1. 何時觸發

只要改動會改變介面「看起來 / 感覺 / 動起來 / 互動方式」的東西，就先讀 skill：
新頁面/區塊、新元件（按鈕/彈窗/表單/表格/圖表）、改色票或字體、調動畫、改導覽。
純後端/資料/DevOps **不需要**。

## 2. 三步流程

1. **釐清**：產品/頁面類型 + 風格關鍵字（本專案＝ dashboard / fintech / dark / data-dense）。
2. **對齊既有 tokens**（不要另起爐灶）：
   - 色：`theme.js` 的 `NEON`（cyan 主行動、magenta 金強調、green 漲、red 跌）。
   - 形：`theme.shape.borderRadius`、卡片 `paperCard`、字體（Fraunces 標題 / Manrope 內文 / 等寬數字）。
   - 元件：複用 `components/`（`ConfirmDialog`、`Stat`…）與 `utils/`（`number.js` 的 `signOf`/`signedMoney`/`formatPercent`/`formatCompact`）。
3. **實作**：一次一個小批、可測；改完跑驗證（見 §5）。

## 3. 優先序閘門（1→10，交付前由高到低過）

1. **無障礙**（CRITICAL）：圖示鈕 `aria-label`、focus 可見、`color-not-only`、`reduced-motion`。
2. **互動**：載入回饋、危險動作確認（桌面 → 觸控 44px 降權）。
3. **效能**：lazy-load、不要 layout thrash（已大致就位）。
4. **風格**：不用 emoji 當結構圖示（用 `@mui/icons-material`）、一致。
5. **版面/響應式**（桌面降權）：只求縮到 ~768px 不破版。
6. **字體/色**：語意色 token、數字用 `tabular-nums`、對比 ≥ 4.5:1。
7. **動畫**：150–300ms、transform/opacity、尊重 `prefers-reduced-motion`。
8. **表單/回饋**：可見 label + 必填標記、欄位級錯誤、送出 loading/結果、toast 自動消失且 `aria-live`。
9. **導覽**：當前位置高亮、返回可預期。
10. **圖表**：載入/空資料/錯誤態、tooltip、不只靠顏色。

## 4. 交付前檢查表（Web/MUI 版）

- [ ] 圖示鈕都有 `aria-label`（不只 `Tooltip`）。
- [ ] 漲跌/損益不只靠紅綠 → 帶 `+/-`（用 `signOf`/`signedMoney`）。
- [ ] 表單：必填 `required`、即時驗證 `error`+`helperText`、無效時停用送出。
- [ ] 成功用 `Snackbar`（自動消失 + `role="status"`）；錯誤需看清楚 → 常駐 Alert。
- [ ] 危險動作（停/刪）走 `ConfirmDialog`，危險鈕用語意色（error/warning）。
- [ ] 沒有 emoji 當結構圖示（改 `@mui/icons-material`）。
- [ ] 表格：`stickyHeader` + 數字右對齊 + `tabular-nums`。
- [ ] 圖表：有載入/空資料/錯誤態，不是空白畫布。
- [ ] 動畫尊重 `prefers-reduced-motion`（已由 `index.css` 全域處理）。
- [ ] 深色對比目視 OK（綠/紅、次要文字 `text.secondary`）。
- [ ] 縮到 ~768px 不破版。

## 5. 驗證步驟

```powershell
npm --prefix frontend run test    # vitest（純函式 + 元件）
npm --prefix frontend run lint    # eslint，需 0 error
npm --prefix frontend run build   # 確認所有元件能編譯（測試未必覆蓋到）
npm --prefix frontend run dev     # 手動 smoke：建/編 Bot、停 Bot 確認、回測、工作台、交易表、K 線圖
```

> 註：`frontend/node_modules` 若不存在，先 `npm --prefix frontend install`。

## 6. 與既有護欄掛鉤

照 [`ai-implementation-guardrails.md`](../ai-implementation-guardrails.md)：一次一步、對齊原目標、反 vibe slop。
新增 Skill 仍依 [`skill-guidelines.md`](../guides/skill-guidelines.md)。
