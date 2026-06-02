# 變更紀錄 (Changelog)

本檔案記錄 Albee Stock 專案的所有重要變更。

格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，
版本號遵循[語意化版本](https://semver.org/lang/zh-TW/)（主版本.次版本.修訂號）。

變更分類說明：
- **新增 (Added)**：新功能
- **變更 (Changed)**：既有功能的調整
- **修正 (Fixed)**：錯誤修復
- **移除 (Removed)**：移除的功能

---

## [未發布]

### 新增

- Phase 4 收尾—通知擴充 Discord：`services/notifier.py` 重構成多管道（LINE + Discord），
  各管道獨立、任一失敗不影響其他。Discord 走最簡單的 Webhook（`DISCORD_WEBHOOK_URL`，
  `.env.example` 已補欄位說明），沒設定就靜默跳過。附 3 個測試（mock requests，不真發）。

### 文件

- 新增 `docs/phase4-paper-checklist.md`：Phase 4 Paper 連續實跑驗收清單，
  涵蓋排程／開市判斷／風控出場／重啟恢復／通知／績效／多 Bot 並發，逐項「預期 vs 實際」打勾。

### 變更

- Phase 4 收尾—降低多 Bot 並發 API 壓力：`alpaca_client.is_market_open()` 加 30 秒
  TTL 快取，多個 Bot 幾乎同時排程時只第一個真的問 Alpaca clock、其餘吃快取，省 API 額度。
  （只快取開市狀態；現價／持倉刻意不快取，交易決策需即時值。）附 2 個測試。
- Phase 4 收尾—追蹤止損最高價持久化：`models/bot.py` 新增 `peak_price` 欄位，
  `bot_manager.py` 把原本記憶體 dict `_peak_prices` 改成寫資料庫（新增 `_persist_peak`）。
  修正後端重啟後追蹤止損最高價歸零、保護中斷一段時間的問題。
  附 Alembic 遷移 `a1b2c3d4e5f6_add_bot_peak_price`，並補 2 個測試（持久化往返、
  追蹤止損讀持久化最高價），`tests/` 共 40 個全綠。

---

## [0.2.0] - 2026-06-02

### 新增

- Phase 4 收尾—風控欄位全鏈路接通：`BotCreate` schema 與 `create_bot`／`update_bot`／
  `list_bots` 補上 `take_profit_pct`／`stop_loss_pct`／`trailing_stop_pct`／
  `check_interval_sec`，使用者可從前端設定／編輯風控。前端建立 Bot 表單與編輯彈窗
  新增「止盈 %／止損 %／追蹤止損 %／監測頻率（秒）」欄位（填百分比整數，空白=不啟用，
  送出前轉成後端要的小數）。
- Phase 4 收尾—排程改用各 Bot 的 `check_interval_sec`：`POST /bots/{id}/start`
  的 `interval` 改為選填，沒帶就用該 Bot 設定的頻率（預設 60 秒）。
- Phase 4 收尾—重啟自動恢復排程：`main.py` lifespan 啟動時把 `is_active=True` 的
  Bot 用各自頻率重新掛回 APScheduler，修正後端重啟後「顯示啟用但其實沒在跑」的狀態落差。
- Phase 4 收尾—實盤狀態顯示：新增 `GET /status`（回 `is_paper`／`allow_live`／
  `live_armed`）。前端頂部加「模擬交易（綠）／⚠️ 實盤·真錢（紅）」標示 Chip，
  雙閘全開時再加一條紅色警告橫幅。切換環境仍須手動改 `.env`（保留防手滑的雙閘設計）。

- 接入 **Alpaca 官方 MCP Server**（[alpacahq/alpaca-mcp-server](https://github.com/alpacahq/alpaca-mcp-server)）：
  讓 Claude 能用自然語言查帳戶/報價/歷史資料、下 Paper 測試單，加速開發與策略研究。
  - 用 `claude mcp add alpaca --scope local` 安裝，金鑰存使用者層級設定（不進 git）
  - `ALPACA_PAPER_TRADE=true` 鎖定模擬模式
  - CLAUDE.md 新增「可用的 MCP Server」區段說明用法
- 導入 **Alembic** 資料庫遷移（長期 DB 設計）：schema 變更改走版本化遷移，
  取代手動 `ALTER TABLE`，且 SQLite/PostgreSQL 通用。
  - `alembic/env.py` 接專案 `config.DATABASE_URL` 與 model metadata；
    SQLite 開 `render_as_batch=True`（否則未來改/刪欄位會失敗）
  - baseline 遷移（建 `bots`、`trade_logs`）；既有 `albee_stock.db` 以 `stamp head` 標記
  - `setup.bat` 新增 `alembic upgrade head` 步驟，新電腦一鍵建好 schema
- Phase 4 監聽系統—Bot 風控欄位：`models/bot.py` 新增 `take_profit_pct`（固定止盈）、
  `stop_loss_pct`（固定止損）、`trailing_stop_pct`（追蹤止損）、`check_interval_sec`
  （監測頻率，預設 60 秒）。皆 nullable，None = 不啟用該機制。
- Phase 4 監聽系統—風控判斷模組：新增 `services/risk_manager.py`（純函式 `check_exit`，
  依進場價/現價/持倉最高價判止損→追蹤止損→止盈，保護優先）。
  附 8 個單元測試 `tests/test_risk_manager.py`，不需連線、納入 CI。
- Phase 4 監聽系統—出場監測接上交易迴圈：`bots/bot_manager.py` 的 `run_bot_once`
  重構成「持倉/空手」兩分支，持倉時**先跑風控**（觸發即平倉，reason 帶止盈/止損原因），
  沒觸發才看策略賣出訊號。追蹤止損的「持倉最高價」用記憶體 dict 維護。
- Phase 4 監聽系統—開市判斷：`alpaca_client` 新增 `is_market_open()`；
  `run_bot_once` 排程自動跑時休市直接跳過（省 API、避免怪單），
  手動 `/run` 傳 `ignore_market_hours=True` 仍可休市測試。
  `tests/test_bot_manager.py` 共 4 個 monkeypatch 測試（不連網、不碰真 DB）。
- Phase 4 監聽系統—實盤交易安全閥（真錢防線）：`config.py` 新增 `ALLOW_LIVE_TRADING`
  （讀 `.env`，預設 false）。`submit_market_order`（所有下單唯一出口）最前面加閘：
  連到實盤(真錢) 但安全閥未開 → 拒絕下單並丟錯。要動真錢需「實盤網址 + 安全閥開」兩道閘都開。
  `.env.example` 補欄位與風險說明；附 3 個測試 `tests/test_safety_valve.py`。
- 後端 API 重構：把原本全擠在 `main.py` 的路由依功能拆到 `backend/routers/`
  （`bots.py`／`backtest.py`／`orders.py`），`main.py` 只留 app 設定與基本端點。
  URL 路徑不變，23 個測試全綠。
- 前端測試：導入 Vitest + React Testing Library（`npm run test`／`test:watch`），
  新增 `src/test/setup.js`、`vite.config.js` test 設定，
  並補上首批測試（`statRows` 純函式、`ConfirmDialog` 互動），共 7 個全綠。

### 變更

- 變更（前端打包）：K 線圖元件改用 `React.lazy` + `Suspense` 延遲載入
  （點開分頁才下載）；`vite.config.js` 加 `manualChunks` 把第三方套件
  （MUI/React 等）切成獨立 `vendor` chunk，自己的程式碼縮到約 25KB——
  日後只改 app 程式時，使用者不必重抓約 480KB 的 vendor。
- 變更：刪除 Bot 的確認改用 MUI 彈窗（新增通用元件 `ConfirmDialog`），
  取代原本瀏覽器原生的 `window.confirm`，風格與全站一致。
- 重構：把 `App.jsx` 的資料載入邏輯抽成自訂 Hook `useDashboardData`
  （`frontend/src/hooks/`），集中管理 account/bots/trades 三份資料、
  載入中狀態與重新載入。App 改用 `reload()` 取代原本的 `loadAll()`，
  並新增 `loading` 進度條與 `loadError` 顯示。`npm run lint`／`build` 皆通過。
- 變更：前端後端網址改讀環境變數 `VITE_API_URL`（`api.js`），
  沒設定時退回 `http://127.0.0.1:8000`，搬電腦／部署時不必改程式碼。
  新增 `frontend/.env.example` 說明；覆寫時複製成 `.env.local`（已被 gitignore）。
- 重構：把原本 1050 行全擠在 `App.jsx` 的前端拆成模組化結構。
  主題設定獨立為 `theme.js`（含 `NEON` 色票）、策略清單獨立為 `constants.js`，
  各畫面區塊拆到 `frontend/src/components/`（`Header`、`AccountCard`、
  `CreateBotForm`、`BotList`、`BacktestPanel`、`TradesTable`、`EditBotDialog`、
  共用的 `Stat`）。`App.jsx` 瘦身為純編排層（只管 state、handler、分頁），
  約 300 行。畫面與行為完全不變，`npm run build` 通過。
- 重構：把原本全擠在 `main.py` 的 API 依功能拆到 `backend/routers/`
  （`bots.py` Bot 管理、`backtest.py` 回測、`orders.py` 交易紀錄），
  `main.py` 只留建 app／CORS／lifespan 與基本端點（`/`、`/account`），
  用 `include_router` 掛上。所有 URL 路徑不變，23 個測試全綠。

### 文件

- `CLAUDE.md` 改寫：專案結構圖改為對齊現況（路由仍在 `main.py`、7 種策略、
  `performance.py`、扁平 frontend/tests、3 個 `.bat`），開發階段更新為 Phase 3 進行中
- 新增 `docs/skill-guidelines.md`（撰寫 Skill 四原則：避坑指南、漸進式揭露、
  記憶能力、按需觸發危險操作 Hook），CLAUDE.md 改以連結引用以保持精簡

### 新增

- React 前端（Vite）：`frontend/`
  - `api.js`：統一的後端 API 呼叫層
  - `App.jsx`：主畫面（帳戶資訊、建立 Bot 表單、Bot 列表、交易紀錄）
  - 可在畫面上建立 Bot、手動執行策略
- 後端加入 CORS 設定，允許前端（localhost:5173）跨來源呼叫
- 前端導入 Material UI (MUI)，畫面改用現成元件（AppBar、Card、Table、表單），更美觀且響應式
- 整合 TradingView 即時線圖（免費 Advanced Chart Widget），可輸入股票代號切換看盤
- 回測引擎 `backtest_engine.py`：逐日 walk-forward 模擬，計算總報酬、最大回撤、勝率、Buy & Hold 對照
- 回測 API `POST /backtest`，以及前端回測介面（含績效摘要與交易明細）
- 回測引擎單元測試（3 個），CI 一併執行

### 變更

- 前端全套視覺翻新為「亮色玻璃儀表板」風格（淺色背景 + glassmorphism）：
  - 引入特色字體：標題 `Sora`、內文 `Outfit`、金融數字 `JetBrains Mono`（等寬對齊）
  - `index.css` 改為淺灰白背景（#f4f6fb）+ 多層柔和彩色光暈 + 淡顆粒雜訊
  - `App.jsx` MUI 主題改為 light + 彩色 accent 色票（青/洋紅/綠/紅）；
    以 `components.styleOverrides` 一次套用全站白玻璃卡片、漸層按鈕、聚焦彩色邊框輸入框、
    分頁與表格樣式；hover 以彩色邊框+柔陰影取代發光
  - 頂部標題列改為亮色玻璃 sticky header（漸層文字 logo + 呼吸脈動圓點）
  - 功能與 API 行為不變，僅換視覺
- `BotAvatar.jsx` 改為 NFT 風「多部件隨機組合」頭像：底色漸層×6、頭型×6、
  眼睛×6、天線×5、嘴巴×5，依 seed 不同位元獨立挑選 → 上千種組合、每 Bot 獨一；
  規格大小統一（同 viewBox/size），啟用中仍以主色光暈標示

### Phase 3（進行中）

- Bot 績效指標串接：新增 `services/performance.py`（純函式，依真實交易紀錄
  以平均成本法配對買賣，算出勝率/報酬率/交易次數/最大回撤）
  - `GET /bots` 回傳值加入每個 Bot 的 `stats`，另新增 `GET /bots/{id}/stats`
  - 前端 Bot 卡片改為顯示真實績效數字（報酬率正負以綠/紅標色；無交易顯示 "-"）
  - 績效計算單元測試（5 個），CI 一併執行
- 新增換電腦/啟動用批次檔：`setup.bat`（一鍵建環境）、
  `start_backend.bat`、`start_frontend.bat`
- 每個 Bot 顯示獨一無二的方塊像素頭像（`BotAvatar.jsx`，前端 SVG 生成，
  暖色系、左右對稱、圓角，呼應 Claude 的可愛風格）
- Bot 編輯 / 刪除功能（後端 `PUT /bots/{id}`、`DELETE /bots/{id}`；前端編輯彈窗 + 刪除確認）
- Bot 列表加入啟動/停止、執行、編輯、刪除的圖示按鈕（串接既有 start/stop API）
- 啟用中的 Bot 頭像會發光（用該 Bot 自己的顏色）
- 新增 3 種交易策略：唐奇安通道突破 (donchian)、KD 隨機指標 (stochastic)、動量 (momentum)，共 7 種；皆含單元測試

### 變更

- 介面改為分頁：「儀表板」與「K 線圖」。K 線圖獨立整頁、可拖拉調整高度
- Bot 頭像改為 Cyberpunk 機器人風格（深色底 + 霓虹色機器人臉，主色/眼睛色由 seed 決定）
- Bot 列表改為 4 欄卡片網格，每張卡顯示頭像與績效欄位（勝率/報酬率/交易次數/最大回撤，目前留空待串接）
- 網頁改為滿版（移除左右過寬留白）

### 修正

- `alpaca_client.py` 改為延遲初始化：不再於 import 時就建立需要金鑰的 Alpaca
  client。修正沒有 `.env`/金鑰的環境（如 CI）光是 import 服務層就因
  `ValueError: You must supply a method of authentication` 崩潰、導致
  `test_backtest.py` 收集失敗的問題。

---

## [0.1.0] - 2026-06-01

第一個版本：Phase 1 核心骨架完成。

### 新增

- 專案基礎建設：`CLAUDE.md`、`.gitignore`、`.env.example`、`requirements.txt`
- 設定管理 `config.py`（讀取 `.env`，含 Windows UTF-8 主控台修正）
- 資料庫層 `database.py`（SQLite + SQLAlchemy）
- 資料模型：`Bot`（交易機器人設定）、`TradeLog`（交易紀錄）
- Alpaca API 封裝 `alpaca_client.py`（查帳戶、下單、抓 K 線、查報價）
- 通知服務 `notifier.py`（LINE Messaging API，未設定時降級為主控台輸出）
- 交易策略（4 種，皆用 pandas 自算指標）：
  - 均線交叉 `ma_crossover`
  - RSI `rsi`
  - MACD `macd`
  - 布林通道 `bollinger`
- 策略註冊表機制（新增策略只需登記一行）
- Bot 管理器 `bot_manager.py`（執行策略 + APScheduler 定時排程）
- FastAPI 後端 `main.py`：健康檢查、查帳戶、Bot CRUD、手動執行、交易紀錄
- 連線測試腳本 `test_connection.py`
- 單元測試：10 個策略測試（涵蓋 4 種策略的買/賣/觀望情境）
- GitHub Actions CI：push / PR 時自動跑測試

### 變更

- 交易 API 套件從已停止維護的 `alpaca-trade-api` 改為官方新版 `alpaca-py`
- 技術指標改用 pandas 自算，避開 ta-lib 在 Windows 難安裝的問題

### 修正

- `get_latest_price` 改用「最新成交價」而非買賣報價中間值，
  避免休市時 ask=0 導致下單股數計算錯誤
