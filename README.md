# 📈 Albee Stock — 美股自動交易策略機器人系統

<div align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![SQLite](https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white)

</div>

**⚠️ 本專案僅供學習與研究，不構成投資建議。交易有風險，請自行評估。**

## 專案簡介

多 Bot 架構的美股自動交易系統，每個 Bot 可獨立運行一種交易策略，並支援回測、多維度風控與可視化戰情頁。系統從 Alpaca Paper Trading（模擬交易）出發，讓策略在零風險環境下反覆驗證，具備完整雙重安全閥後才可切換至實盤。

目前已完整落地 10 個開發階段：從核心策略引擎、Web 前端、多 Bot 管理，到回測誠實化、自適應市場狀態辨識、策略知識庫與組合進化，直到具備「編排層 + AI 專員 + 人工核准」的 AI 交易公司雛形。

## 技術棧

| 類別 | 技術 |
|---|---|
| 後端 | Python 3.13 + FastAPI |
| 前端 | React (Vite) + Material UI + lightweight-charts |
| 資料庫 | SQLite + Alembic 遷移 |
| 交易 API | Alpaca Markets (alpaca-py) |
| 回測引擎 | 自製 walk-forward + 期望值 EV 指標 |
| 排程 | APScheduler |
| 通知 | LINE Messaging API / Discord Webhook |
| LLM 助手 | OpenAI 相容介面（預設本機 Ollama） |

## 核心功能

• 9 種內建策略（均線交叉、RSI、MACD、布林通道、唐奇安通道、KD、動量、威廉指標、ADX 趨勢）
• Walk-forward 回測引擎，含期望值（EV）、profit factor 等指標
• 風控出場：止盈 / 止損 / 追蹤止損
• 決策審計軌跡：記錄每個時點「為何買 / 賣 / 不動」
• 自適應市場狀態辨識 + 策略自動挑選 + meta-labeling 二級過濾
• 策略知識庫 + LLM 提案 + 組合驗證引擎（人在迴路審核）
• AI 交易公司戰情頁：機會掃描、市場蒐集員、政治風險煞車、董事會人工核准上真錢
## 安裝與設定

**1. 取得 Alpaca Paper Trading 金鑰**

於 alpaca.markets 註冊並切換至 Paper Trading，於 API Keys 頁面產生金鑰。

**2. 設定環境變數**

```
copy .env.example .env
```

填入 Alpaca 金鑰。實盤安全閥 `ALLOW_LIVE_TRADING` 預設為 `false`，請保持關閉直到策略充分驗證。

**3. 安裝套件並初始化資料庫**

```
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\alembic.exe upgrade head
cd frontend && npm install && cd ..
```

也可直接執行根目錄的 `setup.bat` 一鍵安裝。

## 使用方式

```
venv\Scripts\uvicorn.exe backend.main:app --reload   # 啟動後端（8000）
cd frontend && npm run dev                           # 啟動前端（5173）
```

後端 API 文件：`http://127.0.0.1:8000/docs`
前端戰情頁：`http://localhost:5173`
## 專案結構（節錄）

```
Albee_Stock/
├── backend/         FastAPI 後端（策略 / 回測 / 風控 / LLM 助手）
├── frontend/         React 前端（左側 sidebar 多頁工作站）
├── explorations/     LLM 助手探討記憶
├── alembic/          資料庫遷移
├── tests/            pytest 單元測試
└── docs/             專案文件 / 開發藍圖
```

## 安全須知

• 絕不將 `.env`（含金鑰）提交至 Git
• 預設走 Paper Trading，不涉及真錢；實盤需「實盤網址 + `ALLOW_LIVE_TRADING=true`」雙閘全開才會送出真實委託單
