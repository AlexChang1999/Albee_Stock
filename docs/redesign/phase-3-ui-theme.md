# Phase 3 — 佈局清理 + 深藍主題（UI Revamp）

> 目標：主儀表板移除「建立 Bot」表單改為純監控中心；MUI 主題從亮色換成深藍系。
> 為何此階段：在 Phase 2 的 AI 推薦 + Deploy 落地後，手填表單已非主要建 Bot 途徑，可安心移除；
> 深藍主題讓 Phase 1 的圖表水位線與數據色更跳脫。
> 回到總藍圖：[README.md](README.md)
>
> **狀態：✅ 已完成（2026-06-03）**。落地檔案：`theme.js`（palette 轉 dark，`NEON` 沿用匯出名改值：
> cyan=亮藍主動作、magenta=黃金點綴、green=青綠獲利、red=洋紅虧損；卡片/按鈕/輸入改深藍面板）、
> `index.css`（深海軍藍底 + 冷色光暈 + color-scheme dark）、`App.jsx`（儀表板移除 `CreateBotForm` +
> 連帶 `handleCreate`/`form` 死碼，改成頂部 AI 市場燈號引導去「AI 探勘」一鍵部署）。
> 前端 build + 31 測試綠。`CreateBotForm.jsx` 元件檔保留備用（已無人引用）；`BotAvatar` 暫未調色。

---

## 一、現況

- 主題：`frontend/src/theme.js` 為**亮色**「精緻淺色金融」風（白卡 + 髮絲線）。`NEON` 色票目前是
  森林綠主色 `#1f6f54` + 黃銅金 `#b0883a` + 漲綠 `#1f7a5a` / 跌紅 `#b23b32`。
- Dashboard 編排（`frontend/src/App.jsx`）：Header → 帳戶卡 → **`CreateBotForm`**（建 Bot 表單）
  → `BotList` → `AutoBacktestPanel` → `BacktestPanel` → `TradesTable` → 右側 `StrategyWorkbench`。
- `index.css` / `index.html`：米白底 + 暖色光暈 + 字體（Fraunces/Manrope/IBM Plex Mono）。

## 二、缺口

1. 主題是亮色，需求要深藍（Deep Blue）基底。
2. Dashboard 仍掛佔版面的建 Bot 表單，未改為純監控中心。

---

## 三、要做的事

### 3.1 深藍主題（`theme.js`）
- `palette.mode` 改 `dark`；背景改深藍系（如 `#0a1628` / `#0f1f38` 層次）。
- 數據色強化對比：獲利**青綠**、虧損**洋紅**，風控水位線色與 Phase 1 對齊。
- **沿用 `NEON` 匯出名**（重寫值即可），避免動既有 `import { NEON }` 的檔案——比照上次淺色改版手法。
- 同步調 `index.css`（深底背景/光暈）、必要時 `index.html` 字體。

### 3.2 佈局清理（`App.jsx`）
- 從 Dashboard 移除 `CreateBotForm`（元件檔可保留，供需要時別處復用；或之後刪）。
- Dashboard 重排為**純監控中心**：
  - 上方：總體損益（帳戶卡升級）+ AI 市場燈號（可接 Phase 2 推薦摘要 / 留位）。
  - 下方：服役中 Bot 狀態卡片（`BotList`）。
- 回測/工作台等保留在各自分頁/側欄，不塞回主儀表板。

## 四、接點（重用既有）

- 主題：`frontend/src/theme.js`（`NEON` 匯出名）、`index.css`、`index.html`。
- 佈局：`frontend/src/App.jsx`、`components/AccountCard.jsx`、`components/BotList.jsx`。
- 建 Bot 入口改由 Phase 2 的「AI 探勘 → Deploy」為主；手動建 Bot 若仍需，移到次要入口（對話框/分頁）。

## 五、注意

- 改 `NEON` 值前先 grep 全前端用到 `NEON.*` 的地方，確保深藍配色下每處仍對比清楚。
- `BotAvatar.jsx`（目前米白徽章風）在深底下可能要回頭調色。

## 六、驗證

1. `npm run dev` 視覺檢查：深藍底、獲利青綠/虧損洋紅對比清楚、圖表水位線跳脫。
2. Dashboard 無建 Bot 表單，呈現「上總損益 + AI 燈號 / 下 Bot 卡片」。
3. 前端 `npm test` 綠（主題/快照若有需同步更新）。

## 七、完成後

更新 `CHANGELOG.md`「未發布」`### 變更`：深藍主題改版 + Dashboard 改純監控中心（附改動檔名）。
