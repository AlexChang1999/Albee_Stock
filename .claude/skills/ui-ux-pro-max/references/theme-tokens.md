# Theme Tokens 速查（Albee Stock）

> 來源：`frontend/src/theme.js`。改 UI 時先對照此表，不要另起爐灶。

## 色票（NEON）

| Token | 用途 | 值（參考，以 theme.js 為準） |
|-------|------|------------------------------|
| `NEON.cyan` | 主行動色（CTA、高亮） | `#00e5ff` |
| `NEON.magenta` | 金融強調（PnL、重點數字） | `#ff0090` |
| `NEON.green` | 漲、正值、成功 | `#00e676` |
| `NEON.red` | 跌、負值、危險 | `#ff1744` |
| `NEON.amber` | 警告、中性警示 | `#ffd740` |

## Palette 語意色

| Token | 場景 |
|-------|------|
| `text.primary` | 主要文字 |
| `text.secondary` | 次要文字（說明、標籤） |
| `background.paper` | 卡片背景 |
| `background.default` | 頁面背景 |
| `primary.main` | 主色（同 cyan） |
| `error.main` | 錯誤/危險 |
| `warning.main` | 警告 |
| `success.main` | 成功 |

**⚠️ 絕不寫死 hex**——深色底上寫死的深色文字（`#1a2238`）會隱形。

## 字體

| 角色 | Font Family |
|------|------------|
| 標題（h1~h4） | Fraunces |
| 內文、UI 文字 | Manrope |
| 數字（等寬） | 加 `fontVariantNumeric: 'tabular-nums'` |

## 元件 Variant

| 場景 | 用法 |
|------|------|
| 卡片 | `<Paper variant="paperCard">` 或 `sx={{ ...theme.components.MuiPaper.variants }}` |
| 主要按鈕 | `<Button variant="contained" color="primary">` |
| 危險按鈕 | `<Button variant="contained" color="error">` |
| 警告按鈕 | `<Button color="warning">` |

## 形狀

```js
theme.shape.borderRadius  // 統一圓角
```

## 動畫基線

- 時長：150ms（micro）、250ms（standard）、300ms（slow）
- 屬性：只 animate `transform` / `opacity`（不 animate `height` / `width` / `top`）
- **必加**：`@media (prefers-reduced-motion: reduce)` 或靠 `index.css` 全域覆蓋
