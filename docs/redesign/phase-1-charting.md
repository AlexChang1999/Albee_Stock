# Phase 1 — 圖表引擎替換（Charting）

> 目標：廢除 TradingView `<iframe>` widget，改用 `lightweight-charts` 原生圖表，做到「後端算出
> 的風控水位線能畫在圖上」與「多視窗網格盯盤」。
> 為何先做這階段：圖表是後續 AI 決策視覺化的載體，且與後端解耦，風險最低、可獨立驗收。
> 回到總藍圖：[README.md](README.md)
>
> **狀態：✅ 已完成（2026-06-03）**。落地檔案：後端 `backend/routers/bars.py`、`/bots` 加
> `avg_entry_price`；前端 `LightweightChart.jsx`、`utils/priceLines.js`、`components/ChartGrid.jsx`、
> `api.getBars`、`App.jsx` 佈局切換。測試後端 81 綠、前端 31 綠。詳見 `CHANGELOG.md`。
> 未做（留後續）：圖上拖曳水平線連動更新 DB（需求標明的「未來擴充」）。

---

## 一、現況

- K 線圖元件：`frontend/src/TradingViewChart.jsx` — 動態插入 TradingView 官方
  `embed-widget-advanced-chart.js`，以 `<iframe>` 呈現。React 無法在其上畫線。
- `frontend/package.json` — **無任何第三方圖表庫**（只有 MUI + Emotion）。
- 即時報價已可用：`frontend/src/hooks/useLiveQuote.js`（接後端 `/ws/quotes`，斷線自動重連）。
- Bot 風控狀態已存 DB：`backend/models/bot.py` 的 `take_profit_pct` / `stop_loss_pct` /
  `trailing_stop_pct` / `peak_price`；進場均價來自 Alpaca `position.avg_entry_price`（實時查）。

## 二、缺口

1. 無原生圖表庫，畫不了自訂水平線。
2. 無水位線繪製邏輯（進場均價 / 止損 / 追蹤止盈）。
3. 無網格佈局（一次只能看一檔）。

---

## 三、要做的事

### 3.1 裝套件
- `cd frontend && npm install lightweight-charts`。

### 3.2 原生 K 線元件（取代 iframe）
- 新增 `frontend/src/LightweightChart.jsx`（或改寫 `TradingViewChart.jsx`，保留檔名以免動
  `App.jsx` 的 `React.lazy` import 路徑——擇一，建議新增 + App 換引用）。
- 用 `createChart` + `addCandlestickSeries`，K 線資料打後端歷史 bars（沿用
  `backend/services/market_data.get_bars`，前端可加 `GET /bars/{symbol}` 或重用既有回測資料端點）。
- 即時最後一根 K 線跳動：接 `useLiveQuote(symbol)`，用 `series.update()` 更新當前 bar。

### 3.3 水位線繪製（核心）
- 用 `series.createPriceLine({ price, color, lineStyle, title })` 畫三條：
  - **進場均價線**：白/灰、虛線（`LineStyle.Dashed`），title「進場 avg」。
  - **靜態止損線**：紅、實線，價 = 進場價 ×(1 − `stop_loss_pct`)。
  - **動態追蹤止盈線**：綠、實線，價依 `peak_price` ×(1 − `trailing_stop_pct`)，隨價創高上移。
- 資料來源：讀該標的對應 Bot 的風控欄位（`GET /bots` 已回 Bot 清單；進場均價需從持倉查，
  可在 Bot stats 端點補帶 `avg_entry_price`）。

### 3.4 網格佈局
- K 線分頁支援 2x2 網格（先固定 2x2，自訂分割列為未來擴充）。
- 用 MUI `Grid` 排 4 格，每格一個 `LightweightChart`，各自訂標的（預設帶服役中 Bot 的標的）。

---

## 四、接點（重用既有）

- 即時價：`frontend/src/hooks/useLiveQuote.js`。
- 歷史 bars：`backend/services/market_data.get_bars(symbol, days, source)`。
- 風控資料：`backend/models/bot.py` 欄位 + `backend/routers/bots.py` 的 Bot/stats 端點。

## 五、不在本階段

- 圖上拖曳水平線連動更新 DB（需求標明的「未來擴充」），本階段只做唯讀繪製。

## 六、驗證

1. `npm install lightweight-charts` 成功、`npm run dev` 起得來。
2. 單一標的：K 線正常顯示、即時最後一根會跳；對一檔有部位的 Bot，圖上正確畫出 3 條水位線，
   追蹤止盈線在價格創高後上移。
3. 網格：2x2 同時顯示 4 檔不卡頓。
4. 前端測試 `npm test` 綠。

## 七、完成後

更新 `CHANGELOG.md`「未發布」`### 變更`/`### 新增`：記下換圖表庫、水位線、網格（附改動檔名）。
