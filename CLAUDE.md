# Albee Stock — 美股自動交易策略機器人系統

## 專案簡介

多 Bot 交易系統，每個 Bot 獨立運行一種交易策略。
系統在本機 Windows 11 運行，但必須易於搬遷到其他電腦。

## 技術棧

- **後端**: Python 3.13 + FastAPI
- **前端**: React (Vite)
- **資料庫**: Neon 雲端 PostgreSQL（2026-06 起正式使用，多台電腦共用同一份資料；
  `.env` 沒填 `DATABASE_URL` 自動退回本機 SQLite。**新電腦完整設置流程**見
  [`docs/guides/setup-postgres-sync.md`](docs/guides/setup-postgres-sync.md)）
- **交易 API**: Alpaca Markets API (免費版)
- **即時報價**: Alpaca WebSocket
- **回測引擎**: 自寫引擎（`backend/services/backtest_engine.py`，隔日成交 + 含成本；原規劃 backtrader 未採用）
- **通知**: LINE Notify → 未來擴充 Discord / Telegram
- **任務排程**: APScheduler

## 關鍵 Python 套件

| 用途 | 套件 |
|------|------|
| Web 框架 | fastapi, uvicorn |
| 交易 API | alpaca-py（官方新版；舊的 alpaca-trade-api 已停止維護） |
| 資料處理 | pandas, numpy |
| 技術指標 | 用 pandas 自算（避開 ta-lib 在 Windows 難安裝的問題） |
| 回測 | 自寫 `backtest_engine.py`（pandas；未用 backtrader） |
| 通知 | line-bot-sdk, requests |
| 排程 | apscheduler |
| 資料庫 ORM | sqlalchemy |
| 環境變數 | python-dotenv |
| LLM 助手 | openai（OpenAI 相容 SDK，預設指向本機 Ollama，免費；換供應商只改 `.env`） |

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
├── docs/                  # 文件（依用途分四夾；打開先看 README.md 索引）
│   ├── README.md              # 文件地圖（四大分組 + 各檔用途）
│   ├── ai-implementation-guardrails.md  # 開工前必讀：反 slop / 對齊原目標合約
│   ├── remaining-work-backlog.md        # 進行中未完成工作盤點（A~G，可餵 AI）
│   ├── history/               # 完成過的開發藍圖（phase-6~11 + redesign，歷史報告素材）
│   ├── guides/                # 操作教學（setup / 使用說明 / how-to-add-strategy / skill 守則…）
│   ├── reference/             # 概念規格（workflow-diagrams / roadmap / human-vs-ai / strategies…）
│   └── ux/                    # 前端 UX（ux-workflow / ux-audit）
├── scripts/
│   └── validate_layers.py     # 層驗證 CLI（Phase 7：跑 watchlist 印各層 verdict 表）
├── backend/
│   ├── main.py            # FastAPI 入口（建 app + CORS + 掛 router；基本端點 / 與 /account）
│   ├── config.py          # 設定管理（讀 .env）
│   ├── database.py        # 資料庫連線設定
│   ├── test_connection.py # Alpaca 連線測試腳本
│   ├── routers/           # API 路由（依功能拆檔）
│   │   ├── bots.py        # Bot 管理（CRUD/啟停/執行/績效）
│   │   ├── backtest.py    # 回測 API（手動/全自動掃描/蒙地卡羅壓力測試）
│   │   ├── orders.py      # 交易紀錄 API
│   │   ├── positions.py   # 持倉清單 API（GET /positions，含浮動損益；無金鑰優雅回 []）
│   │   ├── presets.py     # 策略方案 CRUD + 一鍵回測 + 回測歷史（依 EV 排序）
│   │   ├── chat.py        # 本機 LLM 思考助手（對話 + 兩段式事後檢討）
│   │   ├── strategies.py  # 策略清單單一來源（GET /strategies，Phase 6 step-10）
│   │   ├── quotes.py / bars.py # 即時報價 / 歷史 K 線（給前端圖表）
│   │   ├── fundamentals.py    # 基本面/財報/新聞（yfinance）
│   │   ├── recommendations.py # AI 海選推薦（redesign P2）
│   │   ├── automation.py      # 模式 B 自動化規則（redesign P4）
│   │   ├── explorations.py    # 探討檔案記憶唯讀端點（Phase 9）
│   │   ├── knowledge.py       # 策略知識庫 CRUD/驗證/晉升（Phase 8）
│   │   ├── company.py         # 公司戰情聚合（Phase 10 step-01）
│   │   ├── opportunities.py   # 常駐機會清單（Phase 10 step-02）
│   │   ├── factors.py         # 因子數值表 + CSV 匯出（Phase 10 step-03）
│   │   ├── collector.py       # 市場蒐集員收件匣（Phase 10 step-04）
│   │   ├── political.py       # 政治事件流 + 風險煞車（Phase 10 step-05）
│   │   ├── promotion.py       # 董事會核准 Bot 上真錢（Phase 10 step-06）
│   │   └── macro.py           # 總經序列查詢（Phase 11，FRED 資料地基）
│   ├── models/            # SQLAlchemy 資料模型
│   │   ├── bot.py         # Bot 模型（含風控欄位 + 保護單 id + tracking 降級欄位）
│   │   ├── trade.py       # 交易紀錄模型
│   │   ├── strategy_preset.py # 策略方案（參數組合）
│   │   ├── backtest_run.py    # 回測歷史（含 EV 指標 + 檢討摘要）
│   │   ├── decision_log.py    # 決策審計軌跡（Phase 6 step-08，含沒成交但有決策的時點）
│   │   ├── portfolio_state.py # 組合權益峰值（Phase 6 step-09 回撤熔斷用，單列持久化）
│   │   ├── automation_config.py # 模式 B 自動化規則（存 DB 可編輯，redesign P4）
│   │   ├── strategy_knowledge.py # 策略知識庫（candidate→validated→curated，Phase 8）
│   │   ├── opportunity.py     # 常駐探勘機會（含 OOS 指標，Phase 10）
│   │   ├── factor_snapshot.py # 因子快照（Phase 10 step-03）
│   │   ├── raw_strategy_find.py # 蒐集員 raw 素材（Phase 10 step-04）
│   │   ├── political_event.py # 政治事件（Phase 10 step-05）
│   │   └── macro_series.py    # 總經序列（FRED，Phase 11）
│   ├── services/          # 業務邏輯
│   │   ├── alpaca_client.py   # Alpaca API 封裝（延遲初始化 + 雙閘 + 保護單/撤單）
│   │   ├── market_data.py     # 統一資料源（回測=實盤同路，Phase 6）
│   │   ├── bar_cache.py       # K 線快取
│   │   ├── yfinance_client.py / fundamentals.py # yfinance 報價備源 / 基本面
│   │   ├── backtest_engine.py # 回測引擎（含期望值 EV + 成本模型 + 隔日成交）
│   │   ├── vectorized_engine.py # 向量化回測（海選加速）
│   │   ├── optimizer.py       # 全自動掃描（策略×參數網格，OOS EV 排名）
│   │   ├── screener.py        # AI 海選漏斗（量能→情緒→EV）
│   │   ├── analytics.py       # 延伸績效指標（Sharpe/Sortino/VaR/CVaR + tear sheet）
│   │   ├── monte_carlo.py     # 蒙地卡羅壓力測試（bootstrap 重抽日報酬）
│   │   ├── performance.py     # Bot 績效指標計算（含每回合報酬配對）
│   │   ├── capital.py         # 組合層資金/購買力守門（Phase 6 step-05，純函式 plan_capital）
│   │   ├── circuit_breaker.py # 組合回撤熔斷（Phase 6 step-09，只擋進不擋出）
│   │   ├── risk_manager.py    # Bot 層止盈/止損/追蹤止損出場（Phase 4）
│   │   ├── decision_context.py # 決策脈絡：市場快照/出場分類/買入假設失效回填（結構化交易日誌）
│   │   ├── protective_orders.py # 券商端 GTC 保護單規劃（backlog H1）
│   │   ├── heartbeat.py       # 每日心跳日報 + dead-man ping（backlog H2）
│   │   ├── tracking.py        # tracking error 對帳 + 自動降級（backlog H3）
│   │   ├── notifier.py        # 通知服務（LINE / Discord）
│   │   ├── quote_stream.py    # Alpaca WebSocket 即時報價
│   │   ├── llm.py             # LLM 客戶端（本機 Ollama，外送閘）
│   │   ├── explorations.py    # 探討/檢討檔案記憶（INDEX 路標 + 內容檔，防路徑穿越）
│   │   ├── regime_features.py # 市場狀態特徵（Phase 7 step-01）
│   │   ├── regime.py          # 狀態分類（Phase 7 step-02）
│   │   ├── strategy_selector.py # 狀態→策略對照表 + 選策略（Phase 7 step-03，含 build_map_from_df）
│   │   ├── sizing.py          # 分數凱利部位（Phase 7 step-04）
│   │   ├── meta_label.py      # meta-labeling 二級過濾（Phase 7 step-05）
│   │   ├── event_risk.py      # 事件風險閘（Phase 7 step-06，只煞車不猜方向）
│   │   ├── validation.py      # 防過擬合框架（Phase 7 step-07：walk-forward/purged k-fold/層閘）
│   │   ├── layer_validation.py # 層驗證 harness（baseline-vs-candidate 樣本外比較各層加分）
│   │   ├── strategy_generator.py # LLM 提案策略參數（Phase 8 step-02）
│   │   ├── evolution.py       # 知識庫候選 OOS 驗證管線（Phase 8 step-04）
│   │   ├── automation.py / automation_config.py # 模式 B 自動部署 + 規則（redesign P4）
│   │   ├── opportunity_scan.py # 常駐探勘機會掃描（Phase 10 step-02）
│   │   ├── collector.py       # 爬蟲蒐集員（RSS，Phase 10 step-04，預設關）
│   │   ├── political.py       # Discord 政治員（煞車，Phase 10 step-05，bridge 預設關）
│   │   ├── fred_client.py / macro_data.py / macro_features.py # FRED 總經資料地基（Phase 11）
│   │   ├── orderflow_proxy.py # 籌碼面 proxy 特徵（Phase 11）
│   │   ├── discovery.py       # 探勘橋：raw find → LLM 產候選（Phase 12 step-02，預設關）
│   │   └── auto_validate.py   # 候選自動批次 OOS 驗證（Phase 12 step-03，判準零修改，預設關）
│   ├── strategies/        # 交易策略模組（每個策略一個檔案）
│   │   ├── base.py        # 策略基底類別
│   │   ├── ma_crossover.py    # 均線交叉
│   │   ├── rsi.py             # RSI
│   │   ├── macd.py            # MACD
│   │   ├── bollinger.py       # 布林通道
│   │   ├── donchian.py        # 唐奇安通道（突破）
│   │   ├── momentum.py        # 動量
│   │   ├── stochastic.py      # KD 隨機指標
│   │   ├── williams_r.py      # 威廉指標 %R
│   │   ├── adx_trend.py       # ADX 趨勢
│   │   └── lookback.py        # 依策略參數推算回看天數（回測=實盤共用，Phase 6 step-01）
│   └── bots/
│       └── bot_manager.py # 管理所有 Bot 的啟停/執行/排程（Phase 6：每輪用 bot_id 重查最新設定）
├── explorations/         # 思考助手「探討/檢討」檔案記憶（INDEX.md 路標 + 每筆一檔，進 git）
├── frontend/              # React 前端（Vite；左側 sidebar + react-router 多頁，Phase 9）
│   ├── .env.example          # 前端環境變數範本（VITE_API_URL）
│   └── src/
│       ├── App.jsx            # 路由編排層（state + handler + <Outlet context> 分配給各頁）
│       ├── theme.js           # MUI 深藍主題 + NEON 色票（redesign P3）
│       ├── constants.js       # 共用常數（策略清單 STRATEGIES）
│       ├── api.js             # 前端 API 呼叫（讀 VITE_API_URL）
│       ├── BotAvatar.jsx      # Bot 頭像元件（深藍發光徽章）
│       ├── LightweightChart.jsx  # 原生 K 線圖（lightweight-charts，取代舊 TradingView iframe，redesign P1）
│       ├── pages/             # 各路由頁（Dashboard/Trades/BacktestRuns/Presets/Explorations/
│       │                      #   Decisions/Evolution/Library/AiExplore/Charts/Fundamentals/BacktestTools/
│       │                      #   Company/Opportunities→戰情頁內/Factors/Collector/Political/Promotion，Phase 10）
│       ├── components/        # 畫面區塊元件
│       │   ├── SidebarLayout  # 左側導覽外殼（Phase 9 step-01）
│       │   ├── AssistantDrawer  # 思考助手全站抽屜（Phase 9 step-08，右下浮動鈕）
│       │   ├── Header / AccountCard / PositionsCard / BotList / Stat / ConfirmDialog
│       │   ├── BacktestPanel / TradesTable / EditBotDialog / KnowledgeCard
│       │   ├── RecommendationsPanel / AutomationPanel  # AI 海選推薦 / 模式 B 自動化規則（redesign P2/P4）
│       │   ├── ChartGrid / LiveQuote / EquitySparkline / BacktestResultCard
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

## 檔案放置規範（新增檔案放哪 — Claude 與人都遵守）

> docs/ 已依用途分四夾（2026-06 重整，零刪除）。**新增任何檔前先想清楚歸哪夾**，
> 別再丟回 docs/ 根或亂塞，否則很快又積成一坨找不到。命名沿用既有風格（kebab-case、Phase 用 `phase-N-主題/`）。

### 文件（docs/）

| 要新增的東西 | 放這裡 | 例 |
|--------------|--------|-----|
| 某 Phase 的開工藍圖 / step 契約 | `docs/history/phase-N-主題/`（含 in-progress；做完不用搬） | `docs/history/phase-12-strategy-discovery/README.md` |
| 「AI 終端機改版」子軌文件 | `docs/history/redesign/` | `docs/history/redesign/phase-5-xxx.md` |
| 操作教學 / runbook / 安裝 / 使用說明 / 上線檢查表 | `docs/guides/` | `docs/guides/how-to-deploy.md` |
| 概念 / 規格 / 路線圖 / 工作流圖 / 個別策略筆記 | `docs/reference/`（策略筆記進 `reference/strategies/`） | `docs/reference/strategies/macd.md` |
| 前端 UX 稽核 / 工作流 | `docs/ux/` | `docs/ux/ux-audit-2026-12.md` |
| 反 slop 開工合約、進行中 backlog | **docs/ 根**（只有這兩類留根，最常讀） | — |

- **新增文件後**：更新 [`docs/README.md`](docs/README.md) 索引表那一列（它是文件地圖，漏了就等於沒人找得到）。
- **連結用相對路徑**並確認解析得到；搬移既有檔一律 `git mv`（保歷史血緣），改完 grep 驗證無殘斷連結。

### 程式碼（backend/ · frontend/ · tests/ · scripts/）

| 要新增的東西 | 放這裡 |
|--------------|--------|
| 交易策略模組（一策略一檔，鬆耦合） | `backend/strategies/<name>.py`（+ 註冊 + 前端 `constants.js` 清單 + 測試） |
| 業務邏輯 / 服務 | `backend/services/<name>.py` |
| API 路由（依功能拆檔） | `backend/routers/<name>.py`，並在 `backend/main.py` 掛上 router |
| SQLAlchemy 資料模型 | `backend/models/<name>.py`（改欄位走 Alembic，**勿手動 ALTER**） |
| 前端頁面 / 區塊元件 / Hook / 純函式工具 | `frontend/src/{pages,components,hooks,utils}/`（元件測試同層 `*.test.jsx`） |
| 測試 | `tests/test_<主題>.py`（**扁平結構**，勿建子資料夾） |
| 維運 / CLI 腳本 | `scripts/` |

- **root 維持乾淨**：只放慣例頂層檔（`CLAUDE.md`/`README.md`/`CHANGELOG.md`/`*.bat`/設定檔）。
  `.bat` 用 `%~dp0` 錨定 root，**不要搬進子資料夾**（雙擊路徑會壞）。新文件一律進 `docs/`、新腳本進 `scripts/`。

## 開發階段

| 階段 | 內容 | 狀態 |
|------|------|------|
| Phase 1 | 核心基礎：資料串接 + 策略 Bot + 通知 | ✅ 完成 |
| Phase 2 | Web UI + 回測引擎 | ✅ 完成（前端 + TradingView 看板 + 回測引擎） |
| Phase 3 | 多 Bot 管理 + 更多策略 | ✅ 完成（Bot CRUD/啟停、績效指標、8 種策略、分頁式 UI、CI） |
| Phase 4 | 自動交易監聽系統 + 實盤切換準備 | ✅ 完成（風控欄位 + 止盈/止損/追蹤止損出場、追蹤止損最高價持久化、開市判斷、實盤雙閘安全閥、Alembic 遷移、監聽狀態可視化、Discord 通知） |
| Phase 5 | 策略工作台 + 本機 LLM 思考助手 + 期望值最優 | 🚧 進行中（核心已落地：策略工作台 UI、Preset CRUD、EV 回測歷史、本機 Ollama 助手、explorations 檔案記憶；roadmap：[`docs/reference/roadmap-strategy-workbench.md`](docs/reference/roadmap-strategy-workbench.md)） |
| Phase 6 | 可信度地基（讓回測 EV ≈ 實盤 EV：成本/隔日成交/樣本外 OOS/統一資料路徑/組合風控/決策審計） | ✅ 完成（step-01~10，藍圖 [`docs/history/phase-6/`](docs/history/phase-6/README.md)） |
| Phase 7 | 自適應市場狀態（狀態辨識→選策略 + 分數凱利 + meta-labeling + 防過擬合驗證） | ✅ 完成（step-01~07：特徵/狀態分類/選策略/凱利/meta-labeling/事件風險閘/驗證框架，藍圖 [`docs/history/phase-7-adaptive-regime/`](docs/history/phase-7-adaptive-regime/README.md)；機制就位，各層 OOS 加分待 step-07 驗證後決定去留） |
| Phase 8 | 策略知識庫 + 組合進化（蒐集多策略→整合組合→驗證→人在迴路策展） | ✅ 完成（step-01~06：知識庫模型/LLM 提案/組合引擎/OOS 驗證管線/排行+使用時機/人在迴路審核，藍圖 [`docs/history/phase-8-strategy-evolution/`](docs/history/phase-8-strategy-evolution/README.md)） |
| Phase 9 | 專業前端工作站（左側導覽 + 多頁面：交易/回測/方案/探討/決策/進化/知識庫） | ✅ 完成（step-01~08：sidebar+路由外殼/交易/回測歷史/方案/探討（+後端讀取端點）/決策/進化+知識庫/助手抽屜，藍圖 [`docs/history/phase-9-frontend-workstation/`](docs/history/phase-9-frontend-workstation/README.md)） |
| Phase 10 | AI 交易公司（編排層 + 戰情頁：市場蒐集員/政治員/常駐探勘/因子報表/董事會核准 Bot 上真錢） | ✅ 完成（step-01~07：戰情頁/常駐機會清單/因子表/爬蟲蒐集員/Discord 政治員/董事會核准頁/開機常駐化，藍圖 [`docs/history/phase-10-ai-company/`](docs/history/phase-10-ai-company/README.md)；step-05 政治員為「煞車」且 bridge 預設關，連真 Discord 需先有同步川普貼文的鏡像頻道） |
| Phase 11 | 總經 + 籌碼資料地基（FRED 序列入庫 + macro 特徵 + orderflow proxy，餵 Phase 7 狀態機） | ✅ 完成（藍圖 [`docs/history/phase-11-macro-data/`](docs/history/phase-11-macro-data/README.md)；macro 層真資料 OOS 驗證無加分，2026-06-11 誠實砍除——資料地基留著、層不上線） |
| Phase 12 | 策略自動探勘入庫管線（collector 收料 → LLM 探勘橋產候選 → 自動 OOS 驗證 → 漏斗報表 + 人在迴路晉升） | 🔶 step-01~04 已實作（collector 通電 guide/探勘橋 `discovery.py`/自動驗證 `auto_validate.py`/戰情漏斗卡 + 心跳待審行，藍圖 [`docs/history/phase-12-strategy-discovery/`](docs/history/phase-12-strategy-discovery/README.md)）；step-05 兩週觀察待常駐機器開跑（模板 [`review-e2e.md`](docs/history/phase-12-strategy-discovery/review-e2e.md)），跑滿後留/降級/砍三選一。預設全關（`DISCOVERY_ENABLED`/`AUTO_VALIDATE_ENABLED`=false）；晉升 curated 仍只能由人觸發 |

> **改版子軌**：[`docs/history/redesign/`](docs/history/redesign/README.md) 的 Phase 1–4 是 Phase 2~4 的「AI 終端機改版」子軌（圖表/AI 推薦/深藍主題/自動化），與上表主線編號不同、勿混淆。
> **跑真錢前必讀**：[`docs/reference/human-vs-ai-operation.md`](docs/reference/human-vs-ai-operation.md)（人機操作落差 + 分階段上線）。

## ⚠️ AI 自動 coding 前必讀

任何 AI（或人）拿 `docs/history/phase-*/` 藍圖**自己 coding** 前，**必讀並遵守**
[`docs/ai-implementation-guardrails.md`](docs/ai-implementation-guardrails.md)——防止「偏離原目標」與「產生 vibe slop」的合約：
開工前讀原目標錨點 + 對應 step、coding 中守反 slop 規則、收工前對完成定義 DoD。一次一步、永遠對齊原目標。

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
# 資料庫（雲端 Neon PG；留空/註解掉＝退回本機 SQLite）
# 連線字串從 Neon Dashboard → Connect 複製；新電腦設置見 docs/guides/setup-postgres-sync.md
DATABASE_URL=postgresql://neondb_owner:<密碼>@ep-xxxx.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require

ALPACA_API_KEY=你的_API_Key
ALPACA_SECRET_KEY=你的_Secret_Key
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Paper Trading
ALLOW_LIVE_TRADING=false  # 實盤安全閥：true 才允許真錢下單（預設關）
LINE_CHANNEL_ACCESS_TOKEN=你的_LINE_Token
LINE_CHANNEL_SECRET=你的_LINE_Secret

# 思考助手用的 LLM（OpenAI 相容介面；預設本機 Ollama，免費、離線）
LLM_BASE_URL=http://localhost:11434/v1   # Ollama；換 Gemini/Groq 等只改這三行
LLM_API_KEY=ollama                        # 本機 Ollama 隨意填；雲端供應商填真金鑰
LLM_MODEL=llama3.1                        # 想用別的本機模型改這裡
LLM_ALLOW_CLOUD=false                     # 外送閘：非本機 LLM 須設 true 才放行（防策略資料外洩）
EXPLORATIONS_DIR=                         # 探討檔案記憶資料夾（留空＝專案根 explorations/）
```

> **LLM 助手定位**：只做策略「設計/微調/事後檢討」與讀回測歷史，**無**下單/啟停 Bot/
> 改實盤安全閥/跑 shell 的能力。預設本機 Ollama（須先 `ollama serve` + `ollama pull llama3.1`），
> 沒裝/連不上時 API 回優雅 400 提示，不會卡住其他功能。

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

> 下面是開工必記的精簡鐵則。**完整踩坑史料 + commit 溯源**（每個坑當初怎麼炸、怎麼修）見
> [`docs/reference/dev-pitfalls-log.md`](docs/reference/dev-pitfalls-log.md)。

- **「回測 = 實盤」鐵則（Phase 6 地基，最容易被破壞）**：回測看到的 EV 必須是實盤拿得到的
  EV 的誠實估計。三件事必須一致、不可分岔：
  - **同資料源 + 同回看長度**：實盤與回測都走 `market_data.get_bars(..., source=settings.DATA_SOURCE)`
    + `strategies/lookback.required_lookback_days(...)`；**不要**在實盤端寫死 `alpaca_client.get_bars(days=60)`。
  - **含成本 + 隔日成交**：回測走 `_simulate_from_signals`（手續費/滑價 + 訊號於次根開盤成交、
    最後一根不成交）；**不要**用當根收盤零成本「偷看未來」報虛高 EV。
  - **挑冠軍 / 設門檻一律看樣本外（OOS）**：`optimizer` 以 `oos_expected_value` 排名、
    `automation`/`screener` 門檻比對 OOS；**不要**在整段歷史挑樣本內最佳（過擬合）。
  - 自動下單系統的每筆決策都應落 `DecisionLog`（含沒成交的觀望/跳過），方便事後查驗。
- **Alpaca 套件**：用 `alpaca-py`，不是舊的 `alpaca-trade-api`。
  - 交易：`from alpaca.trading.client import TradingClient`
  - 資料：`from alpaca.data.historical import StockHistoricalDataClient`
- **Windows 主控台編碼**：預設 cp950 印 emoji/中文會崩潰。
  已在 `backend/config.py` 開頭用 `sys.stdout.reconfigure(encoding="utf-8")` 修正；
  獨立腳本（如 test_connection.py）需自行加同樣修正。
- **前端顏色一律吃主題、別寫死 hex（深藍主題的隱形陷阱）**：全站走 `theme.js` 的深藍主題
  （`palette` 與 `NEON` 色票）。元件顏色要用 `color="text.primary"`/`"text.secondary"` 或
  `theme`/`NEON` 變數，**不要寫死淺色 hex**——換深底後寫死的深色文字（如 `#1a2238`）會貼在
  深藍面板上隱形。`Stat.jsx` 就踩過這坑（已改吃主題色）。新元件比照既有深底元件取色。
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
  - DB 連線讀 `config.py` 的 `DATABASE_URL`（可由 `.env` 覆寫）。**現已指向 Neon 雲端
    PostgreSQL**（`.env` 設 `DATABASE_URL=postgresql://...`，程式零改；沒填則退回本機
    SQLite）。設定/換機 runbook：`docs/guides/setup-postgres-sync.md`。

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

要新增 Skill（放在 `.claude/skills/`）時，請先讀 [`docs/guides/skill-guidelines.md`](docs/guides/skill-guidelines.md)：
避坑指南、漸進式揭露、記憶能力、按需觸發的危險操作 Hook 四大原則。
