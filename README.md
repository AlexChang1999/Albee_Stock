# Albee Stock — 美股自動交易策略機器人系統

多 Bot 架構的美股自動交易系統，每個 Bot 獨立運行一種交易策略。
從 Alpaca **Paper Trading（模擬交易）** 開始，安全地驗證策略，未來可切換實盤。

> ⚠️ 本專案僅供學習與研究，不構成投資建議。交易有風險，請自行評估。

## 技術棧

- **後端**：Python 3.13 + FastAPI
- **前端**：React (Vite) + Material UI + 左側 sidebar 多頁路由（react-router）+ 原生圖表 `lightweight-charts`
- **資料庫**：SQLite（用 **Alembic** 做版本化遷移，未來可換 PostgreSQL）
- **交易/資料 API**：[Alpaca Markets](https://alpaca.markets)（`alpaca-py` 官方 SDK）
- **回測**：自製 walk-forward 回測引擎（含**期望值 EV** 指標）
- **排程**：APScheduler
- **通知**：LINE Messaging API、Discord Webhook（選用）
- **LLM 助手**：OpenAI 相容介面，預設接**本機 Ollama**（免費、離線），可改 `.env` 換供應商

## 目前進度

| 階段 | 內容 | 狀態 |
|------|------|------|
| Phase 1 | 核心基礎：資料串接 + 策略 Bot + 通知 | ✅ 完成 |
| Phase 2 | Web UI + 回測引擎 | ✅ 完成 |
| Phase 3 | 多 Bot 管理 + 更多策略（8 種） | ✅ 完成 |
| Phase 4 | 自動交易監聽系統 + 實盤切換準備 | ✅ 完成 |
| Phase 5 | 策略工作台 + 本機 LLM 思考助手 + 期望值最優 | ✅ 完成（含選配：一鍵轉 Bot + 主動提醒；tool_calls 顯示因架構改記憶注入已棄做） |
| Phase 6 | 可信度地基（回測 EV ≈ 實盤 EV：成本/隔日/OOS/統一資料路徑/組合風控/決策審計） | ✅ 完成（step-01~10） |
| Phase 7 | 自適應市場狀態（狀態辨識→選策略 + 分數凱利 + meta-labeling + 防過擬合驗證） | ✅ 完成（step-01~07） |
| Phase 8 | 策略知識庫 + 組合進化（蒐集多策略→整合組合→驗證→人在迴路策展） | ✅ 完成（step-01~06） |
| Phase 9 | 專業前端工作站（左側導覽 + 多頁面：交易/回測/方案/探討/決策/進化/知識庫） | ✅ 完成（step-01~08） |

> 另有「改版子軌（redesign）」Phase 1–4，是 Phase 2~4 的「AI 終端機改版」子軌（圖表/AI 推薦/深藍主題/自動化），✅ 已落地，與上表主線編號不同（詳見下方說明與 [`docs/redesign/`](docs/redesign/README.md)）。

**已完成**：專案骨架、**9 種策略**（均線交叉／RSI／MACD／布林通道／唐奇安通道／KD 隨機指標／動量／威廉指標／ADX 趨勢）、
Bot CRUD + 啟停、績效指標（勝率/報酬率/交易次數/最大回撤）、walk-forward 回測引擎、
**風控出場**（止盈/止損/追蹤止損，最高價持久化）、**開市判斷**、**實盤雙閘安全閥**、
**監聽狀態可視化**（最後檢查時間/持倉峰值）、Alembic 遷移、分頁式 React 前端（模組化）、
前後端單元測試、GitHub Actions CI。

**Phase 5 已落地**（roadmap：[`docs/roadmap-strategy-workbench.md`](docs/roadmap-strategy-workbench.md)）：
- 「**策略工作台**」（方案/回測/EV歷史/LLM助手）——Phase 9 已把內容拆進各自頁面（`/presets`、`/backtest-runs`）與助手抽屜，舊的右側 `StrategyWorkbench` 元件已移除
- **策略方案（Preset）** CRUD + 一鍵 Python 回測，結果寫入 `backtest_runs`
- 回測歷史用**期望值 EV**（非勝率）排序挑最優，含 profit factor、expectancy
- **本機 LLM 思考助手**（預設 Ollama，免費）：設計 / 微調 / 事後檢討
- **檔案化探討記憶** `explorations/`：每次檢討存一檔 + `INDEX.md` 路標，
  助手先掃路標挑相關舊探討再寫新檢討（兩段式、讀歷史越來越聰明）

**Phase 6 已落地**（可信度地基，藍圖：[`docs/phase-6/`](docs/phase-6/README.md)）——讓「回測看到的 EV」
是「實盤拿得到的 EV」的誠實估計，且每筆自動決策可追溯、可熔斷：
- **回測誠實化**：統一資料路徑（實盤 = 回測同源同回看）、成本模型（手續費 + 滑價）、隔日成交語意、
  **樣本外（OOS）EV** 排名挑冠軍（防過擬合）
- **組合層風控**：購買力守門（`capital.plan_capital`）、回撤熔斷（`circuit_breaker`，只擋進不擋出）
- **AI 情緒入決策**：第二層 LLM 情緒當「否決閘 + 次要加權」（EV 為主、情緒為輔）
- **決策審計軌跡**：`DecisionLog` 留下每個時點「為何買/賣/不動」（含沒成交的觀望/跳過）
- **排程每輪重查 Bot**：改風控/參數對執行中的 Bot 立即生效，不必重啟

**Phase 7 已落地**（自適應市場狀態，藍圖：[`docs/phase-7-adaptive-regime/`](docs/phase-7-adaptive-regime/README.md)）——
讓系統先認市場「現在是什麼狀態」再決定怎麼打，並用防過擬合框架誠實檢查每層加分值不值得留：
- **狀態辨識 → 選策略**（step-01~03）：`regime_features` 算特徵 → `regime.classify_regime` 分類 →
  `strategy_selector` 依「狀態→策略對照表」選當下最適策略
- **分數凱利部位**（step-04，`sizing`）：用 OOS 勝率/賠率算凱利分數，控制部位大小（僅自動部署流）
- **meta-labeling 二級過濾**（step-05，`meta_label`）：BUY 訊號再過一層信心閘，不足則降為 HOLD
- **事件風險閘**（step-06，`event_risk`）：事件期只當風險煞車（不猜方向）
- **防過擬合驗證框架**（step-07 + 收尾 harness）：`validation` 的 walk-forward / purged k-fold +
  `layer_validation` 對每層做 baseline-vs-candidate 樣本外比較，`is_layer_worth_it` 誠實判決去留
  （實測：meta ✅ 過、adaptive ❌、kelly ❌、event ⚪ 不可驗證——機制就位，加分待續調）

**Phase 8 已落地**（策略知識庫 + 組合進化，藍圖：[`docs/phase-8-strategy-evolution/`](docs/phase-8-strategy-evolution/README.md)）——
把「蒐集多策略 → 整合組合 → 驗證 → 人在迴路策展」串成閉環：
- **策略知識庫**（step-01）：依理論/場景存策略說明，含 OOS 指標、狀態親和性、使用時機
- **LLM 策略提案 + 組合引擎**（step-02~03）：本機 Ollama 提案候選 + 把多個已驗證子策略組成 `CompositeStrategy`
- **自動驗證管線**（step-04）：候選一律過 Phase 6 OOS + Phase 7 step-07 walk-forward / purged CV，只有「OOS 真加分」才通過
- **排行 + 使用時機**（step-05）：依 OOS EV 排序，附「何時該用」說明
- **人在迴路審核**（step-06）：AI 只負責提案/驗證/排序，**晉升（validated→curated）/ 退回一律使用者點按**，理由寫進 `explorations/`

**Phase 9 已落地**（專業前端工作站，藍圖：[`docs/phase-9-frontend-workstation/`](docs/phase-9-frontend-workstation/README.md)）——
把「全擠在一個儀表板分頁 + 右側工作台」重構成左側 sidebar 分區的多頁終端機：
- **導覽重構**（step-01）：上方 Tabs → 左側 sidebar + react-router 多頁；儀表板瘦身成純監控中心
- **多頁面**（step-02~07）：交易紀錄 `/trades`、回測歷史 `/backtest-runs`、策略方案 `/presets`、探討檢討 `/explorations`（+ 新增 GET 端點）、決策審計 `/decisions`、進化實驗室 `/evolution`、策略知識庫 `/library`
- **思考助手改全站抽屜**（step-08）：右下浮動鈕開關，並**拆除**舊的右側 `StrategyWorkbench`（內容已各自有家）

**改版子軌（redesign）已落地**（AI 終端機改版，藍圖：[`docs/redesign/`](docs/redesign/README.md)）——
Phase 2~4 的視覺/自動化子軌（編號與主線不同）：
- **原生圖表**（P1）：`lightweight-charts` 取代 TradingView iframe，可畫進場/止損/追蹤止盈水位線（可拖曳連動 DB）+ 2x2 網格盯盤
- **AI 推薦資料流**（P2）：漏斗式海選（量能 → 本機 LLM 情緒 → EV）+ `/ai-recommendations` + 一鍵 Deploy
- **深藍主題**（P3）：深海軍藍沉浸金融風，移除手填「建立 Bot」表單，儀表板改純監控
- **模式 B 全自動護欄**（P4）：EV 閾值排程自動建 Bot（總開關預設關、與實盤雙閘獨立、全程 Paper），前端 `AutomationPanel` 唯讀規則 + 手動試跑

> 系統工作流全貌見 [`docs/workflow-diagrams.md`](docs/workflow-diagrams.md)（Mermaid 畫的 4 張圖：
> 高層全景 / 決策流水線 / 回測 EV / 層驗證）。

**後續 / 未竟（非阻塞，未承諾時程）**：
- ~~**Phase 5 選配**：主動提醒、好策略一鍵轉 Bot、助手 tool_calls 顯示~~ ✅ 完成（好策略一鍵轉
  Bot `POST /presets/{id}/to-bot` + 主動提醒 `GET /reminders`；**tool_calls 顯示已棄做**——助手早改成
  「記憶預先注入 system 提示」、不再用 tool-use，無 tool_calls 可顯示）
- **Phase 7 層加分續調**：`adaptive` / `kelly` 樣本外未加分、`event` 不可驗證——機制已就位，待更多資料/調參再決定去留
- ~~**redesign 後續**：自動化規則由 `.env` 改 DB 表~~ ✅ 完成（`automation_config` 單列表 + `PUT /automation` 前端可編輯）
- **實盤上線前必讀**：[`docs/human-vs-ai-operation.md`](docs/human-vs-ai-operation.md)（人機操作落差 + 分階段上線）

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
- `GET /bots/{id}/decisions`：查該 Bot 的決策審計軌跡（Phase 6，含「沒成交但有決策」的時點）
- `POST /backtest`：對某策略跑回測
- `GET /trades`：查交易紀錄
- `GET /strategies`：列出可用策略 `[{value,label}]`（Phase 6，策略清單單一來源）

**策略工作台（Phase 5）**

- `GET/POST/PUT/DELETE /presets`：策略方案（參數組合）CRUD
- `POST /presets/{id}/backtest`：用方案跑回測並存入歷史
- `GET /backtest-runs`：回測歷史（依**期望值 EV** 排序，可篩最愛）
- `PUT /backtest-runs/{id}/favorite`：標記/取消最愛
- `POST /chat`：與本機 LLM 助手對話（注入帳戶/方案/EV歷史/探討路標當上下文）
- `POST /chat/postmortem`：對某筆回測做事後檢討，寫入 `explorations/` 檔案記憶

**AI 探勘 / 自動化 / 圖表（redesign 子軌）**

- `GET /ai-recommendations`：漏斗式海選（量能 → 情緒 → EV）回傳值得部署的策略推薦
- `GET /automation`：看模式 B 自動化規則與名額（由 `.env` 的 `AUTO_DEPLOY_*` 設定）
- `POST /automation/run`：手動觸發一輪自動部署（`?dry_run=true` 只預覽、`?force=true` 略過總開關）
- `GET /bars/{symbol}`：歷史日 K 線（給原生圖表 `lightweight-charts`）
- `GET /quotes/{symbol}`：一次性最新報價（即時報價另走 WebSocket）
- `GET /fundamentals/{symbol}`、`/financials`、`/news`、`/actions`：基本面/財報/新聞

**探討記憶 / 策略知識庫（Phase 8/9）**

- `GET /explorations`、`GET /explorations/{name}`：探討/檢討檔案記憶（唯讀路標 + 內容）
- `GET /knowledge`、`GET /knowledge/ranking`、`GET /knowledge/{id}`：策略知識庫（可依狀態/OOS EV 排序）
- `POST /knowledge/{id}/validate`：跑 OOS + walk-forward 驗證管線
- `POST /knowledge/{id}/promote`、`POST /knowledge/{id}/reject`：人在迴路晉升/退回

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

可用的 `strategy`：`ma_crossover`、`rsi`、`macd`、`bollinger`、`donchian`、`stochastic`、`momentum`、`williams_r`、`adx_trend`
（完整清單以 `GET /strategies` 為準）

> 風控欄位（`take_profit_pct`／`stop_loss_pct`／`trailing_stop_pct`）皆為小數百分比、可不填（None=不啟用）。

## 專案結構

```
Albee_Stock/
├── backend/
│   ├── config.py            # 設定管理（讀 .env，含實盤安全閥）
│   ├── database.py          # SQLite 連線
│   ├── main.py              # FastAPI 入口（CORS + 掛 router + lifespan 恢復排程）
│   ├── test_connection.py   # Alpaca 連線測試
│   ├── routers/             # API 路由（bots / backtest / orders / presets / chat / automation / strategies …）
│   ├── models/              # 資料模型（Bot、TradeLog、StrategyPreset、BacktestRun、DecisionLog、PortfolioState）
│   ├── services/            # Alpaca 封裝、回測引擎、optimizer、screener、自動部署、資金守門 capital、
│   │                        #   回撤熔斷 circuit_breaker、績效、風控、通知、LLM、探討檔案記憶；
│   │                        #   Phase 7：regime_features/regime/strategy_selector/meta_label/
│   │                        #   sizing(凱利)/event_risk/validation/layer_validation
│   ├── strategies/          # 9 種交易策略 + 註冊表 + 顯示名（list_strategies 單一來源）
│   └── bots/                # Bot 管理器（執行 + 排程；每輪用 bot_id 重查最新設定）
├── frontend/                # React 前端（Vite，模組化；左側 sidebar + react-router 多頁）
│   └── src/
│       ├── api.js           # 後端 API 呼叫層（讀 VITE_API_URL）
│       ├── App.jsx          # 路由編排層（state + handler + <Outlet context> 分配給各頁）
│       ├── pages/           # 各路由頁（Dashboard/Trades/BacktestRuns/Presets/Explorations/
│       │                    #   Decisions/Evolution/Library/AiExplore/Charts/Fundamentals…）
│       ├── components/      # 畫面區塊元件 + 測試（SidebarLayout 導覽外殼、AssistantDrawer 助手抽屜、
│       │                    #   AccountCard/BotList/AutomationPanel、LightweightChart/ChartGrid 原生圖表…）
│       ├── hooks/ utils/    # 自訂 Hook、純函式工具（好測試）
│       └── ...
├── explorations/            # 思考助手的「探討/檢討」檔案記憶（INDEX.md 路標 + 每筆一檔）
├── alembic/                 # 資料庫遷移
├── tests/                   # 後端單元測試（pytest）
├── docs/                    # 專案文件（skill 守則、roadmap、phase 藍圖、workflow-diagrams 工作流圖…）
├── scripts/                 # 輔助腳本（validate_layers.py 層驗證 CLI…）
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
