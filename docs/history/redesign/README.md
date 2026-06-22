# Albee Terminal 改版藍圖 — AI 驅動量化交易終端機

> 本資料夾是「把現有 CRUD 表單式後台 → 升級為 AI 驅動、視覺化看盤、深藍主題的量化交易工作站」
> 的施工總藍圖。原始需求出自專案根目錄 `需求更新.md`，這裡把它**深化、對齊專案現況、拆成 4 個
> 可獨立施工的階段**。
>
> 撰寫日期：2026-06-03。
> 施工原則：**一階段一階段慢慢改**，每階段完成各自更新 `CHANGELOG.md`。
> 本資料夾僅為文件藍圖，尚未動任何程式。

---

## 〇、為什麼要改（痛點）

現況是「CRUD 表單式後台」：建 Bot 要手填名稱/策略/股票/金額/風控，圖表是別人家的 iframe
看板（React 介入不了），主題是亮色。三個痛點：

1. **太僵化、太手動**：一檔一檔手看財報跟交易量、手填參數，失去自動化意義。
2. **圖表是「別人的視窗」**：TradingView widget 用 `<iframe>` 嵌入，React 無法在上面畫
   後端算出的止損/追蹤止盈水位線，也做不了多視窗網格盯盤。
3. **亮色介面長時間盯盤累**：獲利/虧損/風控線不夠跳脫。

目標：把最繁瑣的「海選、回測、算 EV」交給系統，把最終決策權留給人（模式 A）；信任建立後再
讓系統依 EV 閾值自動建 Bot（模式 B）。全程維持**零成本本機運行**與**隱私保護**。

---

## 壹、核心需求（四大塊）

### 1. 雙軌 AI 交易模式（Dual-Track AI System）
兩種由本機 Ollama 驅動的自動化決策工作流：

- **模式 A（輔助駕駛 / 綠燈）**：AI 每日盤前掃描市場，結合訊息面（新聞/財報）與交易量，算出多組
  策略配置。前端「AI 策略探勘中心」分頁以卡片展示高期望值（EV > 0）建議。使用者檢閱後點
  **一鍵部署（Deploy）**，系統自動建 Bot + 掛排程。
- **模式 B（自動駕駛 / 紅燈）**：後端設「全局自動化規則」。當 AI 掃出的策略 EV 超過閾值
  （如 EV > 150 且勝率 > 55%），系統無需人工確認，自動配資建 Bot 跑（Paper / 實盤）。

### 2. 專業級多視角圖表（Professional Interactive Charting）
廢除 TradingView `<iframe>` widget，改用資料雙向綁定的原生圖表 `lightweight-charts`：

- **多螢幕監控**：K 線分頁支援網格佈局（2x2 或自訂分割），同時盯多檔服役中 Bot 標的。
- **水位線自動繪製**：讀 Bot 資料庫狀態，在圖上自動畫：
  - 進場均價線（白/灰虛線）
  - 靜態止損線（紅實線）
  - 動態追蹤止盈線（綠實線，隨價創高自動上移）
- **視覺化操作（未來擴充）**：圖上直接拖曳水平線，連動更新後端風控 `take_profit_pct` 等參數。

### 3. 無摩擦 UI/UX（Frictionless UI/UX）
- **版面重構**：主儀表板移除佔版面的「建立 Bot」表單，改為純監控中心（上方總損益 + AI 市場
  燈號，下方服役 Bot 狀態卡片）。
- **視覺升級**：捨棄亮色背景，全面改用**深藍色（Deep Blue）**為基底。讓獲利（青綠）、虧損
  （洋紅）與圖表風控水位線更跳脫，減輕長時間盯盤疲勞。

### 4. 設計思路（Why，避免實作偏離初衷）
- **為何雙軌 AI**：完全信任 AI 下真錢風險高，但全手動又失去自動化意義。模式 A 建立人機互信
  （系統海選、人決策 Deploy）；連續穩定獲利後再把條件寫進模式 B，循序漸進自動化。
- **為何換掉 TradingView widget**：iframe 是「別人的視窗」，React 無法畫線、無法把後端追蹤止損
  同步上去。`lightweight-charts` 能把 WebSocket 即時價 + DB 風控參數轉成圖上動態水平線。
- **為何深藍主題 + 移除表單**：AI 架構下 Bot 應由 AI 藍圖轉化而非手填；深藍系契合科技感與
  數據密集介面，讓發光圖表與 AI 決策卡片成為視覺焦點。

---

## 貳、成本與算力（零成本 + 漏斗式篩選）

核心優勢：**完全免費零成本運行** + **隱私保護**。引入 AI 海選時針對本機算力優化。

- **零成本堆疊**：AI 核心走本機 Ollama 開源模型（如 Llama 3 8B），`LLM_ALLOW_CLOUD=false`
  把資料鎖本機、零 API 費用；資料用 yfinance + Alpaca Paper Trading。
- **漏斗式篩選（Funnel Filtering）**（避免盤前批次掃描癱瘓本機）：
  - **第一層（低算力）**：先用 Python/Pandas 做技術面 + 交易量篩選（如 `Volume > MA(20) × 2.5`）。
  - **第二層（高算力）**：只把第一層篩出的 5~10 檔之新聞/財報摘要，交本機 Ollama 做情緒打分。
- **未來擴展**：改 `.env` 開 `LLM_ALLOW_CLOUD=true` 平滑切雲端模型；資料源可從 yfinance 換
  Alpaca 付費 Data Plan 拿 tick data。

---

## 參、現況 vs 需求對照（缺口分析）

> 探查既有程式所得。**已有的盡量重用**，別重造。

### 已有、可重用

| 能力 | 既有檔案 | 對應需求 |
|------|---------|---------|
| 全自動掃描海選（8 策略 × 參數網格，依 EV 排名，資料只抓一次共用 df） | `backend/services/optimizer.py`（`PARAM_GRIDS`、`run_auto_backtest()`）、`POST /auto-backtest`（`backend/routers/backtest.py`） | 模式 A 引擎雛形 |
| 回測引擎 EV 全套（expectancy、profit_factor） | `backend/services/backtest_engine.py`（`_run_on_df`） | EV 排名依據 |
| yfinance 資料源（source 可選 alpaca/yfinance） | `backend/services/yfinance_client.py`、`market_data.py` | 漏斗第一層抓量價 |
| 即時報價 WebSocket（後端單連線扇出） | `backend/services/quote_stream.py`、`routers/quotes.py`、前端 `hooks/useLiveQuote.js` | 圖表水位線即時價 |
| 基本面/財報/新聞 | `backend/services/fundamentals.py`、`routers/fundamentals.py` | 漏斗第二層情緒素材 |
| APScheduler 排程（目前只排 Bot 定時檢查） | `backend/bots/bot_manager.py` | 可加盤前掃描 job |
| Bot 風控欄位齊全 | `backend/models/bot.py`（`take_profit_pct`/`stop_loss_pct`/`trailing_stop_pct`/`peak_price`） | 圖表三條水位線資料來源 |
| LLM 對話/事後檢討慣例 | `backend/routers/chat.py`、`backend/services/explorations.py` | 情緒打分可沿用呼叫慣例 |

### 缺口（需求要、現況無）

| # | 缺口 | 現況 | 對應階段 |
|---|------|------|---------|
| 1 | 原生圖表 + 水位線 + 網格 | `frontend/src/TradingViewChart.jsx` 用 iframe；`package.json` 無圖表庫 | [Phase 1](phase-1-charting.md) |
| 2 | 漏斗式篩選 + `GET /ai-recommendations` + 探勘分頁 + 一鍵 Deploy | 有 EV 海選但無 volume 漏斗、無情緒層、無獨立 API/分頁 | [Phase 2](phase-2-ai-recommendations.md) |
| 3 | 深藍主題 + 移除建 Bot 表單 | 亮色「精緻淺色金融」主題；Dashboard 仍掛 `CreateBotForm` | [Phase 3](phase-3-ui-theme.md) |
| 4 | EV 閾值自動建 Bot（模式 B 規則引擎） | 完全無，全手動建 Bot | [Phase 4](phase-4-automation.md) |

---

## 肆、分階段施工藍圖

依此順序施工（避免大規模重構崩潰），每階段一個文件、完成各自更新 `CHANGELOG.md`：

| 階段 | 文件 | 主題 | 一句話 | 狀態 |
|------|------|------|--------|------|
| Phase 1 | [phase-1-charting.md](phase-1-charting.md) | 圖表引擎替換 | 裝 `lightweight-charts`、畫水位線、做網格 | ✅ 完成 |
| Phase 2 | [phase-2-ai-recommendations.md](phase-2-ai-recommendations.md) | AI 推薦資料流 | 漏斗式篩選 + `/ai-recommendations` + 探勘分頁 + Deploy | ✅ 完成 |
| Phase 3 | [phase-3-ui-theme.md](phase-3-ui-theme.md) | 佈局清理 + 深藍主題 | 移除表單、Dashboard 純監控、深藍色票 | ✅ 完成 |
| Phase 4 | [phase-4-automation.md](phase-4-automation.md) | 全自動護欄（模式 B） | EV 閾值排程自動建 Bot | ✅ 完成 |

> 全 4 階段已落地（2026-06-03）。後續微調：~~前端自動化規則面板~~（✅ 已補，監控中心 `AutomationPanel`）、
> ~~`BotAvatar` 深底調色~~（✅ 已補，深藍徽章 + 冷白線稿）、~~圖上拖曳水平線連動 DB~~（✅ 已落地，`handlePriceLineDrag`）。

---

## 伍、鐵則（全程不可違反）

- **全程 Paper Trading**（模擬），除非使用者明確切換。
- **實盤雙閘安全閥完全不動**：須同時 `ALPACA_BASE_URL` 用實盤網址 + `ALLOW_LIVE_TRADING=true`
  才送真錢單，由 `alpaca_client.submit_market_order` 把關。模式 B 自動建 Bot 仍受此閘保護。
- **LLM 預設本機 Ollama**：`LLM_ALLOW_CLOUD=false` 把策略資料鎖本機；外送雲端須明確開閘。
- **EV 為主、勝率為輔**：「一週勝率 90%+」極危險（常小賺多次、一次大賠），一律看 EV + 先回測
  + Paper 驗證，慎防過度擬合。
- 程式碼加**中文註解**；策略模組**鬆耦合**；每次有意義變更更新 `CHANGELOG.md`。
