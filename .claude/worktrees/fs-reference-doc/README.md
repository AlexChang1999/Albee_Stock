# Albee Stock — 美股自動交易策略機器人系統

多 Bot 架構的美股自動交易系統，每個 Bot 獨立運行一種交易策略。
從 Alpaca **Paper Trading（模擬交易）** 開始，安全地驗證策略，未來可切換實盤。

> ⚠️ 本專案僅供學習與研究，不構成投資建議。交易有風險，請自行評估。

## 技術棧

- **後端**：Python 3.13 + FastAPI
- **前端**：React (Vite) + Material UI
- **資料庫**：SQLite（用 **Alembic** 做版本化遷移，未來可換 PostgreSQL）
- **交易/資料 API**：[Alpaca Markets](https://alpaca.markets)（`alpaca-py` 官方 SDK）
- **回測**：自製 walk-forward 回測引擎
- **排程**：APScheduler
- **通知**：LINE Messaging API、Discord Webhook（選用）

## 目前進度

| 階段 | 內容 | 狀態 |
|------|------|------|
| Phase 1 | 核心基礎：資料串接 + 策略 Bot + 通知 | ✅ 完成 |
| Phase 2 | Web UI + 回測引擎 | ✅ 完成 |
| Phase 3 | 多 Bot 管理 + 更多策略（7 種） | ✅ 完成 |
| Phase 4 | 自動交易監聽系統 + 實盤切換準備 | ✅ 完成 |
| Phase 5 | 策略工作台 + Claude 思考助手 + 期望值最優 | 🚧 規劃中 |

**已完成**：專案骨架、**7 種策略**（均線交叉／RSI／MACD／布林通道／唐奇安通道／KD 隨機指標／動量）、
Bot CRUD + 啟停、績效指標（勝率/報酬率/交易次數/最大回撤）、walk-forward 回測引擎、
**風控出場**（止盈/止損/追蹤止損，最高價持久化）、**開市判斷**、**實盤雙閘安全閥**、
**監聽狀態可視化**（最後檢查時間/持倉峰值）、Alembic 遷移、分頁式 React 前端（模組化）、
前後端單元測試、GitHub Actions CI。

**Phase 5 規劃**：見 [`docs/roadmap-strategy-workbench.md`](docs/roadmap-strategy-workbench.md)
（右側可伸縮「策略工作台」、Python 一鍵回測、用**期望值 EV** 而非勝率挑最優策略、
Claude 助手負責設計/微調/事後檢討並讀回測歷史越來越聰明）。

## 安裝與設定

### 1. 取得 Alpaca Paper Trading 金鑰

1. 到 [alpaca.markets](https://alpaca.markets) 註冊並登入
2. 切換到 **Paper Trading**（模擬交易）
3. 在右側 **API Keys** 產生金鑰
   - API Key 開頭通常是 `PK`，約 20 碼
   - Secret Key 約 40 碼（**只會顯示一次**，請馬上複製）

### 2. 設定 .env

```powershell
copy .env.example .env
```

編輯 `.env`，填入金鑰（不要加引號、不要有多餘空格）。
實盤安全閥 `ALLOW_LIVE_TRADING` 預設 `false`，**請保持關閉**直到充分驗證策略。

### 3. 安裝套件 + 建立資料庫

```powershell
# 懶人版：根目錄雙擊 setup.bat（會裝依賴 + 跑資料庫遷移）

# 或手動：
python -m venv venv                                      # 建虛擬環境（只需一次）
venv\Scripts\python.exe -m pip install -r requirements.txt  # 後端依賴
venv\Scripts\alembic.exe upgrade head                    # 建立/更新資料庫 schema
cd frontend && npm install && cd ..                      # 前端依賴
```

> **資料庫 schema 變更一律走 Alembic**，不要手動 `ALTER TABLE`。
> 改了 `backend/models/` 後：`alembic revision --autogenerate -m "說明"` → 檢查 → `alembic upgrade head`。

## 使用方式

```powershell
# 懶人版：雙擊 start_backend.bat 與 start_frontend.bat

# 或手動：
venv\Scripts\python.exe backend\test_connection.py       # 1) 測 Alpaca 連線
venv\Scripts\python.exe -m pytest tests/                 # 2) 跑單元測試（不需連線）
venv\Scripts\uvicorn.exe backend.main:app --reload       # 3) 啟動後端（8000 埠）
cd frontend && npm run dev                                # 4) 啟動前端（5173 埠，另開終端機）
```

> 前後端要**同時跑**：後端在 8000 埠提供 API，前端在 5173 埠顯示畫面。

- 後端 API 文件：<http://127.0.0.1:8000/docs>
- 前端畫面：<http://localhost:5173>

### 主要 API

- `GET /status`：查目前環境（模擬/實盤、安全閥狀態）
- `GET /account`：查帳戶餘額
- `GET /bots`：列出所有 Bot（含績效、持倉峰值、最後檢查時間）
- `POST /bots`：建立一個交易 Bot
- `PUT /bots/{id}`、`DELETE /bots/{id}`：編輯／刪除 Bot
- `POST /bots/{id}/run`：讓 Bot 立刻跑一次策略（可休市測試）
- `POST /bots/{id}/start`、`POST /bots/{id}/stop`：啟動／停止定時執行
- `POST /backtest`：對某策略跑回測
- `GET /trades`：查交易紀錄

### 建立 Bot 的範例（POST /bots）

```json
{
  "name": "AAPL 均線交叉",
  "strategy": "ma_crossover",
  "symbol": "AAPL",
  "params": { "short_window": 5, "long_window": 20 },
  "trade_amount": 1000,
  "take_profit_pct": 0.10,
  "stop_loss_pct": 0.05,
  "trailing_stop_pct": 0.03,
  "check_interval_sec": 60
}
```

可用的 `strategy`：`ma_crossover`、`rsi`、`macd`、`bollinger`、`donchian`、`stochastic`、`momentum`

> 風控欄位（`take_profit_pct`／`stop_loss_pct`／`trailing_stop_pct`）皆為小數百分比、可不填（None=不啟用）。

## 專案結構

```
Albee_Stock/
├── backend/
│   ├── config.py            # 設定管理（讀 .env，含實盤安全閥）
│   ├── database.py          # SQLite 連線
│   ├── main.py              # FastAPI 入口（CORS + 掛 router + lifespan 恢復排程）
│   ├── test_connection.py   # Alpaca 連線測試
│   ├── routers/             # API 路由（bots / backtest / orders）
│   ├── models/              # 資料模型（Bot、TradeLog）
│   ├── services/            # Alpaca 封裝、回測引擎、績效、風控、通知
│   ├── strategies/          # 7 種交易策略 + 註冊表
│   └── bots/                # Bot 管理器（執行 + 排程）
├── frontend/                # React 前端（Vite，模組化）
│   └── src/
│       ├── api.js           # 後端 API 呼叫層（讀 VITE_API_URL）
│       ├── App.jsx          # 主畫面編排層
│       ├── components/      # 畫面區塊元件 + 測試
│       ├── hooks/ utils/    # 自訂 Hook、純函式工具（好測試）
│       └── ...
├── alembic/                 # 資料庫遷移
├── tests/                   # 後端單元測試（pytest）
├── docs/                    # 專案文件（skill 守則、roadmap、驗收清單…）
├── .github/workflows/       # GitHub Actions CI
├── setup.bat / start_*.bat  # 一鍵安裝/啟動
├── requirements.txt
├── CHANGELOG.md             # 變更紀錄
└── CLAUDE.md                # 給 Claude Code 的專案上下文
```

## 測試

```powershell
# 後端：全部單元測試
venv\Scripts\python.exe -m pytest tests/

# 前端：Vitest
cd frontend && npm run test
```

每次 push 或開 PR 時，GitHub Actions 會自動跑這些測試。

## 注意事項

- **絕對不要**把 `.env`（含金鑰）提交到 Git。
- 預設走 **Paper Trading**，不會用到真錢。實盤需「實盤網址 + `ALLOW_LIVE_TRADING=true`」**雙閘全開**才會送真錢單。
- Windows 主控台若出現中文/emoji 亂碼，程式已內建 UTF-8 修正。
