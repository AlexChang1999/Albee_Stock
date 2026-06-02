# Albee Stock — 美股自動交易策略機器人系統

## 專案簡介

多 Bot 交易系統，每個 Bot 獨立運行一種交易策略。
系統在本機 Windows 11 運行，但必須易於搬遷到其他電腦。

## 技術棧

- **後端**: Python 3.13 + FastAPI
- **前端**: React (Vite)
- **資料庫**: SQLite (開發) → 未來可換 PostgreSQL
- **交易 API**: Alpaca Markets API (免費版)
- **即時報價**: Alpaca WebSocket
- **回測引擎**: backtrader
- **通知**: LINE Notify → 未來擴充 Discord / Telegram
- **任務排程**: APScheduler

## 關鍵 Python 套件

| 用途 | 套件 |
|------|------|
| Web 框架 | fastapi, uvicorn |
| 交易 API | alpaca-py（官方新版；舊的 alpaca-trade-api 已停止維護） |
| 資料處理 | pandas, numpy |
| 技術指標 | 用 pandas 自算（避開 ta-lib 在 Windows 難安裝的問題） |
| 回測 | backtrader |
| 通知 | line-bot-sdk, requests |
| 排程 | apscheduler |
| 資料庫 ORM | sqlalchemy |
| 環境變數 | python-dotenv |

## 專案結構（現況）

> 反映實際檔案，非原始規劃。

```
Albee_Stock/
├── CLAUDE.md              # 專案說明（給 Claude Code 的上下文）
├── README.md              # GitHub 說明文件
├── CHANGELOG.md           # 變更紀錄
├── .env.example           # 環境變數範本（不含真實金鑰）
├── requirements.txt       # Python 依賴
├── setup.bat              # 一鍵安裝依賴 + 跑資料庫遷移
├── start_backend.bat      # 一鍵啟動後端
├── start_frontend.bat     # 一鍵啟動前端
├── alembic.ini            # Alembic 設定
├── alembic/               # 資料庫遷移
│   ├── env.py             # 接專案 config 的 DATABASE_URL + model metadata
│   └── versions/          # 每次 schema 變更一個遷移檔
├── docs/
│   └── skill-guidelines.md    # 撰寫 Skill 的守則
├── backend/
│   ├── main.py            # FastAPI 入口（建 app + CORS + 掛 router；基本端點 / 與 /account）
│   ├── config.py          # 設定管理（讀 .env）
│   ├── database.py        # 資料庫連線設定
│   ├── test_connection.py # Alpaca 連線測試腳本
│   ├── routers/           # API 路由（依功能拆檔）
│   │   ├── bots.py        # Bot 管理（CRUD/啟停/執行/績效）
│   │   ├── backtest.py    # 回測 API
│   │   └── orders.py      # 交易紀錄 API
│   ├── models/            # SQLAlchemy 資料模型
│   │   ├── bot.py         # Bot 模型
│   │   └── trade.py       # 交易紀錄模型
│   ├── services/          # 業務邏輯
│   │   ├── alpaca_client.py   # Alpaca API 封裝（延遲初始化）
│   │   ├── backtest_engine.py # 回測引擎
│   │   ├── performance.py     # Bot 績效指標計算
│   │   └── notifier.py        # 通知服務（LINE 等）
│   ├── strategies/        # 交易策略模組（每個策略一個檔案）
│   │   ├── base.py        # 策略基底類別
│   │   ├── ma_crossover.py    # 均線交叉
│   │   ├── rsi.py             # RSI
│   │   ├── macd.py            # MACD
│   │   ├── bollinger.py       # 布林通道
│   │   ├── donchian.py        # 唐奇安通道（突破）
│   │   ├── momentum.py        # 動量
│   │   └── stochastic.py      # KD 隨機指標
│   └── bots/
│       └── bot_manager.py # 管理所有 Bot 的啟停
├── frontend/              # React 前端（Vite，已模組化拆分）
│   ├── .env.example          # 前端環境變數範本（VITE_API_URL）
│   └── src/
│       ├── App.jsx            # 主畫面編排層（state + handler + 分頁）
│       ├── theme.js           # MUI 主題 + NEON 色票
│       ├── constants.js       # 共用常數（策略清單 STRATEGIES）
│       ├── api.js             # 前端 API 呼叫（讀 VITE_API_URL）
│       ├── BotAvatar.jsx      # Bot 頭像元件
│       ├── TradingViewChart.jsx  # K 線圖元件（App 以 React.lazy 延遲載入）
│       ├── components/        # 畫面區塊元件
│       │   ├── Header / AccountCard / CreateBotForm / BotList
│       │   ├── BacktestPanel / TradesTable / EditBotDialog
│       │   ├── ConfirmDialog / Stat
│       │   └── *.test.jsx     # 元件測試（Vitest + RTL）
│       ├── hooks/             # 自訂 Hook
│       │   └── useDashboardData.js  # 載入 account/bots/trades
│       ├── utils/             # 純函式工具（好寫測試）
│       │   └── botStats.js (+ botStats.test.jsx)
│       └── test/             # 測試環境設定（setup.js）
├── tests/                 # 測試（pytest，扁平結構）
│   ├── test_strategies.py
│   ├── test_backtest.py
│   ├── test_performance.py
│   └── test_api.py
```

## 開發階段

| 階段 | 內容 | 狀態 |
|------|------|------|
| Phase 1 | 核心基礎：資料串接 + 策略 Bot + 通知 | ✅ 完成 |
| Phase 2 | Web UI + 回測引擎 | ✅ 完成（前端 + TradingView 看板 + 回測引擎） |
| Phase 3 | 多 Bot 管理 + 更多策略 | ✅ 完成（Bot CRUD/啟停、績效指標、7 種策略、分頁式 UI、CI） |
| Phase 4 | 自動交易監聽系統 + 實盤切換準備 | ✅ 完成（風控欄位 + 止盈/止損/追蹤止損出場、追蹤止損最高價持久化、開市判斷、實盤雙閘安全閥、Alembic 遷移、監聽狀態可視化、Discord 通知） |
| Phase 5 | 策略工作台 + Claude 思考助手 + 期望值最優 | 🚧 規劃中（見 [`docs/roadmap-strategy-workbench.md`](docs/roadmap-strategy-workbench.md)） |

## 重要規則

- **絕對不要**把 `.env` 檔案提交到 Git（包含 API Key）
- 所有交易先走 **Paper Trading**（模擬），除非使用者明確切換
- 實盤下單有**雙閘安全閥**：須同時「`ALPACA_BASE_URL` 用實盤網址」+「`ALLOW_LIVE_TRADING=true`」
  才會送真錢單，否則 `submit_market_order` 直接拒絕（防手滑燒錢）
- 程式碼要加**中文註解**，幫助學習理解
- 策略模組要**鬆耦合**，能獨立新增/修改/停用
- **每次有意義的變更都要更新 `CHANGELOG.md`**（記到「未發布」區塊）

## 環境變數（.env 需要的欄位）

```
ALPACA_API_KEY=你的_API_Key
ALPACA_SECRET_KEY=你的_Secret_Key
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Paper Trading
ALLOW_LIVE_TRADING=false  # 實盤安全閥：true 才允許真錢下單（預設關）
LINE_CHANNEL_ACCESS_TOKEN=你的_LINE_Token
LINE_CHANNEL_SECRET=你的_LINE_Secret
```

## 常用指令

> 以下都在「專案根目錄」執行。本機用 venv 虛擬環境，python 在 `venv\Scripts\`。

> 懶人版：根目錄有 `setup.bat`（裝依賴）、`start_backend.bat`、`start_frontend.bat` 可直接雙擊。

```powershell
# 安裝依賴
venv\Scripts\python.exe -m pip install -r requirements.txt

# 測試 Alpaca 連線（先確認金鑰有效）
venv\Scripts\python.exe backend\test_connection.py

# 執行策略單元測試（不需連線）
venv\Scripts\python.exe tests\test_strategies.py

# 啟動後端（注意：從根目錄、用 backend.main:app）
venv\Scripts\uvicorn.exe backend.main:app --reload
# 啟動後開 http://127.0.0.1:8000/docs 看 API 文件

# 啟動前端（Phase 2 之後）
cd frontend && npm run dev
```

## 已知注意事項（踩過的坑）

- **Alpaca 套件**：用 `alpaca-py`，不是舊的 `alpaca-trade-api`。
  - 交易：`from alpaca.trading.client import TradingClient`
  - 資料：`from alpaca.data.historical import StockHistoricalDataClient`
- **Windows 主控台編碼**：預設 cp950 印 emoji/中文會崩潰。
  已在 `backend/config.py` 開頭用 `sys.stdout.reconfigure(encoding="utf-8")` 修正；
  獨立腳本（如 test_connection.py）需自行加同樣修正。
- **API 金鑰格式**：有效的 Paper 金鑰開頭是 `PK`（約 20 碼），Secret 約 40 碼。
  太短的金鑰會得到 `unauthorized.`。
- **資料庫 schema 變更走 Alembic，別再手動 `ALTER TABLE`**：
  - 改完 `models/` 的欄位後，標準流程：
    ```powershell
    venv\Scripts\alembic.exe revision --autogenerate -m "說明改了什麼"
    # 打開 alembic\versions\ 新產生的檔，人工檢查無誤後：
    venv\Scripts\alembic.exe upgrade head
    ```
  - 新電腦/全新 DB：`venv\Scripts\alembic.exe upgrade head` 一行建好（`setup.bat` 已含）。
  - **SQLite 必備坑**：`alembic/env.py` 已設 `render_as_batch=True`。SQLite 的 `ALTER`
    很弱（不能改/刪欄位），沒開 batch 模式，未來改欄位的遷移會失敗。
  - DB 連線讀 `config.py` 的 `DATABASE_URL`（可由 `.env` 覆寫）。未來換 PostgreSQL
    只要在 `.env` 設 `DATABASE_URL=postgresql://...`，程式不用改。

## 可用的 MCP Server

### Alpaca MCP（官方）

已安裝 Alpaca 官方 MCP Server，讓 Claude 能用自然語言直接操作 Alpaca 帳戶。

- **來源**：[alpacahq/alpaca-mcp-server](https://github.com/alpacahq/alpaca-mcp-server)
- **執行方式**：`uvx alpaca-mcp-server`（依賴由 uv 自動管理）
- **安裝設定**：用 `claude mcp add alpaca --scope local ...` 加入，金鑰存使用者層級
  設定（`~/.claude.json`），**不進 git**。`ALPACA_PAPER_TRADE=true` 鎖定 Paper 模式。
- **重灌指令**（新電腦/重設時，金鑰自己填，別 commit）：
  ```
  claude mcp add alpaca --scope local \
    --env ALPACA_API_KEY=你的Key \
    --env ALPACA_SECRET_KEY=你的Secret \
    --env ALPACA_PAPER_TRADE=true \
    -- uvx alpaca-mcp-server
  ```

**能做什麼**（自然語言驅動，免寫程式）：

| 類別 | 範例問法 |
|------|----------|
| 帳戶查詢 | 「看我的帳戶餘額和購買力」 |
| 持倉查詢 | 「我現在持有哪些部位？」 |
| 即時報價 | 「AAPL 現在多少錢？」 |
| 歷史資料 | 「給我 TSLA 過去 30 天日線」 |
| 下單（Paper） | 「用市價買 1 股 NVDA」 |
| 查訂單 | 「列出今天所有未成交訂單」 |

**用途定位**：開發/研究時的快速試手工具——查帳戶、抓資料、下測試單，
不用切到後端 API 或寫 script。正式自動交易邏輯仍走 `backend/`（FastAPI + 策略模組）。

⚠️ **安全**：目前鎖 Paper（模擬）。切實盤要把 `ALPACA_PAPER_TRADE` 改 `false`，
風險自負，務必想清楚。真實金鑰絕不貼進對話或 commit。

## 撰寫 Skill

要新增 Skill（放在 `.claude/skills/`）時，請先讀 [`docs/skill-guidelines.md`](docs/skill-guidelines.md)：
避坑指南、漸進式揭露、記憶能力、按需觸發的危險操作 Hook 四大原則。
