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
