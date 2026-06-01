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
