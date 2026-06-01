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

## 專案結構（規劃）

```
Albee_Stock/
├── CLAUDE.md              # 專案說明（給 Claude Code 的上下文）
├── README.md              # GitHub 說明文件
├── .env.example           # 環境變數範本（不含真實金鑰）
├── .gitignore             # Git 忽略規則
├── requirements.txt       # Python 依賴
├── backend/
│   ├── main.py            # FastAPI 入口
│   ├── config.py          # 設定管理（讀 .env）
│   ├── database.py        # 資料庫連線設定
│   ├── models/            # SQLAlchemy 資料模型
│   ├── routers/           # API 路由
│   │   ├── bots.py        # Bot 管理 CRUD
│   │   ├── backtest.py    # 回測 API
│   │   └── orders.py      # 訂單紀錄 API
│   ├── services/          # 業務邏輯
│   │   ├── alpaca_client.py   # Alpaca API 封裝
│   │   ├── data_feed.py       # 即時/歷史資料取得
│   │   ├── backtest_engine.py # 回測引擎
│   │   └── notifier.py       # 通知服務（LINE 等）
│   ├── strategies/        # 交易策略模組（每個策略一個檔案）
│   │   ├── base.py        # 策略基底類別
│   │   ├── ma_crossover.py    # 均線交叉策略
│   │   ├── rsi.py             # RSI 策略
│   │   ├── macd.py            # MACD 策略
│   │   ├── bollinger.py       # 布林通道策略
│   │   └── breakout.py        # 突破策略
│   └── bots/              # Bot 管理器
│       └── bot_manager.py # 管理所有 Bot 的啟停
├── frontend/              # React 前端（Vite）
│   ├── src/
│   │   ├── pages/         # 頁面元件
│   │   ├── components/    # 共用元件
│   │   └── api/           # 前端 API 呼叫
│   └── ...
├── tests/                 # 測試
│   ├── test_strategies/
│   └── test_services/
└── docs/                  # 文件
```

## 開發階段

| 階段 | 內容 | 狀態 |
|------|------|------|
| Phase 1 | 核心基礎：資料串接 + 策略 Bot + 通知 | ✅ 完成 |
| Phase 2 | Web UI + 回測引擎 | ✅ 完成（前端 + TradingView 看板 + 回測引擎） |
| Phase 3 | 多 Bot 管理 + 更多策略 | 🔲 未開始 |
| Phase 4 | 實盤交易切換 | 🔲 未開始 |

## 重要規則

- **絕對不要**把 `.env` 檔案提交到 Git（包含 API Key）
- 所有交易先走 **Paper Trading**（模擬），除非使用者明確切換
- 程式碼要加**中文註解**，幫助學習理解
- 策略模組要**鬆耦合**，能獨立新增/修改/停用
- **每次有意義的變更都要更新 `CHANGELOG.md`**（記到「未發布」區塊）

## 環境變數（.env 需要的欄位）

```
ALPACA_API_KEY=你的_API_Key
ALPACA_SECRET_KEY=你的_Secret_Key
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Paper Trading
LINE_CHANNEL_ACCESS_TOKEN=你的_LINE_Token
LINE_CHANNEL_SECRET=你的_LINE_Secret
```

## 常用指令

> 以下都在「專案根目錄」執行。本機用 venv 虛擬環境，python 在 `venv\Scripts\`。

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
