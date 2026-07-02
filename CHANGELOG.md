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

### 新增 (Added) — Phase 16 M5：進場趨勢過濾器框架（2026-07-02）

- **新 `backend/services/trend_filters.py`**：`TrendFilter` 基底（`allow_entry(df, i)`）+
  六個過濾器註冊表——只否決 BUY、不產生訊號、不碰 SELL/HOLD（只煞車不猜方向）：
  - `ema_stack`：EMA20>50>200 多頭排列（pandas ewm，因果不偷看）
  - `vwap_side`：價在 session VWAP 上（日內專用；日 K 放行 + 註明不適用）
  - `adx_min`：ADX ≥ 門檻（復用 `indicators.adx_components`；NaN 保守否決）
  - `hh_hl`：近 N 根「最後兩個 swing 高/低點都走高」的上升結構（復用 M4 swing 偵測）
  - `bos`：收盤突破最近已確認 swing high（break of structure）
  - `regime`：Phase 7 `classify_regime` == trending 才進
- **引擎掛點**：`_run_on_df(+entry_filters)` 在訊號產生後、成交模擬前過濾；
  被否決記 HOLD + 否決理由。`None`（預設）行為與現況 bit-for-bit 相同。
- **M5 只建框架**：哪個 filter 上線由 M6 研究矩陣 `is_layer_worth_it` OOS 判定，
  加不了分就砍（比照 Phase 11 macro 層前例）。
- 測試 `tests/test_trend_filters.py` 11 個；全套 668 passed。

### 新增 (Added) — Phase 16 M4：可插拔出場政策 ExitPolicy（2026-07-02）

- **新 `backend/services/exit_policies.py`**：`ExitPlan`（stop/target/trailing + meta 依據）+
  `ExitPolicy` 基底（`on_entry` 進場算計畫、`on_bar` 逐 bar 更新＝M10 動態出場掛點）+ 註冊表：
  - `fixed_pct`：包既有 % 止盈損（與舊參數路徑**逐欄全等**，回歸基準）
  - `atr`：stop = entry − k×ATR(n)，波動大放遠、波動小收緊；資料不足誠實回無停損
  - `swing`：stop = 近 N 根已確認 swing low − buffer（防未來：右邊需 right 根確認）
  - `vwap`：日內跌破 session VWAP 出場（動態逐 bar 更新；日 K 誠實拋錯）
  - R:R 內建：`target = entry + rr_multiple ×(entry − stop)`（M6 掃 1.5~4R）
- **回測引擎統一走政策路徑**：`_simulate_from_signals(+exit_policy)`，舊 % 參數內部轉接
  FixedPctPolicy（兩者互斥、同給拋錯）；每筆有 stop 的交易記 `r_multiple`（損益/初始風險 R），
  彙總 `avg_r_multiple`；optimizer walk-forward 聚合回填 `oos_avg_r_multiple`（M3 留的欄）。
  `run_backtest(+exit_policy_key/exit_policy_params)`。
- **swing/ATR 偵測進 `strategies/indicators.py`**（`atr`/`swing_lows`/`swing_highs`，
  M5 BOS/HH-HL 共用；嚴格低於左右鄰居才算 swing，水平盤不誤判）。
- **實盤側同一份政策（回測=實盤鐵則）**：
  - Bot 加 `exit_policy_key`/`exit_policy_params`/`exit_plan`（遷移 `03274cbd08de`；
    exit_plan 存進場當下算好的計畫，重啟不會用「現在的指標」重算而漂移）。
  - `risk_manager.check_exit_plan`：吃絕對觸價的出場判斷（順序同回測：停損→追蹤→停利）。
  - `protective_orders.protective_order_from_exit_plan`：券商端 GTC stop 價由
    ExitPlan.stop_price 供給（`order_matches_plan` 自癒對帳沿用零改動）。
  - `bot_manager`：進場用「跑訊號同一份 K 線」算 plan 並持久化；持倉輪檢查吃 plan；
    續抱時動態政策 on_bar 更新；平倉/券商端成交/空手清 plan。
  - bots API 收 `exit_policy_key`/`exit_policy_params`（建檔即驗證，錯誤回 400）。
- 測試 `tests/test_exit_policies.py` 16 個（各政策數學/防未來/intrabar 觸發順序/跳空成交/
  r_multiple/與舊路徑全等回歸/check_exit_plan/保護單轉接）；全套 657 passed。

### 新增 (Added) — Phase 16 M3.5：前端顯示 walk-forward OOS 診斷欄位 + timeframe 選單（2026-07-02）

- **回測歷史列表補 M3 欄位**（`backend/routers/presets.py _run_summary`）：
  `oos_expected_value` / `overfit_gap` / `oos_num_round_trips` / `timeframe`
  （舊紀錄沒跑 walk-forward 回 None，前端顯示 "—"）。
- **前端三處補顯示**（Gap > 0.5 紅色警示＝後端排名守門的沉底線；顏色吃 theme/NEON）：
  - `BacktestRunsPage`：EV 榜加「OOS EV / Gap / K線」三欄。
  - `StockArenaPage`：排行榜加「Gap / OOS 回合 / OOS Sharpe」欄；新增 K 線時間框架下拉，
    掃描與**部署 bot 都帶同一個 timeframe**（回測=實盤鐵則）。
  - `AutoBacktestPanel`：新增 timeframe 下拉；排行榜加可排序欄「OOS EV / Gap / OOS 交易」。
- `frontend/src/constants.js` 新增 `TIMEFRAMES` / `DEFAULT_TIMEFRAME`
  （與後端 `services/timeframes.py ALL_TIMEFRAMES` 同一份清單）。
- 元件測試：`AutoBacktestPanel.test.jsx` 新檔 + StockArena / BacktestRuns 各補一測
  （前端 141 passed、後端 641 passed 全綠）。

### 修正 (Fixed) — 測試樁補 timeframe 參數（2026-07-02）

- M2 給 `market_data.get_bars` / `bar_cache.get_bars_cached` / `yfinance_client.get_bars`
  加了 `timeframe` 參數後，4 個測試檔（`test_bar_cache` / `test_batch_fetch` /
  `test_bot_manager` / `test_oos`）的 monkeypatch 假函式簽名沒跟上，收到
  `timeframe` kwarg 直接 TypeError（13 failed）。全部補上 `timeframe="1Day"` 預設參數。

### 新增 (Added) — Phase 16 短線轉型 M1~M3：選主鎖租約制 + 多 timeframe 地基 + optimizer walk-forward（2026-07-02）

> 藍圖與 M4~M12 計畫書：[`docs/history/phase-16-intraday-swing/`](docs/history/phase-16-intraday-swing/README.md)

- **M1 選主鎖修復（修掉唯一真金風險：靜默失鎖 → 雙 leader 重複下單）**：
  - `backend/services/scheduler_lock.py` 重寫為**租約制**（新表 `scheduler_lease` 單列，
    遷移 `2768500820b2`——同時補建 Neon 幽靈 rev 的血緣）：原子 UPDATE 搶租約（TTL 90s、
    DB 時鐘 UTC）、leader 每 30s 續約驗鎖、續約失敗**先立旗擋單再卸排程**、
    follower 每 30s 嘗試接手自動升級（VM 重啟後零人工自動重取鎖）。
  - `alpaca_client` 下單**第三閘** `assert_leader()`：非 leader 一律拒單（與實盤雙閘並列）。
  - `main.py` lifespan 重構：leader 區塊抽成 `_promote_to_leader()`；無論輸贏都掛租約守護 job。
  - `bot_manager.unschedule_outbound_jobs()`：降級時卸下所有對外 job。失鎖行為＝只停新單、
    不自動平倉（持倉靠券商端 GTC 保護單）。測試 `tests/test_scheduler_lock.py` 12 個。
- **M2 多 timeframe 資料地基**（1Min/5Min/15Min/30Min/1Hour/2Hour/4Hour/1Day，
  預設 "1Day" 零改動相容）：
  - 新 `backend/services/timeframes.py` 單一事實來源（年化基數 `periods_per_year`、
    bar↔日曆天換算）。`alpaca_client` / `yfinance_client`（超限誠實拋錯）/ `market_data` /
    `bar_cache`（timeframe 目錄維度；日內「今天」永遠當尾缺口重抓）/ `lookback` /
    `analytics`（Sharpe/Sortino 年化基數修正；日內 calmar/cagr 誠實回 None）/
    `backtest_engine`（日內一律 alpaca 源）全鏈貫穿。
  - `bots.timeframe` 欄位（遷移 `d0d0c19d13b0`）；實盤 `_run_strategy` 用 Bot 自己的
    timeframe 抓資料（回測=實盤鐵則）；`_drop_unclosed_today_bar` 泛化為日內濾未收完 bar。
    測試 `tests/test_timeframes.py` 12 個。
- **M3 Optimizer walk-forward 聚合 OOS + 排行榜擴充**：
  - `run_auto_backtest(+timeframe, +walk_forward=True)`：`_wf_aggregate` 把所有滾動 fold 的
    OOS round trips 串接聚合（EV/勝率/PF/MaxDD 取各 fold 最差/串接報酬算 Sharpe·Sortino），
    OOS 樣本數從單次切分的 1~2 筆拉高到可信程度；資料太短誠實退回單次切分。
  - 新欄位 `overfit_gap =(IS−OOS)/|IS|`、`oos_num_round_trips`（跨折加總）、`oos_folds`、
    `oos_sharpe/oos_sortino/oos_profit_factor/oos_max_drawdown_pct`、`oos_avg_r_multiple`
    （留 M4 回填）。**排名守門**：OOS 交易 < `OPTIMIZER_MIN_OOS_TRIPS`(20) 或
    gap > `OPTIMIZER_MAX_OVERFIT_GAP`(0.5) 直接沉底。
  - `/auto-backtest` API 加 `timeframe`/`walk_forward` 參數、摘要回傳全部新欄位
    （BacktestRun.metrics 為 JSON，零遷移）。測試 `tests/test_optimizer_walkforward.py` 6 個。

### 新增 (Added) — 回測驗證日：風控出場模擬 + 4 支全池分析 CLI（2026-07-02）

- **回測引擎 opt-in 風控出場模擬**（`backend/services/backtest_engine.py`）：
  `stop_loss_pct` / `take_profit_pct` / `trailing_stop_pct` 參數（預設 None＝行為 bit-for-bit 不變）。
  日 K 粒度誠實近似：high/low 觸價、跳空穿停損成交在更差開盤價、追蹤止損 peak 不偷看當根、
  檢查順序同實盤 `risk_manager`（停損→追蹤→停利）；交易紀錄加 `exit_reason`、結果加
  `num_stop_loss/num_take_profit/num_trailing_stop` 觸發統計。補 6 個單元測試。
  ——補上「回測=實盤」原則在出場端的缺口（實盤有風控出場、舊回測只認策略訊號）。
- **4 支全池分析 CLI**（`scripts/`，只讀不寫 DB、不下單）＋總報告
  [`docs/reference/analysis-2026-07-02/`](docs/reference/analysis-2026-07-02/README.md)：
  - `full_backtest_report.py`：38 檔 × 9 策略 × 參數網格、OOS EV 排名、蒙地卡羅壓力測試、
    風控對照組（發現：風控組 29/38 檔回撤變小、但停利 15% 傷報酬；只有 17/38 冠軍贏 Buy&Hold）。
  - `scan_frequency_study.py`：分鐘 K 實測 30~600s 掃頻的風控出場延遲滑價 + API 用量
    （結論：日 K 策略掃頻不影響進場；190 bots 下 **300s 維持不變**，60s 會打滿 Alpaca 限流）。
  - `stock_pool_report.py`：38 檔逐檔 OOS EV / 假突破率 / DecisionLog 訊號活動分層
    （誠實發現：32 檔 OOS 樣本僅 1~2 筆屬統計噪音；已證實核心池僅 AMD/AVGO/INTC/ORCL/BAC/MS 6 檔）。
  - `fund_flow_report.py`：11 產業 ETF 相對強度輪動 + 領漲股 + 隔日發動候選 + 資金流納入策略路線圖。

### 修正 (Fixed) — 回測驗證日系統體檢（2026-07-02）

- `/bots` API 190 個 Bot 逐檔打 Alpaca 持倉 + 逐檔查 TradeLog（2×190 次往返、實測 57 秒）
  → 改批次抓（固定 2 次往返）（`backend/routers/bots.py`）。
- `layer_validation` 兩個包裝策略（MetaFiltered/AdaptiveMapped）缺 `produce_signals`
  （回測引擎統一入口改版後漏改）→ 改繼承 `BaseStrategy` 取得預設實作。
- `script_breakout` 漏接指標疊圖映射（`indicator_overlays.py` 補 builder）；
  向量化覆蓋測試的豁免改「ScriptStrategy 子類」原則性判斷（新增 Script 策略不再漏接）。
- `catchup.py` 開機補跑在 cp950 主控台印 emoji 直接炸掉整個補跑 job → 編碼失敗退回 ASCII。
- `notifier.notify()` 的主控台回音 print 在 cp950 下炸掉，會**連後面的 Discord 推播一起死**
  （心跳日報實測沒發出去）→ print 包 try/except，log 失敗不擋推播本體。
- （已知未修）排程選主鎖「靜默失鎖」可能導致雙 leader：VM 失鎖後仍自以為 leader 跑排程。
  處置與根治方案見總報告第 0 節；需重啟 VM 服務 + 後續加「定期驗鎖」。

### 新增 (Added) — 採納 QuantDinger 兩項能力：ScriptStrategy 引擎 + Agent Gateway/MCP

> 分析外部專案 [QuantDinger](https://github.com/brokermr810/QuantDinger) 後採納兩項架構能力，
> 簡單版優先。守住既有「回測=實盤同路徑」與實盤雙閘鐵則。

- **事件驅動 ScriptStrategy 引擎**（`backend/strategies/base.py` 新增 `ScriptStrategy` +
  `backend/strategies/context.py` 新增 `BacktestContext`）：用 `on_bar(ctx, bar)` +
  `ctx.buy()/sell()/close()` 寫有狀態的進出場邏輯（讀得到 `ctx.in_position`/`bars_held`/`history`）。
  - 統一入口 `produce_signals(df)` / `evaluate_last(df)`：向量化策略走預設實作（行為逐位元組不變）、
    事件式策略覆寫成 on_bar 驅動，但**壓出的訊號仍走同一個 `_simulate_from_signals` 成交核心**
    （次根開盤 + 含成本），零分岔。`backtest_engine._run_on_df` 與 `bot_manager._run_strategy` 改吃統一入口。
  - 範例策略 `script_breakout`（突破進場 + 有狀態續抱）：已註冊 + 前端 `constants.js` + 參數 schema。
  - 等價性測試證明「同一規則的向量化 vs 事件式」回測結果（EV/報酬/交易/資金曲線）完全一致。
- **Agent Gateway**（`backend/routers/agent.py`，`/api/agent/v1/*`）：讓 Claude/Cursor 等外部 AI
  透過 bearer token 驅動我們的回測/策略/帳戶/機會/知識庫查詢，並可下「預設 paper」的單。
  - 三道安全閘：① `AGENT_API_TOKEN`（未設＝整組回 503）；② 唯讀為主；③ 下單預設 paper，
    碰真錢須 `AGENT_LIVE_TRADING_ENABLED=true` 第三道閘 + 既有 Alpaca 實盤雙閘把關。
  - 每筆呼叫落 `agent_audits` append-only 審計表（`backend/models/agent_audit.py` + Alembic 遷移 `f7a8b9c0d1e2`）。
- **自家 MCP server**（`mcp_server/server.py` + `README.md`）：stdio MCP 薄包 Agent Gateway，
  工具一對一映射（list_strategies / run_backtest / get_account / list_bots / submit_order 等）。
  `requirements.txt` 加 `mcp>=1.0`（僅跑 MCP 時需要，後端本體不依賴）。
- **設定**：`config.py` + `.env.example` 加 `AGENT_API_TOKEN`、`AGENT_LIVE_TRADING_ENABLED`（預設關）。
- **測試**：`tests/test_agent_gateway.py`（503/401/200 + 審計 + 實盤下單 403）、
  `tests/test_backtest.py` 等價性測試、`tests/test_strategies.py` ScriptStrategy 註冊測試。

### 新增 (Added) — AI 交易日誌分析 + 策略進化反饋迴圈

- **`GET /bots/daily-digest`**：每日交易摘要端點，按 Bot 分組顯示 P&L、exit_kind 分佈、thesis_breach 清單，快速查「昨天到底發生什麼」
- **`POST /review/daily`**：手動觸發 AI 每日交易事後檢討，讀 DecisionLog + TradeLog → LLM 分析虧損模式 → 寫 `explorations/review-YYYY-MM-DD.md` → 推播摘要
- **`GET /review/daily`**：確認指定日期 review 檔案是否存在
- **`backend/services/trade_review.py`**：AI 每日交易分析服務（自動在 UTC 20:00 觸發，LLM 不可用時仍回傳統計）
- **`backend/services/strategy_feedback.py`**：策略進化反饋迴圈——Bot 被汰弱/降級後 LLM 自動分析失效原因、提案新參數候選，寫入 StrategyKnowledge（status=candidate, origin=paper_feedback）
- **`StrategyKnowledge` 新增三欄位**（Alembic 遷移 c5040cf68986）：`origin`（來源：manual/paper_feedback/discovery）、`parent_id`（前版本血緣）、`evolution_note`（AI 分析文字）
- **前端 KnowledgeCard**：`paper_feedback` 候選顯示「從實跑學習」Chip + AI 分析展開
- **前端 EvolutionPage**：新增「來源」篩選 toggle（全部/從實跑學習/人工建立/探勘橋）
- **汰弱/降級後自動觸發反饋**：`bot_review._cull_bot` 和 `tracking._demote_bot` 停 Bot 後自動呼叫 `generate_candidate_from_paper`（LLM 不可用優雅跳過）
- **APScheduler 排程**：`schedule_trade_review()`，每日 UTC 20:00 自動跑 AI 檢討
- **catchup.py**：開機補跑管線加入 `trade_review`（美股收盤後才排）



### 接下來要做（我跟你，下個 session 接手）

> 本批程式已落地（全套件 547 passed / 0 failed），但**有幾件要人觸發 / 要拍板的事還沒做**：

- **全庫籃子重驗（已對 Neon 執行，2026-06-22）**：`scripts/revalidate_basket.py` dry-run→`--apply` 跑完。
  結果：原 7 筆 curated 先**去重 2 筆**（#21≡#17 bollinger、#33≡#16 momentum，key+params 完全相同）→
  剩 5 筆全部**通過**新籃子 OOS（池化 EV 全正：#17 bollinger 118.66、#11 ma_crossover 85.58、
  #19 adx_trend 19.86、#16 momentum 2.62、#29 stochastic 1.49），但機制性 `curated→validated`
  （curated 是人晉升專屬狀態、重驗一律退回 validated，待人去 LibraryPage 逐筆重晉升）。Neon 終態：
  validated 5 / rejected 26 / curated 0。零 reject、零失敗。
- **兩個預設已拍板（2026-06-22）**：① 自動部署觸發狀態 → **`validated`**（跳過 `validated→curated`
  人工閘，驗過即自動建 paper bot；只建 paper、不碰真錢，安全）。config 預設仍留 `curated`（不影響
  VM 等其他機器姿態），由**本機 `.env` 覆寫** `AUTO_DEPLOY_FROM_STATUS=validated`。② 驗證窗 → **10 年**
  （`AUTO_VALIDATE_DAYS=3650` 維持）。新增治理機制見上方「bot 汰弱審查員（Phase 13）」。
- **Neon schema 遷移（已手動套 + 修幽靈 rev，2026-06-22）**：`deployed_at` 遷移 `b9c0d1e2f3a4` 已套 Neon
  （current=head）。★踩到坑：Neon `alembic_version` 原卡在幽靈 rev `7d4a3f725a53`（本機/VM/所有遠端分支
  全查無、source 從沒進 git——當初某機直接對 Neon 套了一個建 `validation_symbols` 表的遷移卻沒 commit）。
  修法：`alembic stamp a8f1c2d3e4b5 --purge`（清孤兒戳記→真實父節點）→ `upgrade head`（套 deployed_at）。
  孤兒 `validation_symbols` 表（68 列手挑種子）**暫留未刪**（要復活那「DB 版驗證 universe」功能再決定）。
  CICD 後續 merge 時 `alembic upgrade head` 會是 no-op（已是 head），不再撞幽靈 rev。
- **啟用新排程（要才開）**：所有新功能**預設全關**。要全自動管線上線需在 `.env`/VM 設
  `AUTO_DEPLOY_KNOWLEDGE_ENABLED=true`（+ 視需要 `DISCOVERY_ENABLED`/`AUTO_VALIDATE_ENABLED`=true）。
  上線前讀 `docs/reference/human-vs-ai-operation.md`（分階段上線）。
- **前端（選配二期）**：`PresetsPage` 加「送進驗證」鈕（呼叫 `/presets/{id}/to-knowledge`）、
  `LibraryPage` curated 卡加「部署成 Bot」鈕（呼叫 `/knowledge/{kid}/deploy`）。本批只做後端。
- **兩週 paper 觀察 → 自動送審 + 報告（缺最後一段自動化）**：paper bot 跑出實績後，
  `promotion.propose_promotion` 達標證據 + `GET /backtest-runs/{id}/report` 報告都已存在，但**沒有排程
  自動把達標 bot 提議送審**。下一步可加「auto_propose」排程串起最後一哩。

### 修正

- **`POST /discovery/validate-batch` 改為非同步（202）**：原同步呼叫跑 38 籃子 walk-forward 回測需數分鐘以上，HTTP 請求必逾時。改用 FastAPI `BackgroundTasks` 立刻回 202；前端 CompanyPage「驗證」鈕按下後改為每 10 秒輪詢 `/company/overview`，偵測到 `candidate/validated/rejected` 數字變動時自動解鎖，最多等 10 分鐘（`backend/routers/discovery.py` + `frontend/src/pages/CompanyPage.jsx`）。
- **`test_discovery_api` 不再連 Neon + 補修非同步後遺漏的斷言（根治 flaky）**：`tests/conftest.py` 在 import `backend.config` 之前把 `DATABASE_URL` 指到暫存 SQLite，讓全域 engine（lifespan 的 `init_db`/resume/排程、`validate-batch` 背景任務 `run_auto_validate(None)` 自建的 `SessionLocal`——這些都不經 `get_db` 覆寫）改走本機檔案，整個測試程序與 Neon 脫鉤（全套件受惠，逐測試仍各自用 `tmp_path` SQLite 隔離）。同時把上一筆 validate-batch 改 202 時漏改的測試斷言（仍期待 `200 + "validated"`）更新為 `202 + status=="started"`。
- **實盤進場訊號改吃「已收盤」日K，根治盤中 whipsaw + 對齊回測隔日成交語意**：`alpaca_client.get_bars` 只給 `start` 沒給 `end`，盤中每次抓資料，最後一根「今天」的日K都是還在跳動、尚未收盤的未完成棒；但 `ma_crossover`/`macd`/`rsi` 等策略設計時的邏輯語意是「用已收盤價判斷金叉死叉/超買賣」。同一天內盤中價格晃動讓指標跟著晃，可能反覆翻轉買賣訊號，且訊號一出就立即市價成交，跟回測「隔日開盤成交」的 EV 假設完全對不上——這是實盤持續虧損、回測歷史績效對實盤沒有參考力的主因。新增 `bot_manager._drop_unclosed_today_bar`：market_is_open=True 時濾掉「今天」那根未收盤日K，只留已收盤資料算訊號；訊號因此在盤中固定不變，靠既有空手/持倉狀態機自然讓成交發生在開盤後第一輪，貼近回測「隔日開盤成交」語意，不需另外疊加排程機制（`_run_strategy`/`_run_adaptive_strategy` 簽章加收 `market_is_open`，`run_bot_once` 查一次 `is_market_open()` 往下傳）。
- **購買力守門套用現金緩衝比例 + 加鎖防多 Bot 並發搶單**：`_available_buying_power()` 原直接回 Alpaca 帳戶原始 `buying_power`，沒套用既有 `PORTFOLIO_CASH_RESERVE_RATIO`（`capital.py::plan_capital` 已實作這個緩衝概念，但只用在模式 B 批次部署規劃、沒接到單一 Bot 的即時買進路徑），現改為回傳扣除緩衝比例後的可用額度。另外 APScheduler 用執行緒池同時跑多個 Bot，`_handle_flat` 買進前「查購買力→送單」原本沒有互斥保護，多個 Bot 幾乎同時觸發買進時可能各自查到「購買力足夠」而一起送單；加一個模組層級 `threading.Lock()` 包住這段臨界區，避免本機並發搶單導致總曝險超過預期。

### 變更

- **側邊欄改為依操作流程的 5 階段分組導覽（可折疊收納）**：原本一條扁平 20 項導覽清單（`SidebarLayout.jsx` 的 `NAV_ITEMS`）順序混亂、核心頁被 Phase 10~14 的戰情／實驗頁夾在中間，整理成依「操作流程」由上而下的 5 個階段——① 監控看盤 → ② 找題材 → ③ 研究‧驗證 → ④ 策展‧演進 → ⑤ 部署。每組標題可點展開/收合，次要的「④ 策展‧演進」「⑤ 部署」**預設收合**讓畫面更短；展開狀態記進 `localStorage`（`albee-nav-open`，照 colorMode 範式），直接走訪收合階段內的頁會自動展開該組、不會把目前頁的導覽藏起來。**純前端呈現層改動：路由、頁面、Outlet context 全部不動，20 頁一頁不刪、皆可達**（`frontend/src/components/SidebarLayout.jsx` + 同層測試）。
- **移除 LINE 通知**：LINE Notify 2025 停服後遺留的 Messaging API 推播已全數移除（`notifier.py` / `config.py` / `requirements.txt` 砍 `line-bot-sdk`）；通知管道統一走 Discord Webhook（`DISCORD_WEBHOOK_URL`）。
- **Discord Webhook 429 重試**：`_send_discord` 遇到 rate limit 時依 `retry_after` 等完再重試，最多 3 次，不再印 ⚠️ 警告。
- **政治專討員看門狗修正**：沒設 `POLITICAL_DISCORD_TOKEN` 或未裝 `discord.py` 時改以 `sys.exit(2)` 退出；`.bat` 看門狗偵測到 exit code 2 即停止（不再無窮重啟）。
- **安裝 `discord.py==2.7.1`**：`requirements.txt` 已記載但 venv 未裝，現已補裝，`political_watcher` 可正常啟動。

### 新增

- **結構化交易日誌（買入假設 → 賣出失效回填）**：把每筆買賣的決策脈絡補到可回溯整個假設生命週期，讓週報/月報自我檢討真的有料可讀（延續 Phase 15「決策 Log 加深」）。
  - **`DecisionLog` 加 8 欄**（Alembic `26c1a3a4aef1`，全 nullable 向後相容，既有 ~30 處寫入點不傳也不壞）：`strategy`（冗存策略代號，自適應記實際挑中的）、`total_amount`（成交總額）、`target_price`/`stop_price`（買進依風控門檻算出的停利/停損價）、`market_snapshot`（均線 5/20/60 排列+位置、量能倍數）、`position_after`（交易後庫存 best-effort）、`exit_kind`（把粗粒度 `sold` 細分成止損/停利/追蹤/策略反轉/券商）、`thesis_breach`（賣出回填「哪個買入假設失效」）。
  - **新 `services/decision_context.py`（純函式，不碰 DB）**：`compute_market_snapshot`（收盤均線/均量**複用圖表同公式**）、`classify_exit_kind`（從 reason 判出場類型，處理「追蹤止損」含「止損」的判斷順序與券商端優先）、`build_thesis_breach`（撈最近一筆買進的 target/stop 跟出場價對照，產「跌破預設停損 $X（進場 $Y，−Z%）；當初預期漲抵 $T 未達；持有 N 天」）。
  - **`bot_manager` 全分支接線**：`_run_strategy`/`_run_adaptive` 的 ctx 多帶 `market_snapshot`+`strategy`；買進算 target/stop/total/position_after；賣出三路（風控/策略/券商回填）算 `exit_kind` + 撈最近買進回填 `thesis_breach`。`get_bot_decisions`/`get_recent_decisions` API 補新鍵。
  - **閉環到「讀教訓」**：`chat._format_decision_history` 把 `exit_kind`/停利停損/行情/`thesis_breach` 一併餵 LLM，覆盤教練 system prompt 加引導善用「假設失效」歸納反覆犯的錯。DecisionsPage 表格加 exit chip（吃 NEON 色票）、🎯停利/⛔停損、「行情」tooltip、假設失效小字。
  - 測試：新 `tests/test_decision_context.py`（15 條：快照各分支／出場分類關鍵字順序／假設失效回填）+ 擴 `test_decision_log`（買進記 target/stop/total、止損回填假設失效、策略反轉分類）。
  - **本批未做（範圍外，標記待後續）**：`STRONG_BUY` 信心分級需策略介面輸出信心分數；「預期持有時間」需 Bot 新增參數 + 前端編輯——兩者皆動既有介面，未納本批。
- **每股多策略艦隊落地 + 決策教訓 Log（Phase 15）**：把「每股只有一個 bot」真正變成「每股多策略並存虛擬交易」，並讓每筆決策記下夠深的脈絡供回頭學。
  - **個股擂台一鍵建艦隊**：`StockArenaPage` 加批次「🚀 部署前 N 名為 paper bots」（N 預設 5）+ 可設每單金額／輪詢秒數；去重（先查 `getBots` 比對同 `symbol+strategy` 已存在就跳過），一次把排行榜前段策略各建一個 paper bot 對該股虛擬交易，最佳由汰弱審查員浮現。全程 paper、複用既有 `createBot`/`startBot`，零新後端。
  - **決策 Log 加深（量／股數／指標快照）**：`DecisionLog` 加 `volume`（決策當下那根 K 的成交量）、`qty`（實際下單股數）、`indicators`（該策略當下指標快照，如 `{"rsi":28.1}`）三欄（Alembic `4810c1ec25d9`）。`bot_manager._run_strategy`/`_run_adaptive_strategy` 改回 `(signal, reason, ctx)`，ctx 的指標快照**複用 `indicator_overlays.compute_overlays`** 取各序列末根（零策略改寫）；各決策分支補傳，`get_bot_decisions` API 補三鍵。
  - **讀教訓（LLM 覆盤摘要）**：新端點 `POST /chat/bot-lessons`——撈該 Bot 決策史（含量/股數/指標）請本機 LLM 產一段「為何那些點買/賣/沒動、下次怎麼改」的檢討。複用 chat 既有 LLM client + **雲端外送閘**（`_cloud_blocked`）；只讀資料不下單。DecisionsPage 表格加「量／股數」欄 + 指標 tooltip + 頭部「📖 讀教訓」鈕。
  - **「300 秒太久？」結論**：不是。`AUTO_DEPLOY_KNOWLEDGE_CHECK_INTERVAL=300` 只用於大型自動艦隊防 Alpaca 限流；手動部署本來就 60 秒，且止損是券商端 GTC 單即時成交、不受輪詢延遲影響。改為**部署時可自選輪詢秒數**，全域預設不動。
  - 測試：`tests/test_bot_lessons.py`（新，端點閘 400/404 + stub 成功）+ 擴 `test_decision_log`（寫入量/股數/指標、`_run_strategy` 回 3-tuple ctx）+ `StockArenaPage.test.jsx`（新，批次部署 + 去重）+ `DecisionsPage.test.jsx`（量欄 + 讀教訓）。藍圖 `docs/history/phase-15-fleet-and-lessons/`。
- **公司可操作化 + 漏斗透明 + 個股策略擂台（Phase 14）**：把「探勘管線預設全關、後端能力沒前端入口、淘汰項被藏」三個讓人困惑的缺口補上，全程人工逐步推進（不開任何排程旗標）。
  - **每個 AI 角色一顆「跑一次」鈕**：戰情頁漏斗卡變操作台（收料／探勘／驗證／部署／審查），跑完漏斗數字當場跳動。後端新增 `backend/routers/discovery.py`（`/discovery/run`、`/triage/{id}`、`/validate-batch`、`/auto-deploy`）+ `POST /collector/scan`；`run_discovery_batch`/`run_auto_validate`/`run_auto_deploy_knowledge` 加 `force`（只略過 `*_ENABLED`，**安全閘全留**）。
  - **文字 → 策略橋可見可按**：CollectorPage 每筆加「🔬 試轉策略」（打 `/discovery/triage/{id}`，走共用 `discovery.triage_one`，防幻覺約束不變）、顯示 `triage_note` + 候選連結；`_serialize` 補 `triage_note`/`knowledge_id`。
  - **出處與漏斗透明**：KnowledgeCard 秀 `oos_metrics` 出處（籃子檔數／walk-forward 折數／回看天數）；新頁 `FunnelPage`（`/funnel`）兩條流水線各階段可點開看實際項目 + 淘汰理由；LibraryPage 切換補 candidate/rejected。
  - **驗證嚴謹度拉齊**：`/knowledge/{id}/validate` 加 `use_basket`——人工驗證可用 `AUTO_VALIDATE_SYMBOLS` 完整籃子（與自動路徑同嚴謹度），EvolutionPage 預設籃子、可切單檔。
  - **個股策略擂台**：新頁 `StockArenaPage`（`/stock-arena`）輸入股票 → `/auto-backtest` 跑遍 9 策略排名 → 每列「部署成 paper bot」；LibraryPage curated 卡加「部署到標的」（補孤兒端點 `/knowledge/{id}/deploy`）；BotReviewPage 適配表加「依標的分組」（每股策略競賽排名）。
  - 測試：`tests/test_discovery_api.py`（新）+ 擴充 `test_discovery`/`test_collector`/`test_auto_validate`/`test_auto_deploy_knowledge`（triage_one / force / scan 回統計 / 端點閘）。藍圖 `docs/history/phase-14-company-operability/`。

- **bot 汰弱審查員（Phase 13，新「職位」：考核 paper 艦隊 + 哪股票配哪策略 fit 註冊 + 軟汰弱）**：
  自動部署讓 Bot 數＝好策略數 × 標的數會持續長（5 策略 × 38 檔 = 190 Bot）。沒人管，艦隊很快
  塞滿「驗證時看似可以、實跑卻爛」的 Bot。新增每日排程的審查員補這個治理缺口：
  - 服務 `backend/services/bot_review.py: run_bot_review()`（仿 `auto_validate`/`auto_deploy_knowledge`
    範式）：取 `promotion_status="paper"` 且 `culled_at IS NULL` 的 Bot，逐支用既有
    `performance.compute_bot_stats` 算實跑績效 →（a）**upsert** 進 `strategy_symbol_fits` 註冊表
    （(策略,標的) 唯一，記 good/poor/insufficient 評等）；（b）夠久（≥`BOT_REVIEW_MIN_AGE_DAYS`）
    夠多筆（≥`BOT_REVIEW_MIN_ROUND_TRIPS`）但不及格（勝率/報酬/回撤任一過線）→ **軟汰弱**
    （`is_active=False` + `culled_at`/`cull_reason`，**不刪資料**、不平倉、不撤保護單）。
  - 評等與汰弱判斷抽純函式 `review_bot(stats, age_days, *, 門檻...)`（好寫測試、零魔術數字）。
  - 界線（仿 tracking 降級）：★**只碰 paper Bot**，`proposed_live`/`approved_live`（真錢相關）一律
    不動；冪等（汰過的下輪不再碰）；失敗隔離（單支例外不擋整批）；一輪汰弱數受
    `BOT_REVIEW_MAX_CULL_PER_RUN` 上限保護（門檻設錯不會一次清空艦隊）；落 `DecisionLog`
    （`ACTION_BOT_CULLED`）+ 通知。
  - 新模型 `backend/models/strategy_symbol_fit.py: StrategySymbolFit`；`Bot` 加 `culled_at`/`cull_reason`
    （Alembic `dad6dd04845c`）。排程 `bot_manager.schedule_bot_review`（仿 `schedule_auto_validate`）+
    `main.py` 接線 + `catchup._daily_steps` 納入（排在自動部署之後，先建 Bot 再有得審）。
  - API `backend/routers/bot_review.py`：`GET /bot-review/fits`（適配排行）、`GET /bot-review/culled`
    （汰弱清單）、`POST /bot-review/run`（手動跑一輪）。前端頁 `frontend/src/pages/BotReviewPage.jsx`
    （fit 排行 + 汰弱清單 + 立即審查鈕，左側導覽「汰弱審查員」）。
  - config 新增 `BOT_REVIEW_*`（總開關**預設 false**、時刻 11 點、門檻全可調）。要開才掛排程。

- **知識庫策略 → 自動建 Paper Bot 排程（curated→bot 自動部署，補全自動管線）**：先前「驗證過的好
  策略」要手動逐筆 deploy 才變 Bot。新增每日排程把目標狀態的知識自動部署成 Paper Bot 掛網跑：
  - 共用函式 `backend/services/knowledge_deploy.py: deploy_curated_to_bots(...)`：手動 deploy 端點
    與自動排程**共用同一支**（行為一致、一處維護）。`activate=False`（手動，人再 start）/
    `activate=True`（自動，建好即掛網跑）；兩者一律 `promotion_status="paper"`。
  - 服務 `backend/services/auto_deploy_knowledge.py: run_auto_deploy_knowledge()`（仿
    `auto_validate` 範式）：取 `status==AUTO_DEPLOY_FROM_STATUS`（預設 `curated`）且 `deployed_at`
    為空的知識，至多 `AUTO_DEPLOY_KNOWLEDGE_MAX_PER_RUN` 筆，逐筆建 Paper Bot；**冪等**（建完戳
    `deployed_at`，永不重建）；單筆失敗隔離。
  - 排程：`bot_manager.schedule_auto_deploy_knowledge`（job_id `auto_deploy_knowledge`，與既有
    screener 版 `schedule_auto_deploy` 區隔）+ `main.py` 掛載（排在 auto_validate 之後）+
    `catchup._daily_steps` 納入開機補跑（只建 paper、與盤前盤中無關，補跑安全）。
  - **新欄 `strategy_knowledge.deployed_at`**（Alembic `b9c0d1e2f3a4`，batch add_column；冪等戳記）。
  - config 旗標群（**預設全關 / 保守**）：`AUTO_DEPLOY_KNOWLEDGE_ENABLED=false`、
    `AUTO_DEPLOY_FROM_STATUS=curated`（可切 `validated` 全自動）、`AUTO_DEPLOY_KNOWLEDGE_SYMBOLS`
    （逗號字串 + property）、`_HOUR=9`、`_TRADE_AMOUNT=1000`、`_MAX_PER_RUN=3`。`.env.example` 同步。
  - ★ **安全紅線**：只建 **paper** bot、完全不碰真錢雙閘（`ALPACA_BASE_URL` 實盤 +
    `ALLOW_LIVE_TRADING`）；上真錢仍走既有 `promotion.py`（人核准 + 雙閘）。預設從 curated 觸發，
    保留「validated→人晉升 curated」人工閘。手動 deploy 端點重構成呼叫共用函式（行為不變）。
  - 測試：`tests/test_auto_deploy_knowledge.py`（自足 temp sqlite）11 例——helper 建 paper bot/
    activate 旗標/去重/空清單、批次器建+冪等/disabled/狀態過濾/validated 觸發/MAX 上限/空 symbols。
- **preset → 知識庫候選 橋（讓工作台手做方案進自動驗證管線）**：先前 `auto_validate` 只吃
  `StrategyKnowledge` candidate，使用者在「策略方案」工作台（`StrategyPreset`）手做的是死路、進不了
  驗證。新增 `POST /presets/{preset_id}/to-knowledge`（`backend/routers/presets.py`，鏡像既有
  `to-bot` 的「複製一份」精神）：把 preset 的 `name`/`strategy_key`/`params` 複製成一筆
  `StrategyKnowledge(status="candidate")`（`notes`→`scenario`），之後就被 auto_validate 吃。
  測試：`tests/test_presets.py` 加 to-knowledge→建 candidate 映射正確、404 共 2 例。
- **curated 策略 → Paper Bot 部署橋（補「策展庫接不到 Bot」斷層）**：先前管線到
  `curated`（人晉升的策展庫）就斷——`promote_knowledge` 只改狀態、不建 Bot，curated 是死路；
  Bot 只能手建或自動部署（screener 海選、不查知識庫）。新增 `POST /knowledge/{kid}/deploy`
  （`backend/routers/knowledge.py`）：
  - **只允許 `status==curated`**（非 curated 回 400，守人在迴路：必先經 OOS 驗證 + 人晉升）。
  - knowledge 列**不綁標的**（驗證是跨籃子做的），部署時由人指定 `symbols`（一檔或多檔，
    各建一個 Bot；自動去空白/去重/大寫）。
  - 新 Bot 一律 `is_active=False` + `promotion_status="paper"`（不自動開跑、不碰雙閘安全閥）；
    人再按 `/bots/{id}/start`，跑出 Paper 實績後走**既有** `promotion.py` 提議上真錢。
    至此「collector→discovery→OOS 驗證→validated→人晉升 curated→部署 Paper Bot→上真錢」整條鏈接通。
  - 部署軌跡寫 explorations 記憶（沿用 `write_knowledge_note`，action=`deploy`）。
  - 測試：`tests/test_knowledge.py` 加 curated→建 N 個 Paper Bot（strategy/params/Paper/inactive
    映射正確）、非 curated→400、symbol 去重 3 例。

### 變更

- **驗證籃子擴成 38 檔跨產業（8→38）**：`config.py: AUTO_VALIDATE_SYMBOLS` 預設由 8 檔擴為
  大盤指數 5 / 半導體 10 / 能源 3 / 科技 10 / 金融 5 / 工業 5（跳過醫療、零售）。籃子越寬越難
  過擬合單檔個性；各檔跑 walk-forward → OOS EV 池化（judge 零改、只改餵料）。`.env.example` 同步。
  ★代價：單筆驗證更慢（38 檔 × ~30 folds），建議搭 `AUTO_VALIDATE_BATCH_SIZE=1` + 下面的 keepalives。
- **Neon 長算連線：database.py engine 加 TCP keepalives（取代 worktree-only 的臨時 .env hack）**：
  `_connect_args` 對非 SQLite 加 `keepalives=1/idle=30/interval=10/count=5`。`pool_pre_ping` 只救
  「借用前」的死連線，救不到「已借出、正跑 38 檔 × 10 年驗證 / 審查員掃艦隊」中途被 Neon
  serverless 掐掉的閒置連線（算完 commit/rollback 才炸 `server closed the connection unexpectedly`）。
  keepalives 讓 OS 每 30 秒探測撐住連線。所有長算 Neon 操作（含 VM/排程端）一勞永逸受惠。
- **自動建艦隊降載：`AUTO_DEPLOY_KNOWLEDGE_CHECK_INTERVAL`（預設 300 秒）**：每筆知識部署到全部
  標的，好策略一多艦隊就大（190 Bot × 60 秒 ≈ 3.2 req/s 逼近 Alpaca 免費 200/min）；自動建的 Bot
  改用 5 分鐘輪檢（~0.6 req/s）。手動 deploy 仍用 60 秒預設，不受影響。
- **自動驗證回看窗：3 年 → 10 年（`AUTO_VALIDATE_DAYS` 1100→3650）**：~30 folds、橫跨更多市況、
  最難過擬合。代價是單筆驗證變慢（N 檔 × ~30 folds）。★前提：`market_data.get_bars(source=
  DATA_SOURCE)` 要抓得到 10 年（Alpaca 免費約 2016 起 ~9 年、yfinance 全史）；抓不到只會 fold 變少、
  不影響判準正確性。`auto_validate` / `revalidate_basket.py` 自動吃新值。`.env.example` + test_validation
  守門註解同步。
- **驗證標的：單檔 SPY → 跨產業一籃子池化（Phase 12 延伸，judge 零改、只改餵料）**：
  先前 OOS 驗證只用單一標的（`AUTO_VALIDATE_SYMBOL="SPY"`），樣本窄＋過擬合單檔個性
  （已晉升 7 筆 curated 全只在 SPY 測過、含退化參數 `period=2`）。改成每檔各跑 `walk_forward`、
  OOS EV **池化**後餵**同一支** `is_layer_worth_it`（`validation.py` judge 與
  `VALIDATION_MIN_IMPROVEMENT=0` **完全沒動**，只改匯進去的料）：
  - **新 config 兩欄**（`backend/config.py` + `.env.example`）：`AUTO_VALIDATE_SYMBOLS`
    （逗號字串，預設 `"SPY,AAPL,JPM,XOM,JNJ,CAT,WMT,NVDA"`＝大盤+科技/金融/能源/醫療/工業/
    零售/半導體）+ `AUTO_VALIDATE_MIN_TRADES_PER_SYMBOL`（門檻 X）。新增 `@property
    auto_validate_symbols`（拆逗號/去空白/去重/大寫，空字串退回單檔 `AUTO_VALIDATE_SYMBOL`）。
    舊 `AUTO_VALIDATE_SYMBOL` 保留不刪。
  - **池化選法（採方案 a）**：某檔所有 fold 總 `num_round_trips` < 門檻 X → **整檔排除**
    （避免靠運氣少數幾筆大賺污染）；達標檔各自先算「該檔所有 fold 平均 EV」，再 N 檔**等權平均**
    成池化 EV（簡單夠用；「每檔每日平均 EV」的方案 b 列為 future）。
  - **門檻 X 取 5**（`AUTO_VALIDATE_MIN_TRADES_PER_SYMBOL=5`）：保守低門檻，先求「該檔真的有
    出手」即納入；太高會把短窗低頻策略全排除掉。
  - **fold 數語意改**：原「walk-forward fold 數 ≥ `VALIDATION_MIN_FOLDS`(3)」→「**達標標的數**
    ≥ 3」。`is_layer_worth_it` 的 `min_folds` 檢查零改，餵進去的 `candidate_oos` 從「各 fold EV」
    變「各達標檔的平均 EV」，語意自然轉為「達標檔數」，避免單檔撐全場。
  - **`evolution.validate_candidate` 簽名 `symbol` → `symbols`**：內部正規化 str/list——
    **單檔（str 或長度 1）走原路徑、`oos_metrics` 結構不變**（既有測試 / `rejudge_noop` 相容）；
    多檔走新 `_validate_basket`。`oos_metrics` 新增 `symbols` / `per_symbol`（每檔 fold 數 / 總交易 /
    平均 EV / 是否達標 / 被排除原因）稽核欄；頭條 `expected_value`＝池化平均；保留
    `noop`/`verdict` 鍵的稽核區分。某檔抓不到資料/湊不出 fold → 跳過記 `per_symbol`，**全失敗才 raise**。
  - **跨檔 no-op 守門**：整籃無任何達標檔（全被門檻排除/全零交易）→ rejected 掛 `noop` 鍵
    （沿用 `is_noop` 精神，但籃子層是逐檔門檻）。
  - **`auto_validate.run_auto_validate` 改丟籃子** `settings.auto_validate_symbols`；失敗隔離/批次/
    冪等不動。手動端點 `POST /knowledge/{id}/validate` 新增可選 `symbols`（不傳用單 `symbol`，相容）。
  - **新腳本 `scripts/revalidate_basket.py`**（一次性維運，同 `rejudge_noop.py` 範式）：對 Neon
    `status in (candidate,validated,curated)` 逐筆用籃子**重跑**回測重判，預設 **dry-run 只印不改**
    （印 舊→新 status / 池化 EV / per_symbol 分布 / 哪檔被門檻排除；curated 降級前印明顯警告行），
    `--apply` 才寫 DB、逐筆 commit、單筆失敗隔離。**本次只實作，尚未對 Neon 執行全庫重驗**
    （含 7 筆 curated 去留待日後人工 `--apply` 後回填）。
  - **測試**：`tests/test_evolution.py` 加籃子池化→validated、跨檔 no-op→rejected、門檻排除一檔、
    達標檔數不足→rejected、某檔無資料跳過、全失敗 raise、單檔 str 保留舊結構 7 例；
    `tests/test_auto_validate.py` 對齊籃子斷言。**`pytest test_evolution test_auto_validate
    test_validation test_knowledge test_discovery test_strategy_generator test_strategies → 85 passed`**。
  - 預設仍**全關**（`AUTO_VALIDATE_ENABLED=false`）；晉升 curated 仍只能人觸發。實作合約見
    [`docs/history/phase-12-strategy-discovery/handoff-multi-symbol-basket.md`](docs/history/phase-12-strategy-discovery/handoff-multi-symbol-basket.md)。

### 修正

- **自動部署改吃「狀態門檻」而非精確值——救回撈不到 curated 的盲點**（`backend/services/auto_deploy_knowledge.py`）：
  原查詢 `status == AUTO_DEPLOY_FROM_STATUS` 是**精確比對**。上線後設 `validated`（跳人工閘）時，
  既有 5 筆**已被人晉升的 `curated`** 好策略（階序比 validated 高）反而撈不到，加上當下 `validated` 為 0，
  導致開機 catchup 全鏈跑完卻 **0 bot**。改成階序門檻 `_deployable_statuses`（candidate<validated<curated，
  rejected 永不部署）：`from=validated` 取「validated 及以上」涵蓋 curated；`from=curated`（預設）仍只取
  curated，**向後相容、VM 姿態不變**。加測試 `test_auto_deploy_validated_threshold_includes_curated`。
- **蒐集員通知數字不再誤導——改顯示收件匣累計總數**（`backend/services/collector.py`）：
  Discord/LINE 推播原本顯示「跳過 N 篇已收過」，N 是「這一輪 RSS 抓回的批次裡有幾篇重複」。
  每輪 feed 都只抓最新固定幾篇，收齊後 N 永遠卡同一個死數字（例如 34），又跟使用者實際
  累計總收數對不上，造成誤解。改成「（收件匣目前共 M 篇）」，M = `RawStrategyFind` 全表筆數，
  真實且會隨收料成長。測試不受影響（`test_collector.py` 16 passed）。
- **修 no-op 漏洞——零交易候選不再混進 validated（Phase 12，收上一條待辦）**：
  上一條重驗暴露的「5 筆 `oos_mean=0.0` 假性過閘」（零交易＝跟「不出手」基準打平＝
  `worth=True`）正式堵掉。**判準其餘不動**（`VALIDATION_MIN_IMPROVEMENT=0` 保留），
  只多一道零交易守門：
  - `evolution.py`：新增純函式 `is_noop(folds)`（所有 fold `num_round_trips` 全 0 ＝ no-op）。
    `validate_candidate` 在跑 `is_layer_worth_it` **之前**先判：是 no-op → 直接 `rejected`，
    `oos_metrics` 掛 `"noop"` 標記（含 reason / total_round_trips），**不進 verdict**。
    三種 reject 來源由鍵稽核區分：`noop`（零交易）／`verdict`（判子刷掉）／`auto_validate`（操作性放棄）。
  - `scripts/rejudge_noop.py`（新，一次性維運）：對既有 `status=validated` 列**不重跑回測**，
    直接套同一支 `is_noop` 重判（folds 才剛算過、存在 `oos_metrics["walk_forward"]`）；
    no-op 退成 rejected、就地重建 `oos_metrics`（JSON 欄位重新賦值才持久化）。
    預設 dry-run 印報告（含「保留的 validated 清單」供人工晉升），`--apply` 才寫 Neon。
  - `tests/test_evolution.py`：新增 `is_noop` 全零/有交易/空/缺鍵 4 例 + `validate_candidate`
    no-op→rejected（含 noop 鍵、無 verdict）/ 有交易正 EV→仍 validated（不誤殺）2 例。
    **`pytest test_evolution test_auto_validate test_validation` → 27 passed**。
  - 重判結果（人工 `--apply` 跑 Neon 後回填）：5 筆 no-op → rejected、validated 剩 7 筆正期望
    （bollinger ~131、ma_crossover{30,10} ~32、stochastic ~3.5…）→ 由人在 LibraryPage 晉升 curated。
- **修自動驗證窗太短——OOS 閘從沒真的評過策略（Phase 12 接續品質地基）**：
  跑 `run_auto_validate` 後 30 筆 candidate 全 rejected、0 validated。診斷 Neon 發現
  **33 筆全死於同一理由「fold 數不足（1 < 3），樣本太少不採信」**——每筆只湊出 1 個
  walk-forward fold。根因：`evolution.validate_candidate` 用預設 `days=365`（SPY ~250 根），
  但 `walk_forward_splits` 要 `train(180)+test(60)` 才出第一 fold、每 `step(60)` 滾一個，
  湊 `VALIDATION_MIN_FOLDS(3)` 需 ≥360 根 → 250 根永遠只 1 fold → **任何策略都不可能過閘**
  （OOS 閘等於沒在評品質，只對「樣本不足」一律打回）。使用者一度誤把「3 筆高 EV」當好策略，
  實為單一 60 根窗的僥倖數字 + 退化參數（`period=2`）。修法（**判準不放水，只加長資料窗**）：
  - `config.py`：新增 `AUTO_VALIDATE_DAYS`（預設 1100 ~754 根＝9 folds；實測 540=3、750=5）。
  - `auto_validate.run_auto_validate`：把 `days=settings.AUTO_VALIDATE_DAYS` 傳進
    `validate_candidate`（該函式早就收 days 參數，只是沒人傳）。
  - `tests/test_validation.py`：新增守門 case，鎖「production 窗 vs MIN_FOLDS 所需根數」、
    並記錄 250 根（舊 365 天）產不到 MIN_FOLDS 的 bug 本體。**17 passed**。
  - 修後對 Neon 重驗 33 筆（rejected→candidate 重跑，2026-06-17）：每筆 **folds=9**
    （窗確實修好，不再 1 fold）→ **validated 12 / rejected 21 / failed 0**。
  - **重驗暴露下一個誠實問題**：12 筆 validated 有 5 筆 `oos_mean=0.0`（長均線等在 60 根
    測試窗內沒觸發訊號＝整段沒交易），它們「過關」純因 `VALIDATION_MIN_IMPROVEMENT=0`
    ——不交易＝EV 0＝跟「不出手」基準打平就算 worth=True。那是「不下場所以不輸」的 no-op、
    非好策略。真正 OOS 正期望僅約 7 筆（bollinger ~131、ma_crossover{30,10} ~32、
    stochastic ~3.5…），且含退化參數 `period=2`（過擬合嫌疑）。**待辦**：把「零交易」與
    「贏過不出手」分開（如要求 `num_round_trips>0` 或 `MIN_IMPROVEMENT>0`），否則 no-op
    會混進可策展清單。本次不改判準（避免一次動太多），先記錄。**（已收：見本區塊最上方
    「修 no-op 漏洞」一條——採 `num_round_trips>0` 守門。）**
- **修探勘橋「參數名漏洞」——LLM 提案被靜默吃預設值，OOS 假淘汰（Phase 12 品質地基）**：
  `discovery.build_triage_prompt` 只告訴 LLM「有哪些策略鍵」卻**沒給每個策略的合法參數名**，
  模型亂猜名（產出 `ma_crossover {short_ma:50, long_ma:200}`，正解是 `short_window`/
  `long_window`）；策略 `generate_signal` 用 `params.get("名", 預設)` 讀參數，遇到不認識的
  鍵**靜默回退預設值**不報錯 → 候選回測其實全用預設 5/20 跑，OOS 測到的根本不是提案策略 →
  全 rejected（看起來像「LLM 品質差」，其實是接線 bug）。修法：
  - `strategies/__init__.py` 新增 `STRATEGY_PARAM_SPECS`（9 策略的合法參數名 + 範圍，
    集中宣告、鏡像既有 `STRATEGY_LABELS`）+ `param_spec()` helper，作為單一真相來源。
  - `discovery.build_triage_prompt` / `strategy_generator.propose_params` 把該策略的
    參數 menu 攤進 prompt（只准用這些名、值落範圍內）。
  - `discovery.triage_find` 新增驗證：提案參數名須全 ∈ schema（擋亂猜的名），值夾回
    `[min,max]`（存進 candidate 的＝實際回測的，誠實不分岔）；`propose_params` 同步濾掉錯名組。
  - **勘誤**：原先誤判「候選全 rejected＝LLM 品質差」，把 `DISCOVERY_BATCH_SIZE` /
    `AUTO_VALIDATE_BATCH_SIZE` 降到 3 想「審慎一點」。實際禍首是上述接線 bug——batch size
    只決定「一輪處理幾筆」，**與單筆品質無關**；怕品質該調的是參數 schema 驗證 +
    `_MIN_CONFIDENCE`。修好後 batch size 可放心放大。
  - **測試流程**：
    1. `pytest tests/test_discovery.py tests/test_strategy_generator.py` → **17 passed**
       （含新增 case：錯名 `short_ma` 應被 `triage_find` 擋、正名放行、超界值夾回範圍、
       `propose_params` 濾掉錯名組）。
    2. `pytest tests/test_strategies.py test_strategies_registry.py test_knowledge.py
       test_auto_validate.py` → **41 passed**（確認新增 `STRATEGY_PARAM_SPECS` 沒弄壞既有）。
    3. `scripts/pipeline_smoke.py` 真打本機 Ollama（llama3.1）→ 候選回
       `rsi {period:14, oversold:30, overbought:70}` 參數名全合法；OOS 段在無 `.env`
       的 worktree 因抓不到行情優雅記 failed（接線 OK，真環境有金鑰才跑完）。
    4. 部署後對 Neon 跑 `requeue_and_drain.py --apply --drain`（2026-06-17）：
       51 筆 triaged→new（收件匣 29→80 new）→ 修好的探勘橋 28 輪抽乾→
       **processed=80, built=30, discarded=50, skipped=0**。知識庫多出 30 筆 candidate
       （帶合法參數名），待 `run_auto_validate` 跑 OOS 閘；validated 再由人晉升 curated。
       discarded 50（LLM 判定與既有策略無關）屬正常漏斗淘汰，非 bug。
- **修雲端 Neon 連線閒置被斷導致背景排程崩潰**——VM 上 `run_collector_scan` 每小時
  在 `upsert_finds` 拋 `psycopg2.OperationalError: SSL connection has been closed
  unexpectedly`：Neon 會把閒置太久的連線從伺服器端掐掉，連線池裡那條死 socket 下次
  借用就炸（掃描間隔長的背景工作最容易踩）。`database.py` 的 engine 對非 SQLite 的
  雲端 DB 加 `pool_pre_ping=True`（借連線前先 ping，死了就重建）+ `pool_recycle=300`
  （逾 300 秒主動回收）。SQLite 本機檔案不受影響。
- **堵後端公網裸奔漏洞**——VM systemd `albee-backend.service` 的 `ExecStart` 實際綁
  `--host 0.0.0.0`（與部署文件規定的 `127.0.0.1` 漂移），等於無認證 API 對整個網際網路
  開放。已在 VM 改回 `--host 127.0.0.1`（只綁本機，看畫面走 SSH tunnel）。
  ⚠️ 此為 VM 端 systemd 設定，非本 repo 檔案；新機部署照
  [`free-vm-deployment.md`](docs/guides/free-vm-deployment.md) §4 的範本本就是 `127.0.0.1`。

### 新增

- **探勘管線端到端 smoke 腳本** `scripts/pipeline_smoke.py`：在臨時 SQLite（**不碰 Neon**）
  塞 1 筆合成素材，跑「探勘橋 → 候選 → OOS 閘」整條水管，逐段印 verdict + 驗候選參數名合法。
  開排程常駐前一鍵體檢（Ollama 連線 / 提案品質 / OOS 接線）。
- **11 模組策略探勘工作流文件** `docs/reference/strategy-pipeline-workflow.md`（操作者視角）：
  把側欄 11 頁照「素材→上線」順序串成主水管 + 政治員煞車 + 5 條旁路，標明人只在
  「晉升 curated／跑真錢」兩點出手。已更新 `docs/README.md` 索引。
- **煙霧測試（Smoke Test）**——補上「整台機器開得起來、核心端點回得了話」的整合關卡：
  - `tests/test_smoke.py`：`pytest -m smoke` 起 `TestClient(app)`（驗 lifespan：init_db +
    scheduler leader 選舉不爆）→ 打 `/`、`/status` 與 18 個無金鑰讀端點都回 200 →
    驗 `/positions` 無金鑰優雅降級回 `[]`；整合層（`/account`、`/quotes`）用
    `RUN_INTEGRATION_SMOKE=1` 才跑。已驗 **21 passed, 2 skipped**。
  - `scripts/smoke_test.sh`：線上端點煙霧（curl 打 6 個功能端點），掛進 `deploy.sh`——
    健檢通過後再跑一次，任一端點掛掉一樣觸發回滾（已驗正常全過、故意打錯 `exit 1`）。
  - `pyproject.toml`：註冊 `smoke` marker + `testpaths=["tests"]`（避免無路徑跑時誤收
    `backend/test_connection.py` 害 pytest 崩潰）。
  - `ci.yml`：`test` job 加 `pytest -m smoke` 先跑早退；新增 `frontend` job
    （`npm ci` → `npm run test`（Vitest）→ `npm run build`），補上 CI 從不驗前端的缺口；
    `deploy` 改 `needs: [test, frontend]` 兩關全綠才部署。
  - 計畫書 [`docs/guides/smoke-test-plan.md`](docs/guides/smoke-test-plan.md)（L1~L4 涵蓋範圍、
    三種跑法、混合雲對照、故障排除），docs 索引同步補列。

- **上雲 runbook [`docs/guides/cicd-vm-setup.md`](docs/guides/cicd-vm-setup.md)**——把 2026-06-16
  「CICD 已建好但代碼從沒上雲」的排查與上線步驟寫成單一操作指南：手動部署、補 GitHub
  Secrets（`VM_HOST`/`VM_USER`/`VM_SSH_KEY`）、VM 免密碼 sudo、**關掃描要改 DB 非 `.env`**
  （`scan_interval_min` 存 Neon、`.env` 種子只在首次生效）、Windows 用 Git Bash 連 VM 避開
  PowerShell OpenSSH 權限坑、驗單實例。docs 索引同步補列。

### 修正

- **CD 首次自動部署修復（缺 secret + VM 缺 deploy.sh 的雞生蛋）**——兩件事：
  - **補齊部署 secret**：repo 原本零 secret，CD 的 SSH step 讀到空 `VM_HOST` →
    `error: missing server host` 4 秒就掛。設好 `VM_HOST` / `VM_USER` / `VM_SSH_KEY`
    （Oracle Micro VM `158.101.127.219`、`ubuntu`、對應私鑰）。
  - **CD 自我 bootstrap**：VM 跑的是舊 checkout、還沒有 `scripts/deploy.sh`（部署腳本
    本身是後來才加的 commit），SSH 進去跑 `bash scripts/deploy.sh` → `No such file or
    directory (status 127)`。`ci.yml` deploy step 改為先 `git fetch origin main` +
    `git checkout origin/main -- scripts/deploy.sh` 撈出腳本本身再執行；只 checkout
    腳本、不動 HEAD，保留 deploy.sh 內部 PREV/rollback 語意。
  - **健康檢查改重試**：`deploy.sh` 原本 `sleep 5` 後單發一次 curl，新後端開機（連 Neon /
    import）來不及 → 誤判健檢失敗觸發回滾。改成重試最多 ~60s（20 次 × 3s）。
  - **回滾修正 code/schema 一致性**：原回滾 `git reset` 舊碼後又跑 `alembic upgrade head`，
    但舊碼缺新增的 migration 檔 → `Can't locate revision` 直接炸（exit 255），DB 卡在新
    schema、與舊碼不一致。改為**部署前先記 DB revision**，回滾時先用「新碼」
    `alembic downgrade` 回該 revision（新碼才帶得齊 migration 檔），再 `git reset` 舊碼 +
    重啟，不再 `upgrade head`。

### 新增

- **回測支援 2000–2026 長區間 + 報表顯示真實年月**——三件事：
  - **報表真實日期**：回測引擎 `_simulate_from_signals` 現在收集 `equity_dates`
    （與 `equity_curve` 等長）並寫進結果 / `backtest_runs.metrics`。
    `analytics.returns_from_equity` / `tearsheet_html` 加選用 `dates` 參數，績效報表
    月報酬表改顯示**真實年月**，不再一律從假的 2000-01 起算。沒帶日期 / 舊紀錄 /
    日期解析失敗 → 自動退回假 2000（向後相容、可重現，不讓報表爆）。
    ⚠️ 舊的 `backtest_runs` 沒有 `equity_dates`，要**重跑一次回測**才有真日期。
  - **長區間自動選資料源**：`backtest_engine._resolve_source` ——用 `alpaca`（免費版
    抓不到 2000 年）但 `days` 超過 `ALPACA_MAX_DAYS`（1825≈5 年）時自動改 `yfinance`
    （可回溯 20–50 年），顯式指定 yfinance 不受影響。`days` 無上限，2000→2026 ≈ 9500 天，
    多年資料走本機 `bar_cache` parquet 快取、第二次秒回。
  - **前端快捷區間**：`BacktestPanel` 新增「快捷區間」下拉（近 1/5/10 年、最長 2000 起，
    常數 `BACKTEST_RANGES`），選了填進回測天數。
- **開啟自動管線 runbook**——新增
  [`docs/guides/enable-auto-pipelines.md`](docs/guides/enable-auto-pipelines.md)：釐清
  「自動選標的」（screener/opportunity_scan，盤中自動回測挑策略+標的）與「策略點子探勘」
  （collector→discovery→auto_validate）是**兩條獨立的線**，各列要開哪些開關、怎麼驗證；
  開關預設全關（晉升 curated / 自動部署 / 真錢雙閘一律維持人工）。

- **全自動 CICD：push → 驗證關卡 → 自動部署 VM（含失敗回滾）**——把舊的 `test.yml`
  升級為兩段式 `.github/workflows/ci.yml`：
  - **CI（部署前驗證關卡，「先預測會炸的問題」）**：每次 push / PR 跑①全套 `pytest tests/`
    （無金鑰/無網路皆優雅降級，490 passed）②錯誤級 `ruff`（E9/F63/F7/F82，只抓語法錯/
    未定義名稱，不管風格）③`alembic upgrade head` 可套用（抓壞掉的 migration）
    ④`import backend.main` 煙霧測試（抓啟動階段就爆的）⑤`alembic check` 遷移漂移提醒。
    **觸發分支補上 `develop`**（主力開發分支，舊 CI 只在 main/master 跑、從沒涵蓋過）。
  - **CD（自動部署）**：push 到 `main` 且 CI 全綠 → `appleboy/ssh-action` SSH 進 VM 跑
    `scripts/deploy.sh`：記住舊版 → 拉新碼 → 裝依賴 → `alembic upgrade head` → 重啟
    服務 → 打 `GET /` 健康檢查；**失敗自動回滾到上一版**並重啟。需在 repo 設 Secrets
    `VM_HOST` / `VM_USER` / `VM_SSH_KEY` 與 VM 上的免密碼 sudo 重啟權限（腳本內有說明）。
- **排程器選主鎖（防多實例重複推播/下單）**——新增
  [`backend/services/scheduler_lock.py`](backend/services/scheduler_lock.py)：地端 + 雲端
  VM 同連 Neon 時，開機用 PostgreSQL advisory lock 選主，只有 leader 掛 APScheduler 排程
  （Bot 下單、collector/心跳通知…），其餘實例只當唯讀 API，避免重複下單/重複推播/互蓋止損。
  `main.py` lifespan 整段排程改為「搶到鎖才掛」；SQLite 單機永遠是 leader（無競爭）。
  連線一斷鎖自動釋放，另一實例下次開機接手。新增 `tests/test_scheduler_lock.py`。
- **政治專討員一鍵啟動 `start_political_watcher.bat`**——本機雙擊即啟 `backend.bots.political_watcher`
  （讀鏡像頻道 → Ollama 判讀 → 偏空推 #Albee-通知）。同 `start_backend.bat` 的看門狗迴圈：
  崩潰 10 秒自動重拉、`%~dp0` 錨定根目錄。前提：Ollama 先開 + `.env` 設好 `POLITICAL_*`。

### 修復

- **政治專討員雲端狂洗版 + 漏抓貼文根治（2026-06-15）**——雲端部署後政治員短時間狂發
  通知、且川普發文當下沒抓到。根因是「批次重判 + 通知層零節流」（非自我回饋迴圈，通知
  頻道與監看頻道不同）：搬 Neon 後雲端 `political_events` 空表 → 回補/即時把一批舊貼文
  重判 → 每筆偏空都打一次 `notify`；回補路徑還會對歷史舊貼文補發警報。修法四層收斂：
  ①**回補不發通知**（`_handle_message` 加 `notify_on_alert`，回補傳 False、即時傳 True）；
  ②**同作者警報節流**（`POLITICAL_ALERT_COOLDOWN_MIN` 預設 10 分鐘，冷卻期內只發一則）；
  ③**DB 加 `(author, posted_at)` 唯一鍵**（Alembic 遷移 `a8f1c2d3e4b5`，先 dedup 既有
  重複列再加約束；`record_event` 撞鍵回 `None`，呼叫端據此不重發）；④**回補改「時間型
  補齊」**（只補比 DB 既有最新貼文更新的，空表才退回筆數型；`POLITICAL_BACKFILL_LIMIT`
  預設 5→30）修漏抓。新增 `tests/test_political_watcher.py`（回補不發/即時發一則/重判不發/
  節流/唯一鍵/`latest_event_time`）。另修本機 `.env` 一行 cp950 註解壞位元組（`load_dotenv`
  UTF-8 解碼崩潰、後端與 alembic 起不來）→ 重新編碼為 UTF-8（備份 `.env.bak`）。

### 新增

- **開發踩坑紀錄文件**——新增 [`docs/reference/dev-pitfalls-log.md`](docs/reference/dev-pitfalls-log.md)：
  查閱全專案 172 個 commit，把歷來實際炸過、用 commit 修掉的坑收斂成一頁
  （症狀／根因／修法／出處 commit + 快速索引），分 10 主題（Windows 編碼／DB·Alembic／
  依賴啟動／測試確定性／回測=實盤誠實性／前端／即時系統迴圈／Git 衛生／前瞻偏誤／Linux 部署）。
  定位為 `CLAUDE.md`「已知注意事項」鐵則的完整史料版；同步在 `docs/README.md` 索引與
  `CLAUDE.md` 加指標連結。

### 變更

- **資料庫切換 Neon 雲端 PostgreSQL（2026-06-12）**——`DATABASE_URL` 指向 Neon 免費
  PG 17（新加坡 `ap-southeast-1`），兩台電腦共用同一份資料、換機零搬遷；沒填
  `DATABASE_URL` 仍自動退回本機 SQLite，程式零改。一次性搬遷已完成（Alembic 建表
  20 遷移／15 表 + SQLite 資料搬入；踩坑：遷移種子列會撞 PK，搬遷腳本需先清表再插入，
  已記錄）。**新電腦完整設置流程見 [`docs/guides/setup-postgres-sync.md`](docs/guides/setup-postgres-sync.md)
  的「換電腦 / 新電腦」一節**（git pull 後照做即可）。

### 新增

- **後端正式上雲 24/7（2026-06-15）**——把 FastAPI 後端部署到 Oracle Cloud 免費
  E2.1.Micro VM（Ubuntu，`158.101.127.219`），systemd 服務 `albee-backend`
  （`Restart=always` + 開機自啟）跑 uvicorn 0.0.0.0:8000，連同一份 Neon 雲端 PG、
  Paper 模式（`ALLOW_LIVE_TRADING=false`），本機關機照跑。踩坑：①兩層防火牆（Oracle
  VCN Security List + VM iptables，ACCEPT 8000 須插在 REJECT 規則之前）少一層就 timeout；
  ②1GB RAM 加 2GB swap，Ollama 跑不動故 `LLM_BASE_URL` 清空停用助手。**並開第二台
  Micro（`albee-grab`, `150.136.45.198`）掛 OCI CLI `grab-a1.sh` 重試搶 A1.Flex**
  （Ashburn 3 AD、30s 輪詢、cron `@reboot` 開機自動續搶），搶到再把 bot 搬上 A1。
  詳見 [`docs/guides/cloud-local-division.md`](docs/guides/cloud-local-division.md)、
  [`docs/guides/oci-grab-a1.md`](docs/guides/oci-grab-a1.md)。

- **雲端／地端工作劃分文件 + 搶 A1 runbook**——後端 24/7 上 Oracle E2.1.Micro 後，
  補三份產物釐清分工：①[`docs/guides/cloud-local-division.md`](docs/guides/cloud-local-division.md)
  講「誰在哪跑」，標出最重要紅線——**本機與雲端不可同時讓 Bot active**（兩個 APScheduler
  看同一份 Neon DB + 同一 Alpaca 帳戶 = 重複下單／互蓋止損，`backend/main.py` lifespan
  一啟動就恢復所有 active Bot），附功能對照表、本機前端連雲端 IP、Micro RAM/swap 健康監控
  指令；②[`docs/guides/oci-grab-a1.md`](docs/guides/oci-grab-a1.md) + ③`scripts/grab-a1.sh`
  ——用第二台 Micro 掛 OCI CLI 重試腳本搶 A1.Flex（輪 AD、75s 間隔、容量釋出即建機），
  腳本不含任何真實金鑰/OCID（自填、勿 commit）。純文件 + 獨立 shell，不動後端邏輯。

- **政治員啟動回補**——watcher 啟動時（`on_ready`）自動抓 Discord 頻道最近
  `POLITICAL_BACKFILL_LIMIT`（預設 5，0=關）筆「有文字內容」的歷史貼文，走既有
  判讀＋落表路徑補進 `political_events`：電腦非 24h 開機也不漏啟動前的政治情緒。
  防重用 `(author, posted_at)` 天然鍵（`political.event_exists`，免加欄位免遷移）；
  回補由舊到新處理保時序、失敗只印警告不影響即時監聽。測試 +2（防重/該不該收）。

### 修正

- **政治員自我回饋迴圈防護**——系統通知 webhook（`DISCORD_WEBHOOK_URL`）若指向
  watcher 監看的同一頻道，自己的風險警報會被自己讀回去判讀 → 再發警報 → 無限迴圈
  （實測踩到，15 秒一筆洗版）。修法：①即時監聽與回補都依 webhook id 跳過自己通知
  webhook 發的訊息（`_is_own_notification`）；②啟動時偵測「通知 webhook 與監看頻道
  同頻道」印 🚨 設定錯誤警告。正解仍是通知用獨立頻道的專屬 webhook。測試 +1。

- **文件：前端頁面地圖**（`docs/reference/frontend-pages-map.md`）——sidebar 17 頁
  拆四條工作流（探勘入庫/研究回測/上線執行/情報檢討），Mermaid 小圖×6（拆小張
  橫排避免瀏覽器縮太小）+ 開第一隻 Bot step-by-step + 模擬交易 When/What/Why
  對照表（含「為何選這支股」缺口註記）+ 各頁資料由誰產生。docs/README.md 索引同步。

- **抓取效率升級：批次多檔抓取 + 並行 I/O + 限流**——瓶頸調查確認「慢在逐檔 HTTP
  往返，不在 RAM」（快取已是磁碟 parquet），把傳輸層批次化、判準零修改：
  - **批次 K 線**：`alpaca_client.get_bars_multi()` / `yfinance_client.get_bars_multi()` /
    `market_data.get_bars_multi()`——一次請求抓 N 檔（Alpaca `StockBarsRequest`
    原生吃 list；yfinance 走 `yf.download` 批次），每檔契約與單檔版逐欄一致、
    缺檔回空 DataFrame。watchlist 掃描從「N 檔 N 次往返」變 1 次。
  - **批次快取**：`bar_cache.get_bars_cached_multi()`——逐檔查 parquet 快取分三桶
    （全命中 0 API / 無快取整段 / 尾缺口），有缺口的桶批次補抓（最多 2 次 HTTP），
    缺口判定/合併/切片重用單檔版同一組純函式，結果與逐檔跑完全一致（有測試守門）；
    批次失敗自動退單檔舊路徑。單檔 `get_bars_cached` 一字未動。
  - **批次報價**：`alpaca_client.get_latest_prices()` + `quote_stream` 輪詢改批次——
    一輪所有訂閱股票 1 次請求（原本每 5 秒逐檔各打一次）。
  - **限流保險絲**：`alpaca_client` 加 token bucket（`ALPACA_RATE_LIMIT_PER_MIN`，
    預設 200 = Alpaca 免費版額度；0=不限流），所有資料 API 同一個桶，
    交易單不限流（下單延遲不可接受）。防標的一多被 429 打爆。
  - **並行 I/O**：FRED 多序列（`fred_client.get_observations_multi`，DB upsert 仍
    序列化）與 collector 多條 RSS 改小 ThreadPool 並行（`FETCH_MAX_WORKERS`，
    預設 4；同站每輪仍只一次請求，不對單站猛打）。
  - **呼叫端接上**：screener 第一層批次抓 + 第三層回測前批次暖快取、
    `opportunity_scan.collect_factor_snapshots` 批次、每日領導股回測前批次暖快取。
  - 測試：新增 `tests/test_batch_fetch.py`（12 案：契約一致/單請求/缺檔打底/
    零 API 命中/混桶/失敗 fallback/批次=單檔一致性/限流/時鐘倒退防卡死），
    `test_quotes.py` 隨批次輪詢同步更新。
  - 實測（10 檔 × 60 天、冷快取、yfinance 備源、暖 session 後）：批次 0.32s vs
    逐檔 1.31s ≈ **4.1x**；暖快取第二次 0.05s（0 次外部 API）。Alpaca 源為真正
    單請求批次，預期倍數更高。回測網格並行（P3）量測後暫不做——抓取已非瓶頸。

- **Bot 活動即時可視化（真跑偵測器 + 策略可視化）**——解決「前端無法確認機器人
  是真跑還是假跑」：Bot 一輪執行 <1 秒、前端 30 秒輪詢，中間全黑盒。四件套全上：
  - **後端事件管線**：新增 `backend/services/bot_activity.py`（BotActivityHub：
    APScheduler 執行緒 → `loop.call_soon_threadsafe` → asyncio.Queue → 單一
    forwarder task 扇出，保證事件順序；ring buffer 60 則供新連線回放）+
    `backend/routers/bot_activity.py`（WebSocket `/ws/bot-activity`，連上即收）。
    `bot_manager.py` 執行循環插樁 ~10 個 emit 點（cycle_start → fetch_data →
    compute_signal → risk_check → decision → order_submitted → cycle_end），
    decision/order 掛在 `_record_decision`/`_record_and_notify` 單一漏斗零遺漏。
    鐵則：`emit()` 整段吞例外 + 無事件迴圈時 no-op——可視化壞了交易照常。
  - **Dashboard 卡片即時動畫**：新增 `frontend/src/hooks/useBotActivity.js`
    （播放佇列：資料 100% 真事件、每階段最少顯示 600ms 人眼才看得到）+
    `frontend/src/components/BotActivityStatus.jsx`（抓數據脈衝 / 計算掃光 /
    決策 chip 閃現 / 待機倒數「下輪 Xs」/ 休市靜態待機）。
    **真跑偵測器**：倒數歸零 +15 秒沒等到新一輪 → 卡片亮紅「排程未回應」。
    WS 斷線優雅降級回原輪詢顯示；動畫色全由 NEON 色票推導。
  - **決策即時流**：新增 `GET /bots/decisions/recent`（跨 Bot 最近決策播種）+
    `frontend/src/components/DecisionFeed.jsx`：每輪決策（含「無交叉訊號，觀望」）
    即時滑入 Dashboard，像看機器人的思考日誌。action 標籤/配色映射抽到
    `frontend/src/utils/decisionMeta.js` 三處共用（DecisionsPage 改 import）。
  - **策略視角圖表**：新增 `backend/services/indicator_overlays.py`（策略名+參數 →
    指標序列：MA 雙線/布林三軌/唐奇安通道主圖疊線；MACD/RSI/KD/%R/ROC/ADX 振盪器
    副圖含超買超賣參考線；公式照抄各策略檔、9 策略類零修改，composite 明確回空）+
    `GET /bots/{id}/chart-data`（K 線+指標同一份 df 保證對齊，markers 含 TradeLog
    真實成交 ▲▼ 與可開關的 DecisionLog 觀望點）。`LightweightChart.jsx` 加
    candles/markers/overlays/pane 四個選用 props（v5 `createSeriesMarkers` plugin +
    paneIndex 副圖；不傳 = 舊行為零影響），新增
    `frontend/src/components/BotStrategyChart.jsx` 掛上 Dashboard。
  - 測試：`tests/test_bot_activity.py`（執行緒橋保序/回放/插樁序列/hub 炸掉不影響
    交易，11 例）、`tests/test_indicator_overlays.py`（映射覆蓋全註冊策略/格式/params
    覆寫，6 例）、`tests/test_decision_log.py` 補 recent 端點 1 例；前端
    `useBotActivity.test.jsx`（播放節奏/stale/feed，5 例）+ `BotActivityStatus` /
    `DecisionFeed` / `BotStrategyChart` 元件測試 14 例。後端 466 + 前端 132 全綠。

- **Backlog F 收尾：`ui-ux-pro-max` skill CLI 通電**——從上游開源 repo
  [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)
  （MIT）vendor `scripts/`（search.py/core.py/design_system.py，純 stdlib 免依賴）+
  `data/` 全套 CSV（含 stacks/；排除未引用的開發雜檔 draft.csv/_sync_all.py），附
  `LICENSE-upstream.txt` 署名。SKILL.md 適配註記同步：「CLI 不可用」改為本專案
  Windows 跑法（`venv\Scripts\python.exe ...\search.py "<查詢>" --domain ux`；
  script 自帶 UTF-8 stdout 修正不踩 cp950 坑）。靜態掃描確認無網路/子行程/eval，
  唯一檔案寫入是 `--persist` 明確要求時。backlog F 標 ✅。
- **免費 VM 常駐部署指南**——新增 `docs/guides/free-vm-deployment.md`：Phase 12
  step-05 兩週觀察的常駐機器方案。比較表載明只有 Oracle Cloud Always Free
  Ampere A1（4 OCPU/24GB，永久免費）跑得動 Ollama 8B（AWS 已改 6 個月 credits 制、
  1GB 小機載不動模型）；含開通步驟（搶 A1 容量應對、不開 8000 對公網）、Linux 裝機、
  兩個 Linux 限定坑（APScheduler 吃伺服器本地時間→必設 Asia/Taipei；
  `start_backend.bat` 看門狗改 systemd `Restart=always`）、SSH tunnel 看戰情頁、
  備援方案（小 VM + Groq/Gemini 免費層，`LLM_ALLOW_CLOUD=true` 外送邊界：僅公開
  RSS 素材可外送、策略私有探討留本機）。`docs/README.md` 索引 + backlog D
  checklist 同步補 VM 選項。

- **開機補跑 + 自我修復三層防護（家用電腦非 24/7 也能跑滿每日管線）**——
  - 新增 `backend/services/catchup.py`：後端啟動時檢查「今天該跑而沒跑」的每日 job
    （discovery → auto_validate → 領導股回測 → 心跳 → tracking 對帳，含 collector 預跑），
    時辰已過就立刻補跑；同日去重靠新表 `job_run_log`（`backend/models/job_run_log.py`，
    Alembic 遷移 `2639cd3d3e17`），**只記成功**——失敗不落帳、下次開機自然重試。
    `make_daily_idempotent` 同時包住排程 cron job，補跑與 cron 互不重複執行。
    開關 `CATCHUP_ON_BOOT`（預設開）。
  - APScheduler 加 `coalesce=True` + `misfire_grace_time=3600`：電腦睡眠喚醒後
    一小時內的錯過排程會合併補發一次，不再靜默跳過。
  - `start_backend.bat` 加看門狗迴圈：後端崩潰／斷線退出後等 10 秒自動重啟
    （搭配開機補跑，重啟即接回當日管線，人不在家也能自我修復）。
- **每日領導股回測紀錄**——新增 `backend/services/daily_watch.py`：每天對
  `LEADER_BACKTEST_SYMBOLS`（預設 AAPL/MSFT/NVDA/GOOGL/AMZN/META/TSLA）各跑一輪
  全自動掃描（optimizer，OOS EV 排名），把每檔冠軍存成 `BacktestRun`
  （`preset_id=None`、`is_good=False`，不灌人工策展榜）；單檔失敗不擋其他檔、
  全數失敗拋例外讓補跑機制之後重試。排程 `LEADER_BACKTEST_HOUR`（預設 10 點），
  開關 `LEADER_BACKTEST_ENABLED`、回看 `LEADER_BACKTEST_DAYS`（預設 365）。
- **未上市公司關鍵字監控（SpaceX 等回不了測的公司）**——collector 收料時比對
  `PRIVATE_WATCH_KEYWORDS`（逗號分隔，預設 `SpaceX`），命中標題/摘要的素材寫入
  `raw_strategy_finds.tags`（`watch:<關鍵字>`，新欄位含索引）；通知附命中數，
  `GET /collector/finds?tag=watch:SpaceX` 可過濾查閱。
- 測試：新增 `tests/test_catchup.py`（同日冪等/補跑順序/失敗重試/領導股回測，11 例）、
  `tests/test_collector.py` 補關鍵字監控 3 例；新增 `tests/conftest.py` 測試環境
  全域關閉開機補跑閘（TestClient 起 lifespan 時不真跑背景管線、不互染 monkeypatch）。

- **工作流圖完善（6 張）**——`docs/reference/workflow-diagrams.md`：圖 5 從
  Phase 8–11 擴成 8–12（補 discovery 探勘橋 → auto_validate OOS 閘 → 漏斗報表的
  自動探勘管線，標註預設全關 + 開跑 checklist / 驗收模板連結）；新增圖 6
  「手工新增策略工作流」（點子 → 調參數免寫程式 / strategy-builder skill /
  手動六落地點 → 收尾驗證 → OOS 證明 → 手動 Bot / 自動海選 / 知識庫三用途，
  含「沒加 PARAM_GRIDS 自動化軌看不見」坑註）；對照表補 discovery / auto_validate
  與圖 6 列；`docs/README.md` 索引同步。

- **Phase 12 觀察期開跑前 checklist**——backlog D 項加完整開跑待辦：`.env` 必填
  （Alpaca 金鑰或 `DATA_SOURCE=yfinance`、feeds、兩個 ENABLED 開關、本機 Ollama、
  通知管道）、要常駐的程式（ollama serve、後端 24/7——排程器活在後端行程裡）、
  串接驗通指令（test_connection / overview / 三段手動跑一輪）、起跑儀式（快照 +
  判準凍結）。缺哪項哪段靜默不跑，全列出來防「以為在跑其實沒跑」。

- **Phase 12 step-05：端到端驗收模板**——新增
  `docs/history/phase-12-strategy-discovery/review-e2e.md`（兩週觀察數據表：收料量/
  垃圾率/OOS 通過率〔分母排除 `rejected_by=auto_validate` 操作性放棄〕/curated 增量 +
  optimizer 網格基準對照 + 留/降級/砍三選一判準 + 判準凍結聲明）。兩週觀察需在常駐
  機器全開連跑後回填；backlog D 項與 phase-12 README 狀態同步為「step-01~04 已實作」。

- **Phase 12 step-04：探勘漏斗報表 + 待審提醒（人在迴路收口）**——
  `/company/overview` 加 `discovery_funnel` 區塊（raw 收件匣 + 知識庫各狀態
  group-count + 淘汰率，純讀無遷移）；每日心跳日報加一行
  「探勘漏斗：candidate X｜validated 待審 Y」（查不到以 ? 帶過，心跳永不崩、
  不另開通知管道）；戰情頁加「探勘漏斗」部門卡（四段計數 + validated 待審徽章，
  點擊跳既有 LibraryPage 策展，零新增審核入口；吃 theme 色）。
  測試：後端漏斗聚合 2 案 + 心跳漏斗行 2 案、前端漏斗卡 2 案。

- **Phase 12 step-03：候選自動批次驗證（OOS 閘排程化）**——新增
  `backend/services/auto_validate.py`：每日定時取知識庫 status=candidate 至多
  `AUTO_VALIDATE_BATCH_SIZE` 筆，逐筆呼叫**既有** `evolution.validate_candidate`
  （walk-forward OOS 閘，判準零修改）自然流轉 validated/rejected；不自動晉升 curated。
  失敗隔離：單筆例外不擋整批，失敗計數記 `oos_metrics["auto_validate"]`（免遷移），
  連續 3 次才標 rejected + `rejected_by="auto_validate"`（與 evolution verdict-reject
  可稽核區分；驗證成功時計數自然歸零）。設定 `AUTO_VALIDATE_ENABLED`（預設 false，
  完全不掛排程）/ `AUTO_VALIDATE_BATCH_SIZE` / `AUTO_VALIDATE_HOUR` /
  `AUTO_VALIDATE_SYMBOL`（候選無自帶 symbol，統一基準才可比）；排程掛
  `bot_manager.schedule_auto_validate`。測試 8 案（monkeypatch validate_candidate，
  不回測不連網）。

- **Phase 12 step-02：探勘橋（raw find → LLM 產候選）**——新增
  `backend/services/discovery.py`：每日定時取收件匣 status=new 素材（至多
  `DISCOVERY_BATCH_SIZE` 筆），本機 Ollama 判讀「在講哪種既有策略 + 建議參數」，
  有提案 → 建 `StrategyKnowledge` candidate、find 標 built + 回填 `knowledge_id`；
  不相關/解析失敗 → 標 discarded（原因落新欄 `triage_note`，決策可回查）。
  LLM 連不上 = 整批跳過不標記。設定 `DISCOVERY_ENABLED`（預設 false，完全不掛排程）
  / `DISCOVERY_BATCH_SIZE` / `DISCOVERY_HOUR`；排程掛 `bot_manager.schedule_discovery`。
  Alembic 遷移加 `raw_strategy_finds.knowledge_id`/`triage_note` 兩 nullable 欄。
  守界線：LLM 只提既有策略參數（composite/非數字參數/低信心一律拒）、不生成程式碼、
  不外送雲端（`cloud_blocked` 閘）、不下單。測試 11 案（monkeypatch llm，不連網）。

- **Phase 12 step-01：collector 通電指南 + 邊界測試**——新增
  `docs/guides/collector-feeds-guide.md`（推薦 RSS 來源、robots.txt 檢查步驟、
  `.env` 設定範例、驗收 runbook、「關掉就回全關」說明），`docs/README.md` 索引補列；
  `tests/test_collector.py` 補 3 個邊界測試（CDATA/HTML 摘要、單一 feed 失敗容錯、
  `_parse_feeds` 字串清洗）。collector 本體零修改（藍圖明定只准修 bug）。
  真 feed 連跑 3~7 天觀察為人工驗收，待使用者填 `.env` 執行。

- **Phase 12 藍圖（backlog D Step 1）**——`docs/history/phase-12-strategy-discovery/`：
  README（原目標錨點/現況盤點/架構/5 步路線/防 slop 邊界/Phase DoD）+ step-01~05 契約檔
  （collector 通電/探勘橋 raw→LLM 候選/自動 OOS 驗證/漏斗報表+待審提醒/端到端誠實檢討）。
  程式未開工；預設全關、人在迴路晉升不變、LLM 只提既有策略參數不生成程式碼。

- **壓力測試前端按鈕**——`BacktestResultCard` 加「🎲 壓力測試」鈕，打
  `POST /backtest/stress/{run_id}` 顯示權益 p5/p50/p95、回撤分布、破產機率，
  破產機率 >5% 出警告；`api.js` 加 `stressBacktestRun()`。測試 4 案（mock api）。
- **亮色模式切換（backlog E1）**——`theme.js` 改 `buildTheme(mode)` 雙 palette、
  `index.css` 以 `body[data-mode="light"]` 切整套 CSS 變數，sidebar 加切換鈕、
  選擇存 localStorage；NEON 數據色兩模式共用。
- **排行榜欄位排序（backlog E2）**——`AutoBacktestPanel` 排行榜加 `TableSortLabel`
  + `aria-sort`（EV/EV%/報酬/勝率/回撤/交易皆可排），冠軍列改依「策略+參數」
  判斷不受排序影響。
- **Skeleton 載入態（backlog E3）**——`AccountCard`/`BotList`/`TradesTable` 載入中
  改畫 MUI `<Skeleton>` 佔位，分得清「載入中」與「真的沒資料」；
  `loading` 經 outlet context 傳到各頁。
- **元件測試（backlog E4）**——新增 `AccountCard.test.jsx`（含 Skeleton 態）、
  `BacktestResultCard.test.jsx`；前端 27 檔 111 tests 全綠。

### 變更

- **文件漂移修正（backlog G）**——`CLAUDE.md` 結構樹補齊 Phase 8–11 + backlog H
  的 routers/models/services；`docs/reference/workflow-diagrams.md` 新增
  「圖 5：Phase 8–11 知識庫 → AI 公司軌」（含兩個人工關卡與維運安全軌）。

- **VaR/CVaR 尾部風險指標**——`backend/services/analytics.py` 新增 `var_cvar()`
  （歷史模擬法，純 pandas 分位數、不依賴 quantstats），`extended_metrics()` 回傳
  `var_95_pct` / `cvar_95_pct`，自動流入 `BacktestRun.metrics` JSON（零遷移）。
  前端 `BacktestResultCard` 加 VaR95/CVaR95 chip。測試：`tests/test_analytics.py` 補 4 案。
- **蒙地卡羅壓力測試**——新 `backend/services/monte_carlo.py`：bootstrap 重抽回測
  日報酬產 N 條模擬路徑（不假設常態；捨棄 GBM 與 antithetic variates，理由見 docstring），
  輸出最終權益 p5/p50/p95、回撤分布、破產機率。新端點
  `POST /backtest/stress/{run_id}`（按需計算、不持久化）。測試：`tests/test_monte_carlo.py`（7 案）。
- **RL 可行性評估文件**——`docs/reference/rl-feasibility-assessment.md`：
  DQN/PPO 交易員評估，結論現階段 No-Go（日線資料量餵不飽深度 RL + OOS 鐵則下
  過擬合成本極高），列明四項重啟條件；對照表標明各量化概念在本專案的對應實作。

### 移除

- **Backlog A 收尾：macro overlay 層真資料驗證 → 誠實砍除**——取得 FRED API key 後灌入真
  序列（7 個 series、41,604 筆觀測），以 `scripts/validate_layers.py SPY QQQ AAPL MSFT NVDA`
  跑 walk-forward 層驗證。macro 列 verdict：**worth=False、folds=207（遠超門檻 3）、
  Δ=-101.68**（baseline EV 91.17 → candidate -10.51）——a-priori risk-off 煞車在樣本外
  大幅扣分，依 Phase 7「真資料下無 OOS 加分就砍」鐵律移除：
  - `services/layer_validation.py`：刪 `MacroOverlayStrategy` / `_macro_risk_off` /
    `_build_features` / `validate_macro_layer`，`validate_symbol`/`validate_layers`
    取下 macro 池（也不再需要 DB session）。
  - `scripts/validate_layers.py`：印表迴圈移除 `"macro"`。
  - 刪 `tests/test_macro_layer.py`（整檔測被砍的 overlay 層）。
  - **保留**：FRED 資料層（`macro_data` / `fred_client` / `macro_features` /
    `orderflow_proxy` / `routers/macro.py`）——被否決的是煞車層，不是資料源。
  - 同次驗證的保留層數據：adaptive worth=True（folds=45、Δ=+17.72）、
    meta worth=True（folds=207、Δ=+38.88）；kelly folds=1 < 3 樣本不足不採信。

### 新增

- **維運安全軌 H3 Step 7：tracking error 評估 + 自動降級（「有晉升、沒降級」補完）**——
  - 新增 `services/tracking.py`：`evaluate_tracking` 純函式（Paper 滾動近 10 回合
    均報酬率% vs 機會清單 OOS expectancy_pct × 0.5 折扣；樣本 < 5 回合或無基準
    不對帳不冤殺；OOS≤0 門檻夾 0）；`run_tracking_check` 每日對帳（只在「有新回合」
    的日子計數防重複扣分；違規累計、回升歸零）；連續 3 次違規 → `_demote_bot`
    自動停 Bot（is_active=False + 移除排程）+ DecisionLog(`demoted`) + 通知。
  - **降級邊界（刻意保守）**：只停新決策，**不平倉、不撤券商端保護單**（持倉保護
    不中斷，砍倉由人決定）；單向不自動恢復（重啟走既有 `POST /bots/{id}/start`）；
    與 promotion 狀態機正交（approved_live 一樣會被降級停跑）。
  - `bots` 加 `tracking_breach_count` / `tracking_last_rt_count` / `demoted_at` /
    `demote_reason` 四欄（Alembic `c5d6e7f8a9b0`）；config 五鍵 `TRACKING_*`；
    `bot_manager.schedule_tracking_check`（每日 `TRACKING_CHECK_HOUR` 時，預設 9）。
    `tests/test_tracking.py` 十條全綠；全套件 397 passed。
- **維運安全軌 H3 Step 6：tracking error 資料管**——把「可比的兩個數字」各自接出來：
  - **Paper 側**：`performance.compute_round_trip_returns(trades)` 純函式——
    平均成本法把交易紀錄配成完整回合，回每回合 `profit / entry_cost / return_pct /
    closed_at`（邊界行為與 `compute_bot_stats` 一致：孤兒賣單跳過、部分平倉按比例）。
  - **回測側**：optimizer 結果補 `oos_expectancy_pct`（OOS 期望值佔本金 %）；
    `opportunities` 表加同名欄（Alembic `b4c5d6e7f8a9`），常駐掃描讀寫帶上、
    舊列下次掃描自然回填（不做歷史回填）。
  - **為何用 %**：回測全進全出複利（initial_cash）vs Paper 固定 trade_amount，
    美元 EV 不可直接比，一律 % 歸一化（仍是近似，分母不同——文件誠實標註）。
- **維運安全軌 H2 Step 5：dead-man switch 外側設定 + runbook（純文件/設定）**——
  `.env.example` 補 `BROKER_STOP_ENABLED` / `HEARTBEAT_*` 四鍵與註解；新增
  [`docs/guides/deadman-switch-runbook.md`](docs/guides/deadman-switch-runbook.md)：
  healthchecks.io 免費版設定步驟（period=1h+grace=1h）、警報響起的六步排查順序、
  **每月演練**流程（沒演練過的 dead-man switch 等於沒有）。`docs/README.md` 索引同步加列。
- **維運安全軌 H2 Step 4：每日心跳 + dead-man ping**——一人公司沒有同事盯系統：
  - 新增 `services/heartbeat.py`：`run_daily_heartbeat()` 每日定時發「💓 活著｜持倉 X 檔｜
    啟用 Bot Y 個｜今日決策 N 筆｜權益 $Z」日報（任何查詢失敗以 "?" 帶過照樣發——
    **心跳永不崩**、不依賴開市）；`ping_deadman()` 每 N 分鐘對外側監測服務
    （healthchecks.io）GET 一次，本機掛掉 → ping 停 → 外側主動發警報
    （警報必須在系統外側：本機死了發不出「我死了」的通知）。
  - config 三鍵：`HEARTBEAT_PING_URL`（留空＝dead-man 關）/ `HEARTBEAT_HOUR`（預設 8）/
    `HEARTBEAT_PING_INTERVAL_MIN`（預設 30）。bot_manager 加 `schedule_heartbeat` /
    `schedule_deadman_ping` 兩個排程方法（仿既有體例），main.py lifespan 掛載。
    `tests/test_heartbeat.py` 七條全綠。
- **維運安全軌 H1 Step 3：bot_manager 接上券商端止損託管（核心收尾）**——
  「電腦掛掉止損仍有效」正式生效（`BROKER_STOP_ENABLED` 預設開，關掉=完全退回
  舊版本機輪詢，回歸測試保證）：
  - **進場**：有止損/追蹤止損設定的 Bot 改買整股（買不起 1 股跳過+記審計），
    市價單成交後另掛一張 GTC 保護賣單到券商端（trailing 優先用原生 trailing stop，
    否則 stop 單），訂單 id 落 DB。掛失敗不擋主流程（本機輪詢備援）+ 通知警告。
  - **每輪自癒**（`_ensure_protective_order`）：持倉但保護單失蹤/參數漂移 → 撤舊補掛
    （涵蓋重啟、手動撤單、改風控參數）。best-effort 不阻斷。
  - **本機出場先撤單**（`_cancel_protective_order`）：券商端掛著 sell stop 會保留股數，
    不撤市價賣會被拒；撤不掉=券商端已成交 → 放棄本機賣出防雙重賣。
  - **券商端成交回填**（`_settle_broker_exit`）：空手但 DB 記著保護單 id → 查單，
    已成交就用「實際成交價」補記 TradeLog/DecisionLog + 通知 + 清 peak/id——
    否則績效統計與 tracking error 對帳的資料源會斷鏈。
  - 本機 `check_exit` 輪詢完整保留當備援（belt-and-suspenders）；止盈 v1 不託管
    （OCO 複雜、晚 60 秒不致命）。回測引擎不動：Bot 層 TP/SL 本來就不在回測內，
    盤中觸發/跳空落差由 H3 tracking error 量化。`tests/test_bot_manager.py` 補 8 條。
- **維運安全軌 H1 Step 2：保護單規劃純函式 + `Bot.protective_order_id`**——新增
  `services/protective_orders.py` 三個純函式：`whole_share_qty`（Alpaca stop 單只支援
  整股 → 進場股數 floor 取整，買不起 1 股回 0）、`plan_protective_order`（trailing 優先
  於固定 stop；trail_percent 小數→百分比數字轉換；stop_price round 2 位）、
  `order_matches_plan`（reconcile 容差比對，預設 0.5%）。`bots` 表加
  `protective_order_id`（Alembic `a3b4c5d6e7f8`）：DB 記住券商端保護單 id，
  重啟後不重複掛單、成交後能回填。`tests/test_protective_orders.py` 全分支覆蓋。
- **維運安全軌 H1 Step 1：`alpaca_client` 訂單原語 + 安全閥外推**——為「券商端止損」
  鋪路：實盤雙閘檢查抽成 `_assert_live_allowed()`（市價/停損/追蹤止損所有 `submit_*`
  共用同一道閘，新增單型不可繞過）；新增 `submit_stop_order`（GTC stop 單，託管券商端、
  本機斷電仍有效）、`submit_trailing_stop_order`（原生 trailing stop，券商端自追盤中
  最高價）、`cancel_order`（撤不掉回 False 不丟例外——代表券商端已成交）、`get_order`、
  `get_open_orders`（reconcile 用，失敗回 `[]` 優雅降級）。`tests/test_safety_valve.py`
  補三條：雙閘對三種單型一致擋/放、cancel 已成交回 False。

### 修正

- **`requirements.txt` 重複釘版擋住安裝**——`psycopg2-binary` 同檔出現 `==2.9.12`
  與 `==2.9.10` 兩行（後者為 29de1e5 誤加孤行），`pip install -r` 直接
  ResolutionImpossible。刪除孤行、保留有註解的 2.9.12。
- **文件對齊（純文件、零程式）**——`docs/remaining-work-backlog.md` 補標 Backlog B/C
  已完成（commit `13ef4bb`：`GET /positions`+持倉卡、`test_run_dry_run` 修復），總表與
  建議順序同步更新；新增「**H. 維運安全軌（真錢前必備）**」項（券商端止損 / 心跳+dead-man
  switch / tracking error 對帳+自動降級，三鏈七 step 寫到可餵 AI 的契約詳細度）。
  另修 `docs/reference/one-person-company-gap-analysis.md` 第五部分與 CHANGELOG 不符的
  描述：被砍的是 macro（Δ=-101.68），adaptive 實為 worth=True（Δ=+17.72）但預設關未上線、
  kelly 樣本不足擱置，上線的是 meta-labeling。
- **`database.py` 換 PostgreSQL 會崩**——`connect_args={"check_same_thread": False}` 是
  SQLite 專屬參數，硬塞給 Postgres 報 `invalid connection option "check_same_thread"`。
  改成依 `DATABASE_URL` 方言判斷只在 SQLite 才加，兌現「換 PostgreSQL 只改 .env」承諾。
- **本機 `.env` 編碼修復（不進 git，僅記錄）**——檔案曾被以錯誤編碼存檔，中文註解全變
  亂碼且數個 `KEY=VALUE` 被黏進註解行（dotenv 讀不到）。已依 `.env.example` 範本重建
  （UTF-8 無 BOM），27 個鍵值經雜湊比對零遺失；亂碼版備份於 `.env.garbled.bak`。

### 新增

- **一人公司缺口分析文件（純文件、零程式變更）**——把使用者「一人公司」願景（自動抓策略/
  抓總經/回測/人審核/Paper→真錢/全自動進出場+決策記錄）對照專案現況做缺口盤點，存
  [`docs/reference/one-person-company-gap-analysis.md`](docs/reference/one-person-company-gap-analysis.md)：
  願景對照表（管線已蓋八成）+ 前置進料缺口 A~E（蒐集員沒料吃/策略文字→程式人工斷層/
  watchlist 手動/macro 定位/政治員鏡像頻道）+ 上線後維運缺口 1~9（**止損掛本機輪詢最危險**、
  無心跳監控、有晉升沒降級、無 tracking error 對帳、部位 reconcile、SQLite 無備份、
  組合相關性、PDT/稅務、資料品質閘）+ 建議優先序（真錢前必備：券商端止損→心跳→自動降級）+
  二次盤點補充（F 事件日曆沒接〔經查 `event_risk` 只吃情緒分數、無真實財報/FOMC 日曆源〕、
  G 倖存者偏差、H 日線止損落差、與大戶比拚的誠實定位）。`docs/README.md` 索引同步加列。
- **Backlog B：`GET /positions` 端點 + 前端持倉卡（填掉最大缺口）**——原本只有
  `alpaca_client.get_position(symbol)`（單檔），前端看不到手上部位與浮動損益：
  - `services/alpaca_client.py`：新增 `list_positions()`（包 `trading.get_all_positions()`，
    連線/金鑰失敗回 `[]`，優雅降級）。
  - 新增 `routers/positions.py`（唯讀 `GET /positions`）：把每個 Position 映成
    `symbol/qty/avg_entry_price/current_price/market_value/unrealized_pl/unrealized_plpc`
    （數字轉 float），無金鑰/失敗回空清單、不丟 500；掛進 `main.py`。
  - 前端 `api.getPositions()` + `components/PositionsCard.jsx`（自含資料、掛上 Dashboard，
    損益用 `signedMoney`/`signOf` 帶 +/- 號 + `NEON` 紅綠雙重編碼，不寫死 hex）。
  - 測試：`tests/test_positions.py`（2 測，monkeypatch 假持倉，不連網）；
    `PositionsCard.test.jsx`（3 測：有持倉/無持倉/API 失敗降級）。
- **Backlog A：macro 層真資料驗證 runbook（記錄待辦、不改程式）**——Item A 唯一阻塞是缺免費
  FRED API key（須 stlouisfed.org 帳號）；無 key 時 macro 欄全 NaN、驗證印 `worth=False`，但
  **那不算數**（須真資料下仍 `worth=False` 才誠實砍）。新增
  [`docs/guides/macro-layer-validation-runbook.md`](docs/guides/macro-layer-validation-runbook.md)：
  申請 key → `POST /macro/refresh` → `scripts/validate_layers.py` → 判 verdict 後留/砍的機械式步驟單
  （程式已全就位，本次只記錄；真資料驗證 + 留/砍決策待 key 與標的籃子敲定後執行）。`docs/README.md` 索引同步加列。
- **Phase 11 step-04：回測引擎吃環境 `features` + 接線 bar_cache**——把 step-02/03 的快取與環境
  特徵真正接進回測管線（前三步只交付模組，本步「接線」）：
  - `services/backtest_engine.py`：`_run_on_df` / `run_backtest` 各加**選用** `features` 參數。
    `features` 與價格 df 等長、位置對齊，**只併進「訊號層」**（`generate_signal` 讀得到 macro/買賣壓
    欄）；`features=None`（預設）→ 行為**逐位元組不變**（舊策略/舊呼叫端零改動）。
  - **成交鐵則不動**：`_simulate_from_signals` 仍只收 price-only df，環境特徵**不得碰成交價**
    （成交永遠次根開盤含成本，守「回測=實盤」核心）。
  - **多年回測走快取**：`run_backtest` / `optimizer` / `screener` 的 `market_data.get_bars`
    改呼 `bar_cache.get_bars_cached`（簽章相容、純效能替換、嚴格 ⊆ 請求區間不洩漏未來），
    討回 step-02 遞延的接線。`requirements.txt` 的 `pyarrow` 補裝（parquet 引擎，快取落盤需要）。
  - `tests/test_backtest.py`：+3 測（features 到得了策略、features 不碰成交價、舊策略帶/不帶
    features 結果完全相同）；`tests/test_oos.py` 改 patch 新資料 seam（`bar_cache.get_bars_cached`）。
- **Phase 11 step-05：macro 層 OOS 加分驗證（沒加分就誠實砍）**——用 walk-forward 樣本外比
  「純價量 baseline」vs「+環境覆蓋 candidate」，證明 macro 層有沒有真加分：
  - `services/layer_validation.py`：新增 `MacroOverlayStrategy`（**環境風險煞車**：risk-off 時 BUY→HOLD，
    只煞車不猜方向）、`_macro_risk_off`（**a-priori 固定可解釋門檻**，不在任何資料上 fit：VIX>30／
    殖利率倒掛／失業上升／賣壓>買壓；NaN 一律不煞車）、`_build_features`（macro+orderflow 組欄）、
    `validate_macro_layer(df, db)`；接進 `validate_symbol`/`validate_layers`（開 DB session 取 FRED）。
  - `scripts/validate_layers.py`：印表加 `macro` 一列（`worth | folds | improvement`）。
  - `tests/test_macro_layer.py`（6 測，純合成、不碰外部 API）：OOS 殺手（in-sample 漂亮、OOS 崩 →
    判不值得）、覆蓋煞車邏輯、NaN 不煞車（優雅降級）、四門檻、端到端 verdict 結構、`_build_features` 對齊。
  - **誠實結論（首跑 SPY，無 FRED 資料）**：macro-overlay 層 **`worth=False`（36 folds，Δ=−132.6）**——
    沒填 `FRED_API_KEY` 時 macro 欄全 NaN、煞車只靠 orderflow `pressure_ratio<0.5`，在每根下跌後
    過度抑制進場 → 拖垮 EV。**目前判該砍/待真資料驗證**：要真評估 macro 價值，須先填 `FRED_API_KEY`
    + `POST /macro/refresh` 灌入序列再跑。這正是 step-05 的本職——殺掉沒在 OOS 加分的層，不美化績效。
- **Phase 11 step-02：多年 OHLCV 本機快取（少打外部 API）**——讓「整個歷史」回測（如 `days=3650`）
  跑得起來、又不每次都向 Alpaca/yfinance 重抓。新增 `services/bar_cache.py`，**包在
  `market_data.get_bars` 外層**（不改其簽章、不繞過它，維持單一抓取路徑）：
  - 缺的區間才補抓、抓回來寫進本機 **parquet** 快取（`{BAR_CACHE_DIR}/{source}/{symbol}.parquet`，
    按 source 分開存不混存）；已涵蓋的命中快取、**0 次 API**。
  - **關鍵設計取捨**：freshness 看 sidecar `meta.json` 記的「已涵蓋的請求區間」，**不看最後一根 bar
    日期**——否則週末/假日/停牌時最後一根恆早於 today，會被誤判成缺口而無限重抓。
  - **不可成偷看後門**：回傳區間嚴格 ⊆ 請求區間（不洩漏請求結束日之後的列）。`today` 可注入 → 缺口
    邏輯有確定性（仿 step-01 的 `as_of` 縫）。
  - `config.py`：`BAR_CACHE_DIR`（預設 `data/cache/bars/`）；`.gitignore`：加 `data/cache/`（不進版控）；
    `requirements.txt`：加 `pyarrow`（parquet 引擎）。
  - `tests/test_bar_cache.py`：5 個純單元測試（合成 K 線 + monkeypatch `get_bars`，不連網），驗
    首抓 1 次/二抓 0 次/頭尾缺口只補對應段/回傳嚴格在請求區間內。
  - ⚠️ 接線回測/optimizer/screener 改吃快取 = step-04 的事，本步只交付可用模組 + 測試。
- **Phase 11 step-03：環境特徵 + 買賣壓代理（給回測當輸入特徵）**——把總經序列與「買賣壓」對齊成
  「每根 K 棒一列」的特徵欄。新增兩個**純函式**模組：
  - `services/macro_features.py`：`attach_macro_features(price_df, db)` 對每根 bar 的日期，各序列取
    **`released_at <= bar_date` 的最後一筆** forward-fill，加 6 欄（`fed_funds_level`/`fed_funds_3m_chg`/
    `unemployment_trend`/`cpi_yoy`/`yield_curve`/`vix_level`）。**as-of 一律用 `released_at`**（嚴禁
    `period_date` 偷看未公布未來，守門延續 step-01）；沒總經資料 → 各欄 NaN，不崩。重用
    `macro_data.get_macro_series`。
  - `services/orderflow_proxy.py`：`compute_orderflow(price_df)` 用 **tick 規則**（漲跌方向 × 總量）
    近似買/賣量，加 4 欄（`buy_vol_proxy`/`sell_vol_proxy`/`net_pressure`/`pressure_ratio`）。守恆等式
    `buy+sell==volume`（平盤/首根對半、零量 ratio 給中性 0.5）。**誠實標註：tick 代理、非真實逐筆
    order flow**（真值需付費源 Polygon/Databento，列範圍外，不包裝成真 order flow 行銷）。
  - 兩者皆**無未來函數**（第 i 根只看 `df.iloc[:i+1]`）。`tests/test_orderflow.py`（6 測）+
    `tests/test_macro_features.py`（6 測）：純函式 + 記憶體 SQLite，驗對齊不洩漏/恆等式/方向/無未來函數。
- **Phase 11 step-01：總經/環境資料地基（FRED 接入 + 本機快取 + point-in-time）**——補上專案最大缺口
  「環境資料的大腦」（先前 `grep` 整個 `backend/` 找不到 FRED/非農/利率/CPI）。新增：
  - `services/fred_client.py`：薄 FRED client（聖路易聯準會，免費 API）。仿 `llm.py` 優雅降級——
    沒設 `FRED_API_KEY` 或連不上 → 回 `None`、靜默跳過，不崩、不阻斷其他功能（不另設 `MACRO_ENABLED` 旗標）。
  - `services/macro_data.py`：統一介面（仿 `market_data`）。本機快取 + **point-in-time 守門**——
    每筆存 `period_date`（資料期間）與 `released_at = period + 發布落差`；回測讀取給 `as_of`
    時只回 `released_at <= as_of` 的值，**杜絕偷看尚未公布的數據**（「回測=實盤」鐵則延伸）。
  - `models/macro_series.py`（`macro_observations` 表，唯一鍵 series+period）+ Alembic 遷移。
  - `routers/macro.py`：`GET /macro/series`（point-in-time 唯讀）、`GET /macro/series-list`、`POST /macro/refresh`。
  - `tests/test_macro.py`：6 個純單元測試（記憶體 SQLite + monkeypatch，不連網），含**防洩漏**
    （公布前看不到）與**無 key 優雅降級**。
  - `config.py` / `.env.example`：`FRED_API_KEY` / `MACRO_SERIES` / `MACRO_DEFAULT_LAG_DAYS`。
  - 藍圖 `docs/phase-11-macro-data/README.md`（含 step-01~05 契約）。

### 變更

- **docs/ 資料夾依用途重整（零刪除、純搬移 + 改連結）**——`docs/` 根目錄原積到 21 項
  （8 個完成過的 phase/redesign 夾 + 13 個散落 .md），打開找不到當下要的檔。重整成語意四夾、
  根目錄降到 ~7 項；所有檔用 `git mv` 保留歷史血緣，**一個都沒刪**（供日後歷史歷程報告查閱）：
  - `docs/history/`：phase-6~11 + redesign 的開發藍圖（完成過的契約文件，歸檔備查）。
  - `docs/guides/`：操作教學（`setup.md`〔原 root `SETUP.md` 移入〕/`使用說明.md`/`how-to-add-strategy.md`/
    `setup-postgres-sync.md`/`phase4-paper-checklist.md`/`skill-guidelines.md`）。
  - `docs/reference/`：概念規格（`workflow-diagrams.md`/`roadmap-strategy-workbench.md`/
    `human-vs-ai-operation.md`/`financial-services-reference.md`/`strategies/`）。
  - `docs/ux/`：`ux-workflow.md`/`ux-audit-2026-06.md`。根目錄只留 `ai-implementation-guardrails.md`
    與 `remaining-work-backlog.md` 兩份最常讀。
  - 新增 **`docs/README.md` 文件地圖**（四大分組 + 各檔用途，打開 docs 先看這頁）。
  - 同步修好受影響連結：docs 內 121 條相對連結、`CLAUDE.md`/`AGENTS.md`/`README.md` 的結構樹與路徑、
    `.claude/skills/`（ui-ux-pro-max、strategy-builder）的 doc 路徑、`CHANGELOG` 內 2 條已搬檔的 markdown 連結。
    全 docs 相對連結經程式驗證 **0 殘斷**。CHANGELOG 歷史條目的純文字路徑維持原樣（歷史紀錄不竄改）。
  - **新增 `CLAUDE.md`「檔案放置規範」章節**：把「新增檔案放哪」寫成 Claude 與人都遵守的對照表
    （文件分 history/guides/reference/ux 四夾 + root 只留兩份；程式分 backend 各層／tests 扁平／scripts），
    並要求新增文件後補 `docs/README.md` 索引、搬檔用 `git mv`。防止日後又把檔亂塞回 docs/ 根。

### 修正

- **Backlog C：修 `tests/test_automation.py::test_run_dry_run` 的 pre-existing 失敗**（清掉「353 過/1 失敗」
  那 1 個，全測達 0 失敗）。**根因不是 automation bug，是測試對 dev DB 有隱性依賴**：`run_auto_deploy`
  會 `db.query(Bot).all()` 取 `existing_symbols` 去重，而 dev DB 剛好有同名 `AAPL` Bot → 候選被去重剔除 →
  `planned=[]`。修法（沿用 `test_promotion._isolated_client` 模式）：注入臨時空 SQLite（`dependency_overrides[get_db]`，
  Bot 表空）+ stub `get_account` 丟例外（跳過資金閘，不依賴真帳戶餘額），讓結果只取決於 stub 的海選/門檻、完全確定性。

- **修正 PostgreSQL 全新資料庫遷移失敗**：將 `bots.adaptive` migration 的布林預設值從 SQLite 風格
  `0` 改為跨資料庫相容的 `sa.false()`，避免 PostgreSQL 出現 `BOOLEAN DEFAULT 0` 型別錯誤。

- **修復後端啟動報錯 `no such column: bots.promotion_status`（DB schema 漂移）**——本機 SQLite 的
  `alembic_version` 停在 `f6a7b8c9d0e1`，但實際 DB 已被 `create_all` 建出後續所有「表」
  （automation_config / opportunities / factor_snapshots / raw_strategy_finds / political_events），
  唯獨後續遷移對「既有表」的 `ALTER add_column` 從沒跑過，導致 `bots` 缺 `promotion_status` /
  `promotion_proposed_at` / `promotion_reason` 三欄、查詢即炸。因 `upgrade head` 會撞「表已存在」無法直跑，
  改為**對帳補欄**：冪等補上缺的 3 欄（比照遷移 `c9d0e1f2a3b4`，`promotion_status` 以 `DEFAULT 'paper'` 回填）
  後 `alembic stamp head` 讓版本與實況一致。已驗 `db.query(Bot).all()` 可正常讀 `promotion_status`。
  （`scan_interval_min` 經查已存在，未重複加。）
- **修復 `.bat` 一鍵腳本在 UTF-8 下「command 無法辨識」**——`setup.bat` / `start_backend.bat` /
  `start_frontend.bat` / `background.bat` 含中文但存成 **UTF-8 無 BOM**；搭配 `chcp 65001` 時 cmd.exe 有
  已知的檔案讀取位移 bug（多位元組字後偏移算錯，把後面行攪成亂碼指令 → not recognized）。改存成
  **UTF-8 with BOM**（Windows 11 cmd 認 BOM 後位移正確），內容與 CRLF 不動。已用同模式煙霧測試確認中文正常顯示、無報錯。

### 待辦（後續 / TODO）

> **完整詳細 backlog（餵 AI 實作用）**：[`docs/remaining-work-backlog.md`](docs/remaining-work-backlog.md)——
> A~G 七項各含現況/檔案路徑/函式簽章/step/DoD/測試指令，依價值排序（建議序 B→C→A→其餘）。下方為摘要。

- **Phase 11 macro 層待真資料驗證**（step-05 收尾）：首跑 SPY 判 `worth=False`（無 FRED 資料、
  煞車只靠 orderflow 過度抑制進場）。要真評估 macro 價值，須先填 `FRED_API_KEY` →
  `POST /macro/refresh` 灌入序列 → 重跑 `venv\Scripts\python.exe scripts\validate_layers.py SPY`。
  仍 `worth=False` 則如實砍掉 `MacroOverlayStrategy`（不硬留無加分的層，沿用 Phase 7 紀律）。

> 前端 UX 兩批未做、留待後續的項目（依價值排序）：

- **持倉 / 未實現損益視圖**（價值最高的缺口）：後端目前**無 `/positions` 端點**，
  需先加端點再做前端持倉卡（現金/購買力之外，看得到手上部位與浮動損益）。
- **亮色模式切換**：目前深色單一主題，要加 light/dark 雙主題需整體再過一遍對比。
- **排行榜欄位排序**：`AutoBacktestPanel` 排行榜目前固定依 EV，可比照 `TradesTable` 加 `TableSortLabel`。
- **骨架屏（Skeleton）全面化**：`AccountCard`/`BotList`/`TradesTable` 載入時可用 Skeleton 取代空白/純文字。
- **元件測試持續補**：目前有 `ConfirmDialog`/`BotList`/`EditBotDialog` + 純函式工具，其餘元件待補。
- **skill CLI**：`.claude/skills/ui-ux-pro-max` 未隨附 `search.py`/CSV（規則文字已夠用，CLI 查詢不可跑）。

### 移除

- **清理：刪除被取代的舊藍圖 `docs/blueprint-ai-terminal.md`**——它是「AI 終端機改版」的舊單檔藍圖，
  已被 `docs/redesign/`（深化拆成 4 階段、且全部完成）取代、無任何連結指向、狀態仍停在「規劃中 Draft」，
  刪除以減少混淆。另順手清掉可再生的本機垃圾（`__pycache__` / `.pytest_cache` / 測試殘留暫存夾
  `tests/_tmp_expl_*`，皆 git-ignored、不影響版控）。

### 變更

- **README.md 同步 Phase 10 落地實情（文件，無程式變更）**——修正自打架：進度表已標
  `Phase 10 ✅ 完成（step-01~07）`，但「後續 / 未竟」段第一條仍寫「**尚未動程式**」（前一次
  README 對齊只補到 Phase 8/9，Phase 10 之後才落地、文件沒跟上）。本次：
  - **移除過期句**，改寫成 **Phase 10 通電前置**（政治員需鏡像頻道且 `POLITICAL_ENABLED` 預設關／
    蒐集員需設 `COLLECTOR_RSS_FEEDS`／上真錢仍卡董事會核准 + 實盤雙閘）——機制已落地、只待接真資料來源。
  - **新增「Phase 10 已落地」描述塊**（補平 Phase 5~9 + redesign 格式）：戰情頁 + 常駐機會掃描 /
    因子表 + CSV / 市場蒐集員（只收料）/ 政治專討員（只當煞車、不猜方向）/ 董事會核准（人在迴路上真錢）/
    開機常駐化。
  - **主要 API 清單**補 Phase 10 端點（`/factors`〔+`export.csv`〕、`/collector/finds`、
    `/political/events`〔+`/risk`〕、`/promotions`〔+`propose`/`approve`/`reject`〕，已對程式核實路徑）。
  - **專案結構**補 Phase 10 的 routers / models / pages 與 `political_watcher` 獨立常駐 runner。
  - CLAUDE.md 進度表已是 ✅完成、無矛盾，本次未動。
- **前端 UX 強化（套用 UI/UX Pro Max skill，無障礙 / 回饋 / 表單 / 表格）**——對齊 skill 規則：
  - **無障礙**：圖示鈕補 `aria-label`（`BotList`）；損益/EV 改帶 `+/-` 號（`utils/number.js` 新增
    `signOf`/`signedMoney`/`money`，套到 `BotList`/`BacktestPanel`/`AutoBacktestPanel`/`RecommendationsPanel`）；
    `index.css` 加 `prefers-reduced-motion` 全域弱化動畫。
  - **回饋**：成功訊息改 `Snackbar`（4s 自動消失、`role="status"` 不偷焦點，`SidebarLayout`），錯誤維持常駐。
  - **危險動作**：停 Bot 加二次確認（`App.jsx` + `ConfirmDialog`）；實盤模式 AI 一鍵部署加二次確認（`RecommendationsPanel`）。
  - **表單**：`EditBotDialog`/`BacktestPanel` 加 `required` + 即時驗證 + `helperText`，無效時停用送出。
  - **表格**：`TradesTable` 欄位可排序（`TableSortLabel`+`aria-sort`）、`stickyHeader`、數字右對齊 + `tabular-nums`。
  - **一致性**：`constants.js` 新增 `strategyLabel()` 單一來源（`RecommendationsPanel`/`AutoBacktestPanel` 改用）；
    AI 推薦 EV 上色 + 防 `NaN`。
  - 裝 skill 進 `.claude/skills/ui-ux-pro-max`；新增 `docs/ux-audit-2026-06.md` + `docs/ux-workflow.md`；
    新增 `BotList`/`EditBotDialog` 元件測試。

- **README.md / CLAUDE.md 對齊實情（文件同步，無程式變更）**——比對發現 `README.md` 嚴重過期：
  - 進度表把已完成的 **Phase 8（step-01~06）/ Phase 9（step-01~08）仍標「📋 構想藍圖」**，改為 ✅ 完成；
    Phase 5 標示為「核心已落地（剩選配）」。
  - 新增 Phase 8 / Phase 9 / **改版子軌（redesign）** 三段「已落地」描述，並把「規劃中」段改寫成
    「後續/未竟」非阻塞 backlog（Phase 5 選配、Phase 7 層加分續調、自動化規則改 DB 表、實盤上線必讀）。
  - 移除已刪元件的殘留引用（`StrategyWorkbench`/`CreateBotForm`/`TradingViewChart`）；前端結構改寫為
    「左側 sidebar + react-router 多頁 + `pages/` + `LightweightChart`」；技術棧補 `lightweight-charts`。
  - 主要 API 清單補 `/ai-recommendations`、`/automation`(+`/run`)、`/bars`、`/quotes`、`/explorations`、
    `/knowledge`(+ranking/validate/promote/reject)。
  - `CLAUDE.md` 專案結構前端區塊同步修正（死引用換成現存檔名、補 `pages/` 與新元件）。

### 新增

- **Phase 10 step-05：政治專討員（Discord 事件流，只當煞車）**——補「川普推文 → 風險」前台：
  Discord runner 偵測政治貼文 → 本機 Ollama 判讀 → 落表（`political_events`）→ 分數接既有風險煞車。
  **★ 定位是「煞車（降風險 / 不開新倉），不是油門」**：「貼文 → 漲跌」最易過擬合、無乾淨
  point-in-time 對齊資料可誠實回測，所以只在重大負面時縮部位 / 不開新倉，**不猜方向、不放大部位**。
  - 後端：`models/political_event.py`、`services/political.py`（純函式 `summarize_post` /
    `frequency_features`〔發文頻率特徵〕/ `judge_post`〔本機 Ollama，守外送閘〕/ `event_to_sentiment` /
    `latest_event_sentiment`〔太舊退場〕 + ★ bridge `political_size_factor`〔接既有 `event_risk`〕）、
    `routers/political.py`（`GET /political/events` + `GET /political/risk`）。
  - bridge **預設關**（`POLITICAL_ENABLED=false`）：未啟用一律放行 `size_factor=1.0`，完全不影響現行下單；
    啟用才把最近政治情緒交給既有 `event_risk.assess_event_risk` 決定縮多少 / 要不要不開新倉。
  - runner：`bots/political_watcher.py`（獨立常駐，`python -m backend.bots.political_watcher`；
    discord 套件延遲 import；沒設 `POLITICAL_DISCORD_TOKEN` 印指引後結束）。**來源前提**：Discord bot
    只能讀「它所在的頻道」，需先有「同步川普貼文的鏡像頻道」才有東西可讀。
  - 前端：新頁 `pages/PoliticalPage.jsx`（風險煞車現況橫幅 + 事件表）+ sidebar 導覽「政治專討員」。
  - 依賴：`discord.py==2.7.1`（只給獨立 runner 用，FastAPI 後端不依賴）。
  - DB：Alembic `f2a3b4c5d6e7_add_political_events`。
  - 測試：`tests/test_political.py`（13：純函式 / judge / bridge 開關 / runner glue / API）、
    `PoliticalPage.test.jsx`（3）；全後端 322 passed、全前端 89 passed。

- **Phase 10 step-04：市場蒐集員（爬蟲收料，靈感收件匣）**——補「上網找策略」前台：定時從 RSS / 部落格
  收「策略描述文字」進收件匣（`raw_strategy_finds`），當人 / `strategy-builder` 寫成策略的素材。
  **只收料、不驗證、不部署**——收回來一律走既有 OOS 閘 + 人工核准才可能上線。
  - 後端：`models/raw_strategy_find.py`（status 流轉 new→triaged→built/discarded）、
    `services/collector.py`（純函式 `parse_rss`〔RSS2.0+Atom〕/ `parse_html_listing`〔bs4〕/ `dedup_rows` /
    `upsert_finds`〔冪等、保留 status〕 + best-effort `fetch_url` + 排程入口 `run_collector_scan`）、
    `routers/collector.py`（`GET /collector/finds` + `PATCH /collector/finds/{id}` 改狀態）。
  - 排程：`bot_manager.schedule_collector_scan`（沿用 step-02 APScheduler 機制）；`main.py` 啟動時掛上，
    `COLLECTOR_INTERVAL_MIN` 預設 0（關）、沒設 `COLLECTOR_RSS_FEEDS` 也會跳過，不無故打外站。
  - 前端：新頁 `pages/CollectorPage.jsx`（收件匣表 + 狀態策展鈕）+ sidebar 導覽「市場蒐集員」。
  - 依賴：`beautifulsoup4==4.15.0`（純 Python、Windows 安全，靜態頁解析用）。
  - DB：Alembic `e1f2a3b4c5d6_add_raw_strategy_finds`。
  - 測試：`tests/test_collector.py`（10 項：解析/去重/upsert 冪等/掃描去抖/API 往返）、
    `CollectorPage.test.jsx`（2 項）。**股價不爬**（用既有 `market_data`/yfinance）。守 robots/節流/User-Agent。

- **Phase 10 step-07：開機常駐化（Windows 自啟，純 ops 零交易邏輯改動）**——補「電腦開機就一直跑」：
  新增 `scripts\register_autostart.bat`（用 `schtasks /SC ONLOGON` 註冊「登入時自動啟動」工作
  `AlbeeStockBackend`，觸發既有根目錄 `start_backend.bat`）+ `scripts\unregister_autostart.bat`
  （移除工作）+ 運維手冊 `docs/phase-10-ai-company/ops-autostart.md`（安裝/驗收 checklist/常見操作/
  排查/界線）。後端起來後由既有 `main.py` `lifespan` 自動接回啟用中 Bot + 盤前自動部署 cron +
  常駐機會掃描（step-02），**無程式碼變更**。提醒：常駐跑的仍是 Paper，真錢仍受實盤雙閘 +
  董事會核准（step-06）把關；不做系統服務/NSSM、不在開機腳本塞交易邏輯。

- **Phase 10 step-03：因子數值表 + 報表（蒐集員主管）**——把市場狀態因子（regime_features 的
  7 個因子 + regime 標籤）落成**可查、可匯出**的數值表 + 一頁報表。**因子是觀測佐證、給人和
  回測看的報表，不是新的交易訊號**（不自動下單）。
  - 新增 `factor_snapshots` 表（`backend/models/factor_snapshot.py`：symbol/as_of + 7 因子欄
    〔volume_ratio/return_5d/return_20d/volatility_20d/trend_strength/atr_pct/range_position〕
    + regime），走 **Alembic 遷移** `d0e1f2a3b4c5`。新增 `settings.FACTOR_RETENTION_DAYS`
    （預設 90，0=不修剪）控保留天數，避免 DB 膨脹。
  - `services/opportunity_scan.py` 加純函式 `features_to_snapshot_row`（映射 7 因子鍵、缺值帶
    None，不重算第二套公式）與 `collect_factor_snapshots`（對 watchlist 各檔走**同一條正規資料
    路徑** `market_data.get_bars(..., source=settings.DATA_SOURCE)` →
    `regime_features.compute_features` → `regime.classify_regime` → 落一筆，並依保留天數修剪）；
    `run_opportunity_scan` 在 upsert 機會後**順手呼叫**（best-effort 包 try，因子落表失敗不影響
    機會收集與提醒）。無 look-ahead（compute_features 只用截至最後一根的資料）。
  - 新增 `backend/routers/factors.py`：唯讀 `GET /factors`（依 as_of 由新到舊，可選 symbol/limit）
    與 **本專案第一個 CSV 端點** `GET /factors/export.csv`（`StreamingResponse` + `csv`，表頭與
    欄位順序固定）。`main.py` 掛上 `factors.router`。
  - 前端新增 `pages/FactorsPage.jsx`（沿用既有表格頁風格：symbol 篩選 + 表格 + 匯出鈕，
    regime 中文標籤），sidebar 加「因子報表」+ 路由；`api.js` 加 `getFactors` / `factorsCsvUrl`。
    顏色吃 `theme`/`NEON`、不寫死 hex。
  - 取捨說明：因 `screener` 內部抓完 bars 即丟、不外傳，因子落表是**同一條正規資料路徑的獨立一抓**
    （非 screener 那次）；watchlist 小、日線、成本低，故未為「抓一次共用」而改動 screener（避免
    範圍蔓延）。保留天數用 `config` 設定而非 `automation_config` DB 欄位（少一張表/前端欄位，夠用）。
    測試：`tests/test_factor_snapshot.py`（純函式映射/落表值＝直接算的值/保留天數修剪/端點往返/CSV
    表頭）、前端 `FactorsPage.test.jsx`；並更新 `tests/test_opportunity.py` 讓掃描測試離線餵假 K 線。

- **Phase 10 step-06：董事會核准頁（Bot 進真錢，人在迴路）**——補「老闆一頁核准 + AI 主動提醒」：
  系統偵測「某 Bot Paper 表現達標、建議上真錢」→ 提議 → 使用者一頁**核准 / 退回**。
  - `bots` 表加三欄（`backend/models/bot.py`：`promotion_status`〔paper/proposed_live/
    approved_live/rejected〕/`promotion_proposed_at`/`promotion_reason`），走 **Alembic 遷移**
    `c9d0e1f2a3b4`（`batch_alter_table` 加欄、既有列 server_default 回填 `paper`）。
  - 新增 `backend/routers/promotion.py`：純函式 `evaluate_promotion_readiness`（三道門檻：
    OOS EV ≥ `ev_threshold`、Paper 勝率 ≥ `winrate_threshold`、完整買賣 ≥ 3 才達標，好單測）；
    端點 `GET /promotions`（預設待核清單）、`POST /promotions/{id}/propose`（達標才提議、附證據、
    主動 `notify` 一次、冪等去抖；未達標回 409）、`/approve`、`/reject`（附理由）。達標證據
    **重用既有** `performance.compute_bot_stats`（Paper 實績）+ 機會清單最佳 OOS EV，不重算。
  - `presets._build_reminders` 加第三種提醒 `propose_live_candidate`（Paper Bot 達標但未提議 →
    浮上橫幅），判斷一律走 promotion 的純函式。`main.py` 掛上 `promotion.router`。
  - 前端新增 `pages/PromotionPage.jsx`（比照 `EvolutionPage` 的 tab + 卡片 + 動作鈕：候選 Paper→
    提議、待核→核准/退回），sidebar 加「董事會核准」項 + 路由；`api.js` 加四支呼叫。顏色吃
    `theme`/`NEON`、不寫死 hex。
  - ★**安全紅線**：UI「核准」只是**多一道人工閘**，`approved_live` 只是「人已同意」旗標，
    **不放行真錢**——真錢仍須 `ALPACA_BASE_URL` 實盤 + `ALLOW_LIVE_TRADING=true` 雙閘，由
    `alpaca_client.submit_market_order` 把關（兩者 AND）。本步**完全不碰那道安全閥、不改
    `alpaca_client`、不改 `.env` 語意、不做自動晉升**（一律人工點按）。理由存 `promotion_reason`
    欄位供追溯。測試：`tests/test_promotion.py`（純函式三門檻/狀態流轉冪等/未達標 409/退回理由/
    提醒命中）、前端 `PromotionPage.test.jsx`（候選提議 + 待核核准）。

- **Phase 10 step-02：常駐探勘 + 機會清單持久化（好策略不漏掉）**——把海選從「手動觸發」
  補成**盤中週期自動跑 + 排名候選存 DB**，名額滿時不再把第 6~N 名直接丟掉、關掉 app 也留著。
  - 新增 `opportunities` 表（`backend/models/opportunity.py`：symbol/strategy_key/params/
    `oos_expected_value`/`oos_win_rate_pct`/sentiment/scanned_at/status）；`automation_config`
    加 `scan_interval_min` 欄位（盤中探勘間隔，分；0=關），走 **Alembic 遷移**
    `b8c9d0e1f2a3`（建表 + `batch_alter_table` 加欄、既有規則列 server_default 回填 30）。
  - 新增 `services/opportunity_scan.py`：純函式 `screener_results_to_rows`（映射 + 依 OOS EV 排序）
    與 `upsert_opportunities`（同 symbol+strategy 更新不重複、保留既有 status），及排程入口
    `run_opportunity_scan`——**先過盤中閘**（重用 `alpaca_client.is_market_open()`，收盤跳過不空轉
    回測；查不到開市狀態時 best-effort 照跑），**重用既有 `screener.screen_watchlist`**，把候選
    upsert 進表，對「新發現且超過提醒門檻（OOS EV ≥ `ev_threshold`）」者 `notify` 一次後翻 `seen`
    去抖。`bot_manager` 加 `schedule_opportunity_scan(interval)` 週期 job（0=移除），`main.py`
    啟動時依規則掛上。
  - 新增唯讀 `GET /opportunities`（依 OOS EV 排序，可選 limit/status）；戰情頁聚合加「機會清單」
    部門卡；`PUT /automation` 開放編輯 `scan_interval_min`（改值即時重掛週期 job，不必重啟）、
    前端 `AutomationPanel` 加「探勘間隔」欄位。
  - 紀律：候選 EV/勝率**一律存樣本外（OOS）**、提醒門檻比對 OOS（Phase 6 step-04）；週期 job
    **只收集 + 排名 + 持久化**，不自動建 Bot、不上真錢（部署是 step-06 人工核准）。測試：
    `tests/test_opportunity.py`（純函式/upsert 冪等與 status 流轉/盤中閘與去抖提醒/端點往返）、
    前端 `CompanyPage.test.jsx`+`AutomationPanel.test.jsx` 補對應斷言。

- **Phase 10 step-01：戰情室聚合 + 公司戰情頁（看得到的 AI 公司）**——新增唯讀聚合端點
  `GET /company/overview`（`backend/routers/company.py`），把既有讀取點（帳戶 best-effort /
  Bot 艦隊啟用數 / 自動化規則與名額 / 風控熔斷 / 最近決策審計）組成一包，**純呈現、不自算 EV、
  不做任何交易或部署動作**；帳戶區塊離線（無金鑰）時回 `None` 不讓整頁崩。前端新增
  `pages/CompanyPage.jsx`（sidebar 加「公司戰情」項 + 路由），用「部門卡」呈現每個公司角色現況並
  連到對應既有頁（Bot 艦隊→監控中心、策略主管→回測歷史、回測主管→進化實驗室、決策審計→決策頁）。
  顏色一律吃 `theme`/`NEON`、不寫死 hex。測試：`tests/test_company.py`（聚合鍵齊全 + 離線降級）、
  `CompanyPage.test.jsx`（部門卡渲染 + 連結）。

- **Phase 10「AI 交易公司」構想藍圖**——把使用者願景（市場蒐集員爬蟲找策略 / 蒐集員主管列因子數值表 /
  政治專討員 Discord 判讀川普貼文 / 開機常駐自跑 / 老闆一頁核准 Bot 上真錢）整理成可分步施工的藍圖。
  確立兩條紀律：①「六角色 = 既有服務上的部門/關卡」的**編排層**（非自治多代理 swarm）；②任何新來源
  （爬蟲 / Discord / LLM 提案）的策略點子**一律過 Phase 6 OOS + Phase 7 step-07 防過擬合閘才進 Paper**、
  進真錢再過人工核准 + **既有實盤雙閘不更動**。新增 `docs/phase-10-ai-company/`：README（願景→可行性表
  ＝組織圖對照現有碼→目標架構圖→施工路線→明確界線）+ 7 個 step 檔（戰情頁 / 常駐探勘+機會清單 /
  因子表+報表 / 爬蟲蒐集員 / Discord 政治員 / 董事會核准頁 / 開機常駐化），各檔走護欄合約結構
  （目標→改動→重用既有→DoD→不要做）。`README.md` / `CLAUDE.md` 開發階段表加 Phase 10 列（標構想藍圖）。
  **純文件、未動程式碼。**

- **Phase 5 選配：好策略一鍵轉 Bot + 主動提醒**——補完 `docs/roadmap-strategy-workbench.md`
  第六節的選配項（原列三項，其中「助手 tool_calls 顯示」因助手早改成「記憶預先注入 system 提示」、
  不再用 tool-use 而**棄做**，無 tool_calls 可顯示）。
  - **好策略一鍵轉 Bot**：新增 `POST /presets/{id}/to-bot`（`backend/routers/presets.py`），把方案的
    策略/標的/參數**複製**成一個新 Bot 實跑（複製非綁定：之後改方案不動到 Bot；symbol 轉大寫、
    風控欄位留空、預設不啟動排程）。前端 `PresetsPage` 每張方案卡加「🤖 轉成 Bot 實跑」鈕，走
    `ConfirmDialog` 確認後呼 `api.presetToBot`，成功顯示綠色提示。全程 Paper、不碰實盤雙閘。
  - **主動提醒**：新增 `GET /reminders`（純讀現有資料、不連網），掃出兩類待辦——①回測 EV 為負且
    尚未檢討（提示請助手分析）②標為好策略(`is_good`)但同 標的+策略 還沒建成 Bot（提示可一鍵轉 Bot），
    對齊 Phase 5「EV 檢討 → 越來越聰明」閉環。前端新增 `RemindersBanner` 元件（無事項則不渲染），
    掛在 `PresetsPage` 頂部；建 Bot / 跑回測後以 signal 觸發重抓。顏色吃主題、不寫死 hex。
  - 測試：`tests/test_presets_extra.py`（preset→Bot 欄位對映 / name 覆寫；reminders 負 EV 未檢討、
    已檢討/正 EV 不提醒、好策略未實跑→建 Bot 後消失，6 passed）；前端 `PresetsPage.test.jsx` 補
    轉 Bot 流程、新增 `RemindersBanner.test.jsx`（空/有提醒兩態）。

- **自動化規則 `.env` → DB 表（前端可編輯）**——把模式 B 自動部署規則（`AUTO_DEPLOY_*`）
  從「唯讀吃 `.env`、改了要重啟」搬進 DB 單列表，讓前端可即時編輯儲存。完成 README「後續/未竟」
  列的 redesign backlog。
  - **新 model + 遷移**：`backend/models/automation_config.py`（單列 id=1，比照 `portfolio_state`，
    6 欄：`enabled`/`ev_threshold`/`winrate_threshold`/`max_bots`/`cash_per_bot`/`scan_hour`），
    走 Alembic 遷移 `a7b8c9d0e1f2`（建表 + 用 `.env` 預設常數種一筆預設列）。
  - **存取服務**：`backend/services/automation_config.py` 的 `get_config`（load-or-seed：空表用
    `settings.AUTO_DEPLOY_*` 種一筆防呆）+ `update_config`（只改有帶欄位、驗證範圍、回傳
    `scan_hour` 是否變動）。
  - **後端讀取點全改吃 DB**：`automation.run_auto_deploy` 開頭 `get_config(db)`，總開關 / 門檻 /
    配資一律讀 `cfg.*`（`plan_deployments` 純函式與雙門檻/去重/名額演算法**不動**）；`main.py`
    啟動掛盤前 cron 改讀 DB 的 `scan_hour`。
  - **API**：`GET /automation` 改讀 DB（回傳鍵名/型別不變，保前端契約）；新增 `PUT /automation`
    （6 欄全 Optional、驗證失敗回 400；改 `scan_hour` 即時 `bot_manager.schedule_auto_deploy`
    重掛 cron，不必重啟）。
  - **前端**：`api.js` 加 `updateAutomation`；`AutomationPanel.jsx` 從唯讀儀表加「編輯規則」模式
    （受控表單 + Switch + 數字欄位），儲存呼 PUT；**開啟總開關走 `ConfirmDialog` 二次確認**
    （語意＝開自動駕駛，仍全程 Paper、與實盤雙閘獨立）。顏色吃主題、不寫死 hex。
  - **連帶修正**：`AutomationPanel` 勝率門檻顯示原本寫 `winrate_threshold * 100`，但後端存的就是
    百分比（55=55%），會誤顯示成 5500%；改為直接顯示，與可編輯表單的回送語意一致。
  - **安全紅線**：全程不碰實盤雙閘（`ALPACA_BASE_URL` / `ALLOW_LIVE_TRADING`），自動建的 Bot
    下單仍經 `submit_market_order` 雙閘把關；`.env` 的 `AUTO_DEPLOY_*` 保留當建表種子 / fallback。
  - 測試：新增 `tests/test_automation_config.py`（get_config seed/冪等、update_config 只改有帶/
    驗證/scan_hour 變動旗標、PUT 往返 + 重掛 cron + 驗證 400）；`AutomationPanel.test.jsx` 補
    編輯儲存 / 開總開關需確認，並把假資料的 `winrate_threshold` 對齊真實後端（55 而非 0.55）。

- **redesign 殘項收尾：前端自動化規則面板 + BotAvatar 深底調色**——把 `docs/redesign/README.md`
  與 `phase-4-automation.md` 列為「後續微調」的兩項未竟工補上（redesign 四階段早已完成、
  phase-9 疊在其上無回歸，故只剩這兩個純打磨）。
  - **模式 B 自動化規則面板**：`api.js` 加 `getAutomation`/`runAutomation`；新增
    `components/AutomationPanel.jsx` 掛在監控中心——唯讀展示 `.env` 的 `AUTO_DEPLOY_*` 規則與
    名額（總開關/EV·勝率門檻/配資/盤前時刻/已用·上限），並可「預覽（dry-run）」或「立即試跑一輪」
    （試跑會建 Paper Bot，故走 `ConfirmDialog` 確認、成功後 reload）。規則本身仍由 `.env` 唯讀，
    面板不改門檻、不碰實盤雙閘、不改後端自動化邏輯。`App.jsx` 的 outletContext 補出 `reload`。
  - **BotAvatar 深底調色**：徽章頭像從淺色暖白改為深海軍藍漸層 + 冷白線稿 + 發光點綴色盤
    （吸收 `theme.js` NEON），不再貼在深藍面板上突兀；部件幾何與雜湊邏輯完全不動。
  - **連帶修正**：`Stat.jsx` 寫死的淺色文字（`#1a2238`）在深藍主題下幾乎看不見，改吃主題
    `text.primary`/`text.secondary`（AccountCard 等共用，redesign 換深底後的對比修正）。
  - 測試：新增 `AutomationPanel.test.jsx`（規則渲染 / dry-run 預覽 / 試跑需確認並 reload）；
    Vitest 全綠（71 passed）。

- **Phase 9 step-08 思考助手改全站抽屜 + 拆除 StrategyWorkbench**——右側策略工作台的內容前面步驟
  已分別搬到 `/presets`、`/backtest-runs`，這步收尾：把「思考助手聊天」改成全站可開的抽屜
  `components/AssistantDrawer.jsx`（右下浮動鈕開關，沿用 `api.sendChat`/`api.postmortem`，
  含填回測 ID 做事後檢討），掛在 `SidebarLayout`。確認三功能各有家後，**整支刪除**
  `StrategyWorkbench.jsx`（不留註解死碼）；全站 grep 無殘留 import。助手後端契約不變（仍只思考，
  不下單/不跑回測）。測試：`AssistantDrawer.test.jsx`（開抽屜/聊天/檢討）；Vitest 全綠（68 passed）、
  build 通過。**Phase 9（step-01~08）完成。**

- **Phase 9 step-07 進化實驗室（/evolution）+ 策略知識庫（/library）**——把 Phase 8 的
  「策略知識庫 + 組合進化」呈現成兩頁。
  - `api.js` 加 knowledge 全套（`getKnowledge`/`getKnowledgeRanking`/`getKnowledgeItem`/
    `validateKnowledge`/`promoteKnowledge`/`rejectKnowledge`）。抽共用 `components/KnowledgeCard.jsx`
    （理論/場景/使用時機/OOS 指標/狀態親和性）。
  - `LibraryPage`：唯讀策展庫 + 排行（curated/validated，依 OOS EV 排序），不做晉升/退回。
    `EvolutionPage`：候選審核 + 跑驗證管線 + **人在迴路**晉升（validated→curated）/ 退回（附理由）——
    晉升一律由使用者點按觸發，前端不自動晉升、不重算 EV/驗證。新增 sidebar「進化實驗室」「策略知識庫」項。
  - 測試：`EvolutionPage.test.jsx`（候選/驗證/晉升）+ `LibraryPage.test.jsx`（策展庫/切換）；
    Vitest 全綠（65 passed）、build 通過。

- **Phase 9 step-06 決策審計頁（/decisions）**——把每個 Bot 的決策軌跡（為何在某時點
  買/賣/觀望/跳過）做成可瀏覽頁，「每一筆自動決策可追溯」的前端呈現。`api.getBotDecisions`
  打 Phase 6 `GET /bots/{id}/decisions`；`pages/DecisionsPage.jsx` 選 Bot → 時序列出
  action/signal/reason/price/時間，不同 action（bought/sold/hold/skipped_*）配色。
  只顯示後端審計、不重算。新增 sidebar「決策審計」項。測試：`DecisionsPage.test.jsx`
  （未選不抓/選 Bot 列出含配色）；Vitest 全綠（61 passed）、build 通過。

- **Phase 9 step-05 探討/檢討頁（/explorations）+ 後端讀取端點**——把 explorations 檔案記憶
  （LLM 事後檢討）做成可瀏覽的唯讀頁（左清單 + 右內容）。**唯一碰後端的前端步驟**。
  - 後端：新增 `backend/routers/explorations.py`（`GET /explorations` 重用 `list_index_entries()`；
    `GET /explorations/{name}` 重用 `read_exploration()` 防穿越，讀不到回 404），掛上 `main.py`。
    **不**自己 open()/拼路徑（安全紅線）；唯讀，無寫/改/刪。
  - 前端：`api.js` 加 `getExplorations`/`getExploration`；新增 `pages/ExplorationsPage.jsx`
    （內容用輕量 pre-wrap 顯示，不引重型 markdown 依賴）。新增 sidebar「探討檢討」項。
  - 測試：`tests/test_explorations_api.py`（往返/404/**防穿越** `../`、非 .md，4 passed）+
    `ExplorationsPage.test.jsx`（清單/讀內容）；前端 Vitest 全綠（59 passed）、build 通過。

- **Phase 9 step-04 策略方案頁（/presets）**——把右側工作台的策略方案搬成獨立全頁：
  CRUD（新增/改名/調參/收藏/刪除）+ 一鍵跑回測。沿用工作台既有方案邏輯與 preset api，
  刪除走既有 `ConfirmDialog`、回測結果用共用 `BacktestResultCard`，不自造新表單風格。
  新增 sidebar「策略方案」項。測試：`PresetsPage.test.jsx`（渲染/新增/刪除確認，monkeypatch api）；
  Vitest 全綠（57 passed）、build 通過。

- **Phase 9 step-03 回測歷史 / EV 榜頁（/backtest-runs）**——把埋在右側工作台的回測歷史搬成獨立全頁：
  依 EV 排序的榜、收藏標星、點一筆看完整 metrics + 資金曲線、勾選數筆並排比較。
  - 抽共用元件 `components/BacktestResultCard.jsx`（EV 頭條卡）並回頭讓 `StrategyWorkbench` 區2 改用它，
    不重寫兩份；資金曲線用純 SVG `components/EquitySparkline.jsx`（**不引新圖表庫**）。
  - 不改後端 `/backtest-runs` 排序語意、不在前端重算 EV——只顯示後端結果。新增 sidebar「回測歷史」項。
  - 測試：`BacktestRunsPage.test.jsx`（渲染榜/收藏切換，monkeypatch api）；Vitest 全綠（54 passed）、build 通過。

- **Phase 9 step-02 交易紀錄頁（/trades）+ 篩選**——把暫放回測工具頁的 TradesTable 升級成
  獨立頁，上方加篩選列（依 Bot / 標的 / 買賣別 / 日期區間）。篩選為前端純函式
  `utils/filterTrades.js`（不改後端 /trades 端點），抽純函式好測。新增 sidebar「交易紀錄」項。
  測試：`filterTrades.test.jsx`（各維度/交集/空集/非陣列）+ `TradesPage.test.jsx`（渲染/篩選/清除）；
  Vitest 全綠（52 passed）、`npm run build` 通過。

- **Phase 9 step-01 導覽重構（Tabs→sidebar+路由）+ Dashboard 瘦身**——把原本「上方 4 個 Tabs +
  右側折疊工作台」改成「左側 sidebar 導覽 + react-router 多頁面」的專業終端機外殼。
  - 引入 `react-router-dom`；新增 `components/SidebarLayout.jsx`（常駐外殼：Header + 側欄導覽
    + `<Outlet context>`，沿用 `theme.js` NEON 深藍色票，不另立配色）。
  - `App.jsx` 改成路由根（`BrowserRouter`/`Routes`）；狀態與 handler 仍集中在 App，經
    `<Outlet context>` 分配給各頁；既有四塊搬成路由頁（`pages/DashboardPage`/`AiExplorePage`/
    `ChartsPage`/`FundamentalsPage`），**行為不變**、圖表仍 lazy 分包。
  - **Dashboard 瘦身**：監控中心只留 AccountCard + AI 燈號 + BotList；AutoBacktestPanel /
    BacktestPanel / TradesTable 移出儀表板，暫放 `pages/BacktestToolsPage`（step-02/03 接手拆分）。
  - 測試：`SidebarLayout.test.jsx`（導覽項目/Outlet/實盤警告）；前端 Vitest 全綠（40 passed）、
    `npm run build` 通過。

- **Phase 8 step-01~06 策略知識庫 + 組合進化（人在迴路閉環）**——把「蒐集策略 → 整合組合 →
  自動驗證 → 排序 → 人在迴路策展」串成閉環，強依賴 Phase 6（誠實 OOS）與 Phase 7 step-07（防過擬合）。
  - **step-01 知識庫資料模型**：新增 `StrategyKnowledge`（理論/場景/使用時機/驗證狀態機
    candidate→validated→curated/rejected/OOS 指標/狀態親和性），走 Alembic 遷移
    `f6a7b8c9d0e1`；新增 `routers/knowledge.py` 基本 CRUD。
  - **step-02 策略生成器**：`services/strategy_generator.py` 用 LLM 依場景**草擬**候選參數
    （限既有策略鍵），`POST /knowledge/propose` 只進候選區、不回測不部署；沿用 `llm` 外送安全閥，
    **不**自動寫新策略 `.py`（新邏輯一律走 strategy-builder skill）。
  - **step-03 策略組合引擎**：`strategies/composite.py` 的 `CompositeStrategy`（投票/加權/狀態切換），
    聚合抽成純函式 `aggregate_signals`；註冊進 `STRATEGY_REGISTRY`（鍵 `composite`），走既有
    `_run_on_df`/Bot 流程零特例；子策略統一吃同一份 df（呼應「資料只抓一次」）。
  - **step-04 自動驗證管線**：`services/evolution.py` 的 `validate_candidate` **重用** Phase 6
    含成本/隔日成交回測 + `split_train_test` 單次 OOS + Phase 7 `walk_forward`/`is_layer_worth_it`，
    只有「樣本外真加分」判 validated，否則 rejected；判定鍵讀 OOS/walk-forward，非 in-sample。
  - **step-05 排行 + 使用時機說明**：`GET /knowledge/ranking` 依 OOS EV 排序；
    `POST /knowledge/{id}/usage-note` 用 Phase 7 狀態親和性 + LLM 寫一兩句白話「何時用」，
    寫回 `usage_note`/`regime_affinity`。
  - **step-06 人在迴路審核**：`POST /knowledge/{id}/promote`（validated→curated，**只能由人觸發**）、
    `/reject`（附理由）；採用/淘汰理由沿用 explorations 檔案記憶（新增 `write_knowledge_note`，
    `knowledge-` 前綴與回測檢討區隔不撞檔），形成可追溯軌跡。自動流程到 validated 為止，無自動晉升路徑。
  - 測試：`test_knowledge`/`test_composite`/`test_strategy_generator`/`test_evolution`
    （CRUD/狀態流轉/404、聚合純函式、LLM 提案 monkeypatch、OOS 加分→validated/不加分→rejected）；
    `pytest tests/ -q` 全綠（249 passed）。`composite` 為事件式聚合器，於 `test_vectorized_engine`
    的「全策略向量化」不變式中明確豁免。

### 修正

- **Phase 8 加固：組合策略防呆 + 寫入把關，杜絕「爛組合進庫、實盤 Bot 崩」**——
  - `strategies/composite.py` 新增純函式 `validate_composite_params`：method 須為
    vote/weighted/regime_switch；members 須非空且子策略代號皆為既有策略、**禁巢狀 composite**
    （防無限遞迴）；regime_switch 須帶非空且合法的 `regime_strategies` 對照表。
  - `CompositeStrategy._sub_signal` 加執行期安全網：子策略建立/出訊號失敗時降級為觀望（HOLD），
    **不往上拋例外**——避免單一壞子策略弄崩整個 `bot_manager` 實盤迴圈。
  - `routers/knowledge.py`：`POST/PUT /knowledge` 對 `strategy_key=="composite"` 在**寫入前**
    驗參數（不合法回 400）；`POST /knowledge/propose` 擋下 composite（無 LLM 參數 schema，請手動建立）。
- **驗證管線資料不足時給明確錯誤**——`services/evolution.py` 的 `validate_candidate` 若
  walk-forward 湊不出任何 fold（資料太短）改丟明確 `ValueError`（含所需/實際根數），
  router 轉 400；使用者分得清「資料太短」與「策略真的不加分」，不再靜默判 rejected。
- **`POST /knowledge/{id}/reject` 冪等**——已 rejected 的再退回回 400，避免重複寫 explorations 記憶。
- **`GET /knowledge` 與 `/knowledge/ranking` 加可選 `limit`/`offset` 分頁**（預設全取，向後相容）。
- 測試：`test_composite` 補 `validate_composite_params` 正/反例（空 members／非法子鍵／巢狀／
  錯 method／regime_switch 缺表）與子策略安全網；`test_knowledge` 補 `/propose` 端點、composite
  寫入把關（合法 200／非法 400）、reject 冪等。

### 變更

- **依層驗證結論接線：meta-labeling 收回固定策略線上路徑（其餘層不動）**——跑 `scripts/validate_layers.py`
  （10 檔 watchlist、walk-forward）後依「沒加分就砍」鐵律調整：
  - **唯一在 OOS 加分的是 meta-labeling**（folds=444、Δ=+27.8），但原本只接在 `adaptive` 路徑內，
    而 adaptive 證明有害（folds=90、Δ=−115）且預設關 → meta 在普通 Bot 線上等於死碼。
    把 `should_take` 二級過濾接進 `bot_manager._run_strategy` 的 BUY 路徑（閘 `META_LABEL_ENABLED`），
    流程與 `layer_validation.MetaFilteredStrategy` 一致，線上行為＝樣本外驗證量到的那條。
  - **adaptive 維持關**（`bot.adaptive` 預設 False，無 bot 開啟）；kelly folds 不足（2<3）不認證、擱置；
    event-risk 為風險煞車、不可 OOS 驗證，照舊。
- **層驗證誠實修法：adaptive / kelly 給「公平的樣本外測試」（非調參騙綠）**——遵守 step-07 鐵律
  「框架是用來砍沒用的層、不是美化績效」，只修方法論瑕疵、不為了過而調門檻。
  - **kelly 測試原本根本沒跑到（`folds=0`）**：舊版在同一段 60 根測試窗上「同時估 W/R 又複利」，
    既偷看未來（in-sample 凱利）又因湊不到 `KELLY_MIN_ROUND_TRIPS` 而每 fold 全 skip。
    改成分離訓練/測試＋**擴張窗**估比例：在「測試段之前的全段」估凱利比例（嚴格 OOS、不偷看），
    把固定比例與凱利比例套到測試段已實現報酬流複利比終值。測試段只需 ≥1 筆 round-trip。
    結果：`folds 0→2`、凱利略勝基準（+0.0011），但仍 < `VALIDATION_MIN_FOLDS=3`
    → **無法認證**（資料太薄，需更多標的/更長歷史，不靠調參湊綠）。
  - **adaptive 無可信狀態時 fallback 改為 best-fixed 而非 HOLD**：meta-strategy 在沒把握的狀態
    不該坐現金白丟基準 edge，應退回「整體最佳固定策略」當地板（`AdaptiveMappedStrategy`
    新增 `fallback_key`）。如此 candidate 只在「有把握更好」的狀態才偏離 baseline，驗純粹狀態切換增益。
    結果：OOS 由 **−159.8 改善到 −115.2**（candidate 28.6→73.3），但**仍輸基準**
    → 維持預設關（`bot.adaptive=False`），fallback 設計改善保留。
  - 結論：兩層皆未以誠實手段轉綠——這正是 step-07 框架照設計運作（殺弱層，不美化）。
    meta 仍為唯一 OOS 加分層（+27.8 / 444 folds）。

### 新增

- **工作流視覺化文件**——新增 `docs/workflow-diagrams.md`，用 Mermaid 畫 4 張圖整理系統思緒：
  ① 高層全景（研究/實盤/驗證三軌 + 共用底座）、② 即時/自動交易決策流水線（照
  `bot_manager.run_bot_once` 實際順序，含 Phase 6/7 各閘與 SKIP 出口；標明 Kelly/事件閘僅
  `automation` 自動部署流）、③ 回測/EV 流水線（OOS EV 排名）、④ Phase 7 層驗證流（各層
  worth 判決）。純文件，不動程式碼。
- **文件同步至最新狀態**——`README.md` 進度表補 Phase 7（✅）+ Phase 8/9（藍圖）、策略數 8→9（補 ADX 趨勢）、
  新增 Phase 7 落地說明 + 工作流圖連結；`CLAUDE.md` 專案結構補 Phase 7 services
  （regime_features/regime/strategy_selector/sizing/meta_label/event_risk/validation/layer_validation）、
  `scripts/validate_layers.py`、`docs/workflow-diagrams.md`。

- **Phase 7 收尾：層驗證 harness（用 step-07 實測 step-03~06 各層有沒有加分）**——把 step-07 的
  `walk_forward` / `is_layer_worth_it` 真的接到後面幾層，做誠實的 baseline-vs-candidate 樣本外比較。
  - 新增 `backend/services/layer_validation.py`：用「包裝策略」(`MetaFilteredStrategy` /
    `AdaptiveMappedStrategy`) 把層塞進既有含成本回測路徑（`_run_on_df`，不動 sim）；
    `validate_meta_layer` / `validate_adaptive_layer` / `validate_kelly_layer` / `validate_layers`
    （跨檔池化）。step-04 凱利比「終值報酬」（凱利是部位大小、不改單筆 EV）；
    step-06 誠實標記「無 point-in-time 情緒→不可 OOS 驗證，僅當風險煞車」（不產生假數字）。
  - 新增 `scripts/validate_layers.py`：一鍵跑 watchlist（預設 yfinance）印各層 verdict 表。
  - 小重構 `strategy_selector.py`：抽出 `build_map_from_df`（讓 walk-forward 每個 fold 用訓練段建對照表，
    對外行為不變、既有測試全綠）。
  - 新增 `tests/test_layer_validation.py`（9 測；合成資料 + monkeypatch，不連網）。`pytest tests/ -q` → **227 passed**。
  - **★實測結論（AAPL/MSFT/NVDA/SPY/QQQ, yfinance）**：
    - **step-05 meta-labeling：worth=True（OOS EV +33, 219 folds）→ 有加分，留。**
    - **step-03 adaptive-selection：worth=False（OOS EV −151, 45 folds）→ 自適應輸給「訓練段最佳固定策略」，該降級/砍。**
      （呼應 step-03 文件警告：選策略層是過擬合重災區；預設本就關 `bot.adaptive=False`。）
    - step-04 kelly-sizing：fold 不足（60 根測試窗湊不到 ≥10 回合）→ 此窗格下無法判定，需更長測試窗再驗。
    - step-06 event-risk：不可 OOS 驗證（無 PIT 資料）→ 維持風險煞車定位。
    - 註：本次只產生證據與結論，**未自動刪任何層**；adaptive 的降級/移除另開獨立提案。
  - 新增操作指南 `docs/how-to-add-strategy.md`（新增策略的 6 個落地點 + 怎麼用 + 怎麼驗 OOS）。

- **Phase 7 step-04~06：分數凱利部位 + meta-labeling 二級過濾 + 事件驅動風險閘**——藍圖 [`docs/phase-7-adaptive-regime/`](docs/history/phase-7-adaptive-regime/README.md)。
  - **step-04 分數凱利部位（區塊 3：可投多少量）**：新增純函式 `backend/services/sizing.py`：
    - `kelly_fraction(win_rate, avg_win, avg_loss)`：算 `f* = W − (1−W)/R`，乘分數凱利係數、再用硬上限夾住；
      負期望（f*≤0）或缺賠率原料 → 回 0（不下注）。三重保守：用 OOS 的 W/R + 分數凱利 + 上限。
    - `kelly_trade_amount(...)`：把回測 OOS metrics 換成「該配多少現金」；**OOS 回合數不足 → 回 0**（W/R 不可信）。
    - `optimizer` 補上 `oos_avg_win` / `oos_avg_loss`（凱利的賠率原料，一律用樣本外、含成本的誠實值）。
    - 接線：`automation` 自動部署改用凱利算每檔 `trade_amount`（仍受 Phase 6 step-05 每檔配資上限約束；只會縮不會超）。
    - `config.py` 新增 `KELLY_FRACTION`(0.25)/`KELLY_MAX_FRACTION`(0.2)/`KELLY_MIN_ROUND_TRIPS`(10)。
  - **step-05 meta-labeling 二級過濾（規則式起步，零過擬合）**：新增純函式 `backend/services/meta_label.py`：
    - `should_take(signal, features, regime)`：一級給方向、二級決定「該不該下注 + 信心」。只過濾**進場（BUY）**；
      高波動/爆量滯漲/未知狀態的 BUY 否決，趨勢盤放行；`meta_confidence` 用 step-01 特徵微調（趨勢加分、過熱扣分）。
    - 接線：`bot_manager` 自適應路徑在一級 BUY 後跑二級，信心不足 → 縮回觀望（信心寫進原因供決策審計）。
    - `config.py` 新增 `META_LABEL_ENABLED`(true)/`META_MIN_CONFIDENCE`(0.5)。學習式 meta 列為進階，**必經 step-07 purged CV** 才上。
  - **step-06 事件驅動風險閘（情緒當煞車、不當油門）**：新增純函式 `backend/services/event_risk.py`：
    - `assess_event_risk(sentiment)`：重大負面 → 不開新倉（`size_factor=0`）；偏弱未達否決 → 縮部位；中性/正向 → 照常。
      **明確不猜方向**（bullish 高分不放大部位，factor 上限 1.0）；best-effort（無情緒/連不上不阻斷）。重用既有情緒管線。
    - 接線：`automation` 部署時用 `size_factor` 縮放凱利部位（與既有 `apply_sentiment` 否決閘分工，不重造）。
    - `config.py` 新增 `EVENT_RISK_ENABLED`(true)/`EVENT_RISK_CAUTION_SCORE`(0)/`EVENT_RISK_SIZE_FACTOR`(0.5)。
  - 誠實聲明：這三層都只是「機制就位」；是否真的在 OOS 加分，須用 step-07 `is_layer_worth_it` 驗證，加不了分就砍。
  - 測試：新增 `tests/test_sizing.py`(6) / `tests/test_meta_label.py`(5) / `tests/test_event_risk.py`(6)。
    `pytest tests/ -q` → **218 passed**（乾淨 DB）。

- **Phase 7 step-07：★防過擬合驗證框架（橫跨全部的鐵律）**——藍圖 [`docs/phase-7-adaptive-regime/step-07-anti-overfitting-validation.md`](docs/history/phase-7-adaptive-regime/step-07-anti-overfitting-validation.md)。
  - 新增純函式 `backend/services/validation.py`：
    - `walk_forward_splits` / `walk_forward`：滾動前進驗證。每個 fold 只在「測試段」子 df 上跑含成本
      `_run_on_df`（與正式回測同路徑、與 optimizer OOS 語意一致），回每個 fold 的 OOS 績效。
    - `purged_kfold_splits`：清洗式 K-Fold（López de Prado），測試塊前後各清掉 embargo 根，
      防時序交界洩漏未來（給未來的學習式模型用）。
    - `is_layer_worth_it(baseline_oos, candidate_oos)`：判定「加這層」有沒有在 OOS 上贏過「不加」——
      內建最小提升門檻 + fold 數檢查，**worth=True 才准上線**。心態：用來「殺掉沒用的層」，不是美化績效。
  - `config.py` 新增 `VALIDATION_TRAIN_WINDOW`/`TEST_WINDOW`/`STEP`/`KFOLD`/`EMBARGO`/`MIN_IMPROVEMENT`/`MIN_FOLDS`
    （視窗單位為 K 棒數）。
  - 規範意義：step-02/03/05 的學習式版本、step-03 的對照表，上線前都應先過 `is_layer_worth_it`；
    加不了分的層就砍（CHANGELOG 記「試過、無效、砍掉」也是成果）。step-04 凱利的 W/R 也應吃 walk-forward 的 OOS 統計。
  - 測試：新增 `tests/test_validation.py`（滾動切分正確、purged 無洩漏、`is_layer_worth_it` 能判死
    「in-sample 漂亮、OOS 崩」的假層、fold 不足不採信）。`pytest tests/ -q` → 201 passed（乾淨 DB）。

- **Phase 7 step-01~03：自適應市場狀態（區塊 2：狀態→選策略）**——藍圖 [`docs/phase-7-adaptive-regime/`](docs/history/phase-7-adaptive-regime/README.md)。
  - **step-01 市場狀態特徵工程**：新增純函式 `backend/services/regime_features.py`：`compute_features(df)`
    回 6 個可解釋特徵（`volume_ratio` 重用 `screener`、`return_5d/20d`、`volatility_20d` 年化、
    `trend_strength` 重用 `indicators.adx_components`、`atr_pct`、`range_position` 唐奇安%）。
    純 pandas、無 ML、無未來函數（只用截至最後一根的資料，與回測 walk-forward 同紀律）。
  - **step-02 狀態分類器（路線 A 規則式決策樹）**：新增 `backend/services/regime.py`：`classify_regime(features)`
    用 if-else 閾值分 4 種狀態（`trending`/`ranging`/`high_volume_stall`/`high_volatility`，核心特徵全缺回 `unknown`）。
    閾值放 `config.py`（`REGIME_HIGH_VOL_THRESHOLD`/`REGIME_VOLUME_SPIKE`/`REGIME_FLAT_RETURN`/`REGIME_ADX_TREND`）。
    可解釋、零過擬合；學習式路線 B 未做（沒有 step-07 驗證框架前不碰）。
  - **step-03 狀態→策略自適應選擇**：新增 `backend/services/strategy_selector.py`：
    `build_regime_strategy_map(symbol)` 在 **OOS 測試段**（`optimizer.split_train_test`）對每個策略跑含成本回測，
    把每筆 round-trip 盈虧歸到「進場當時的狀態」，每狀態挑「筆數 ≥ `REGIME_MIN_SAMPLE` 且 EV>0」中 EV 最高者；
    無人達標 → 該狀態回 `None`（保守觀望）。`select_strategy(features, map)` 線上查表；
    `get_regime_strategy_map` 記憶體快取。
  - Bot 新增 `adaptive` 布林欄（預設 False，向後相容）+ Alembic 遷移 `e5f6a7b8c9d0`。
    `bot_manager._run_strategy`：`adaptive` 開啟時走新增的 `_run_adaptive_strategy`——算當下狀態 → 查表挑策略 →
    產生訊號；無可信策略時 `HOLD` 觀望，原因帶 `[自適應 狀態→策略]` 供決策審計查驗。
    `config.py` 新增 `REGIME_MIN_SAMPLE` / `REGIME_MAP_DAYS`。
  - **誠實聲明**：本步只落地「機制」，**未宣稱已證明有效**。自適應是否真在 OOS 上贏過「單一最佳策略」
    須靠 Phase 7 step-07 驗證框架判定，贏不過就該砍掉這層（不要 vibe slop）。故預設關、且狀態無可信策略時保守觀望。
  - 測試：新增 `tests/test_regime_features.py`（特徵算對 + 無未來函數）、`tests/test_regime.py`（各狀態分類）、
    `tests/test_strategy_selector.py`（盈虧歸因 + 查表/退回 + build map 端到端 monkeypatch 不連網）。
    `pytest tests/ -q` → 193 passed（4 failed 為未追蹤孤兒檔 `test_trading_mode.py`，測一個不存在的 per-bot `mode` 功能，非本次變更）。

### 變更

- **Phase 6 step-01：統一資料路徑（實盤 = 回測）**——修 P4「實盤與回測資料源/回看長度分岔」。
  - `config.py` 新增 `DATA_SOURCE`（預設 `alpaca`，可設 `yfinance`）作為**全系統唯一資料源設定**；
    `.env.example` 同步補欄位。
  - 新增純函式 `backend/strategies/lookback.py`：`min_bars_required` 依各策略關鍵參數
    （`long_window`/`slow+signal`/`period`/`k_period`…）算出最小 K 棒數，`required_lookback_days`
    再換算成日曆天數（×1.6 暖機緩衝 + 交易日→日曆日 + 假日緩衝）。回測與實盤共用此推算。
  - `bot_manager._run_strategy` 改走 `market_data.get_bars(..., source=settings.DATA_SOURCE)` +
    `required_lookback_days(...)`，**不再寫死 `alpaca_client.get_bars(days=60)`**。
    修掉「`long_window=120` 等長週期策略實盤只拿 60 根、算不出指標、行為與回測不一致」的靜默失準。
  - `optimizer` / `screener` / `backtest` / `recommendations` 的 `source` 預設改讀 `settings.DATA_SOURCE`
    （保留呼叫端可覆寫參數，向後相容）。
  - 測試：新增 `tests/test_lookback.py`（各策略推算回看天數 ≥ 最小 K 棒數、隨參數遞增、舊版 60 不夠）；
    `tests/test_bot_manager.py` 加實盤資料路徑統一驗證（走 market_data、帶 DATA_SOURCE、帶推算天數）。
    `pytest tests/ -q` → 137 passed。
  - 決策備註：「回看天數一致」採「同源 + 兩路皆 ≥ 策略所需」詮釋，**回測續用 365 天不縮短**
    （縮短會砸爛 EV 樣本數，違反「EV 誠實」）。完整理由見 `docs/phase-6/step-01-unify-data-path.md`「實作備註」。

- **Phase 6 step-02 + step-03：回測誠實化（成本模型 + 隔日成交）**——修 P2（零成本）與 P3（偷看未來）。
  - `config.py` + `.env.example` 新增 `BACKTEST_COMMISSION_BPS`（預設 0，Alpaca 免佣）、
    `BACKTEST_SLIPPAGE_BPS`（預設 5 bps）。
  - **成本與隔日成交都實作在回測「共用核心」`_simulate_from_signals`**（事件式與向量化兩路都呼叫它，
    確保兩路結果仍一致、`test_vectorized_engine` 對拍續綠）：
    - 成本：買進成交價 ×(1+滑價)、賣出 ×(1−滑價)，買賣再各扣手續費；新增回傳 `total_cost`。
    - 隔日成交：訊號在第 i 根收盤算出，成交延到**第 i+1 根開盤價**（無 open 欄退回次根 close）；
      **最後一根的訊號沒有次根 → 不成交**（誠實，不無中生有）。
  - 成本參數沿 `_run_on_df` / `run_vectorized` / `run_backtest`（讀 config 預設，可顯式覆寫）一路帶入。
  - 測試：新增 `tests/test_cost_model.py`（滑價/手續費手算、高頻成本較高）；重寫 `tests/test_backtest.py`
    為隔日成交語意（買在次根開盤、最後一根不成交、零成本 total_cost=0）。
  - ⚠️ **預期效果**：多數策略 EV 會下降（成本 + 隔日成交，雙重保守），這是**預期的誠實化、不是 bug**。

- **Phase 6 step-04：樣本外（OOS）驗證——optimizer 以 OOS EV 排名 ★Phase 核心**——修 P1（樣本內過擬合）。
  - `config.py` + `.env.example` 新增 `OOS_TEST_RATIO`（預設 0.3）。
  - `optimizer.py` 新增純函式 `split_train_test`（時間序列切分，測試段在後、不洗牌）；
    `run_auto_backtest` 對每組參數在「整段 / 訓練段 / 測試段」各跑一次，**冠軍排序鍵改用
    `oos_expected_value`**（次鍵 OOS 總報酬）；metrics 新增 `oos_expected_value` / `oos_win_rate_pct` /
    `oos_total_return_pct` / `is_expected_value`（樣本內保留供對照，看「掉多少」就知道過擬合多嚴重）。
  - `screener.py` 海選門檻 / 排序改看 OOS EV；`automation.plan_deployments` 的 EV/勝率門檻**一律比對 OOS**；
    `/auto-backtest` 排行榜摘要新增 `oos_*` / `is_*` / `total_cost`。
  - ⚠️ **門檻語意變更**：同一個 `AUTO_DEPLOY_EV_THRESHOLD` 現在卡的是 **OOS EV**，比樣本內更難達到——
    這是對的（過擬合的策略本來就該過不了關）。
  - 測試：新增 `tests/test_oos.py`（split 切分/時序、冠軍依 OOS 排名、過擬合落差可見）；
    `tests/test_automation.py` / `tests/test_screener.py` 的假資料改用 `oos_*` 欄位。

- **Phase 6 step-05：組合層資金 / 購買力守門**——修 P6 前半（無組合層資金控管）。
  - 新增純函式 `backend/services/capital.py` 的 `plan_capital(planned, available_cash, cash_per_bot,
    reserve_ratio)`：可動用額度 = `available_cash×(1−reserve_ratio)`，逐筆核可、扣到不夠其餘進
    `rejected`（附原因）；`cash_per_bot<=0` 全核可、`reserve_ratio` 夾在 [0,1] 防呆。
  - `config.py` + `.env.example` 新增 `PORTFOLIO_CASH_RESERVE_RATIO`（預設 0.2，永遠留 20% 現金）。
  - `automation.run_auto_deploy`：部署前 best-effort 查 `get_account().cash` 套 `plan_capital`，
    只建 `approved`，`rejected` 併進回傳摘要與通知（離線查不到帳戶 → 略過守門、不阻斷預覽/測試）。
  - `bot_manager._handle_flat`：買進前 best-effort 查可用購買力，`qty×price > 購買力` 則跳過買進並
    記一筆 `skipped_no_buying_power` 審計（離線/查價失敗放行）。
  - 測試：新增 `tests/test_capital.py`（剛好夠/不夠/保留比例邊界/配資為 0/保留 100%）。

- **Phase 6 step-06：排程每輪重查 Bot**——修 P7（排程持有過期 ORM 物件）。
  - `bot_manager.start_bot` 的 `add_job` 改傳 `args=[bot.id]`（整數），不再鎖死當下的 ORM 物件。
  - `run_bot_once(bot_id, ...)` 改收 `bot_id`，函式開頭用 id 重查最新 Bot：查不到（已刪）→ 移除殭屍
    排程並 return；查到 → 用新鮮 Bot 跑後續。`routers/bots.run_bot_now` 改傳 `bot.id`。
  - 效果：用 `PUT /bots/{id}/risk` 拖曳水位線改風控，對**執行中**的 Bot 下一輪即生效，不必重啟後端。
  - 測試：重寫 `tests/test_bot_manager.py` 改用臨時 SQLite + 真 Bot（驗證重查用新風控值、已刪 Bot
    安全 no-op + 移除殭屍排程）。

- **Phase 6 step-07：AI 情緒真正進決策**——修 P5（死掉的 AI 情緒層；使用者明確要求）。
  - `config.py` + `.env.example` 新增 `SENTIMENT_GATING`（預設 true，總開關）、`SENTIMENT_MIN_SCORE`
    （預設 -20）。
  - `screener.py` 新增純函式 `sentiment_score` / `is_vetoed_by_sentiment`；最終排序鍵改
    `(OOS EV, 情緒分數)`（EV 為主、情緒為次）。
  - `automation.py` 新增純函式 `apply_sentiment`：`bearish` 或分數 `< min_score` → **情緒否決**
    （剔出部署候選）；其餘以情緒做 OOS EV 排序的次要加權；`sentiment=None`（沒跑情緒）視中性不否決；
    `enabled=False` 完全退回純 EV（向後相容）。`plan_deployments` 在 EV/勝率門檻**之後**串接它。
  - 紀律：情緒永遠是「輔」，OOS EV 永遠是「主」——情緒不會把更高 EV 的標的擠到更低 EV 標的之後。
  - 測試：新增 `tests/test_sentiment.py`（否決規則、停用退回、次要加權、EV 不翻盤、screener 排序）。

- **Phase 6 step-08：決策審計軌跡**——修 P8（無決策審計）。
  - 新增 model `backend/models/decision_log.py`（`DecisionLog`：`bot_id/symbol/signal/reason/price/
    action/created_at`，action 列舉 `bought/sold/hold/skipped_market_closed/skipped_no_buying_power/
    skipped_circuit_breaker`），走 Alembic 遷移 `c3d4e5f6a7b8`。
  - `bot_manager.run_bot_once` 各分支都寫一筆 `DecisionLog`（休市跳過/觀望/續抱/購買力不足/熔斷/
    買進/風控賣出/策略賣出）——連「沒成交但有決策」的時點都留痕。
  - 新增 `GET /bots/{id}/decisions`（最近 N 筆、倒序、limit 夾 1~500）。
  - 測試：新增 `tests/test_decision_log.py`（各分支寫對 action/signal/reason、端點往返）。

- **Phase 6 step-09：組合回撤熔斷**——修 P6 後半（無全域風險開關）。
  - 新增純函式 `backend/services/circuit_breaker.py` 的 `portfolio_circuit_breaker(equity_now,
    equity_peak, max_dd_pct)`；`check_breaker` 編排：best-effort 查 `get_account().portfolio_value`、
    更新持久化峰值、回是否熔斷，觸發時 `notify` 一次（去抖）。離線查不到帳戶 → 不熔斷（放行）。
  - 新增 model `backend/models/portfolio_state.py`（單列存權益峰值，重啟仍記得最高水位），
    走 Alembic 遷移 `d4e5f6a7b8c9`。
  - `config.py` + `.env.example` 新增 `PORTFOLIO_MAX_DRAWDOWN_PCT`（預設 20）。
  - 檢查點（只擋**新增曝險**、不碰出場）：`bot_manager._handle_flat` 買進前、`automation.run_auto_deploy`
    開頭；觸發 → 跳過並記 `skipped_circuit_breaker` / 整輪不建 Bot。既有持倉的 `check_exit` 完全不受影響。
  - 測試：新增 `tests/test_circuit_breaker.py`（純函式邊界、更新峰值後跌破熔斷、離線安全放行）。

- **Phase 6 step-10：架構與文件整理（無行為變更）**——清技術債、消除漂移風險。
  - 策略清單收成單一來源：`strategies/__init__.py` 新增 `STRATEGY_LABELS` + `list_strategies()`；
    新增 `GET /strategies`（`backend/routers/strategies.py`）回 `[{value,label}]`。
  - `config.py` 依領域分區重排 + 加區段註解（Alpaca/資料源/DB/LLM/Screener/Automation/回測成本 P6/
    OOS P6/情緒閘 P6/組合風控 P6/即時報價/Explorations），並修正「即時報價」誤標 Phase 6 的註解
    （即時報價屬改版子軌，本份「可信度地基」才是 Phase 6）。
  - 測試：新增 `tests/test_strategies_registry.py`（`GET /strategies` 往返 + 斷言「後端註冊鍵集合 ==
    前端 `constants.js` value 集合」，新增策略忘了同步前端會被測試擋下）。

- ✅ **Phase 6 全數完成（step-01 ~ step-10）**：`pytest tests/ -q` → **173 passed**。

### 文件

- 新增 **AI 實作護欄合約** `docs/ai-implementation-guardrails.md`：防止「未來 AI 自己 coding 時偏離原目標
  + 產生 vibe slop」的合約。內含：原目標錨點（North Star）、三層防漂移檢查（開工前/coding中/收工前）、
  反 slop 速查表、既有可重用清單（registry）、範圍柵欄（一步一分支一 PR）、領域誠實守則（OOS/含成本/
  無 look-ahead/EV/Paper/雙閘）、通用完成定義 DoD、「不確定就停」。所有 phase 步驟檔的共同前言。
  CLAUDE.md 新增「AI 自動 coding 前必讀」區段指向它。
- 新增 **Phase 8「策略知識庫 + 組合進化」構想藍圖** `docs/phase-8-strategy-evolution/`：把「蒐集多策略→
  整合組合→驗證→人在迴路策展」串成閉環。README + 6 步（知識庫資料模型 / 策略生成器 / 組合引擎 Ensemble /
  自動驗證管線 / 庫排行+使用時機 / 人在迴路審核）。強依賴 Phase 6 OOS + Phase 7 防過擬合；晉升一律人工。
- 新增 **Phase 9「專業前端工作站」構想藍圖** `docs/phase-9-frontend-workstation/`：上方 Tabs → 左側
  sidebar 多頁面（監控/交易紀錄/回測 EV 榜/策略方案/探討檢討/決策審計/狀態洞察/進化實驗室/知識庫）。
  README（含推薦 IA）+ 8 步；其中探討頁需補 `GET /explorations` 小端點（重用既有防穿越服務）。
- CLAUDE.md 開發階段表補上 Phase 6–9 + 改版子軌說明 + 跑真錢前必讀指引，確立 Phase 1–9 權威地圖。
- 新增 **Phase 7「自適應市場狀態」構想藍圖** `docs/phase-7-adaptive-regime/`：把
  「依當下市場狀態自動挑策略、算勝率、定部位」的願景，整理成有正式名稱、可評估、可分步施工的東西。
  索引 `README.md`（願景拆成三塊各給正式名稱：事件驅動 / 市場狀態辨識+決策樹 / 凱利+meta-labeling、
  可行性誠實評估、目標架構、**為何強依賴 Phase 6 先做完**、範圍界線）+ 7 個步驟各一檔（狀態特徵工程、
  狀態分類器決策樹、狀態→策略自適應選擇、分數凱利部位、meta-labeling 二級模型、事件驅動層「情緒當過濾
  不當主力」、★防過擬合驗證框架）。**構想/研究階段，明確標示區塊 1（讀演講猜漲跌）是 retail 夢碎重災區、
  只當輔助過濾**。純文件。
- 新增 **Phase 6「可信度地基」規劃文件** `docs/phase-6/`：把現有系統從「廣而淺」收斂成
  「將來能被信任、可託付真錢的自動交易機器人」的施工總藍圖。索引 `README.md`（背景 /
  8 道讀碼實證的根本問題 P1~P8 / 北極星 / 目標架構圖 / 10 步施工路線 / 可信度驗收 / 範圍界線）
  + 10 個步驟各一檔（統一資料路徑、回測成本模型、隔日成交語意、★樣本外驗證防過擬合、
  組合資金守門、排程每輪重查 Bot、AI 情緒真正進決策、決策審計軌跡、組合回撤熔斷、架構整理）。
  核心原則：**讓「回測看到的 EV」≈「實盤真的會發生的事」**。純文件，尚未動程式。
- 新增 `docs/human-vs-ai-operation.md`：分析「程式自動操作 vs 一般人手動操作」的落差
  （程式贏在盯盤 / 紀律 / 算力 / 無情緒；人贏在判斷異常 / 基本面宏觀 / 資金心理 / 過擬合判讀 /
  黑天鵝 / 法遵），並給出「是否真的拿去跑真盤」的誠實結論與分階段上線路線。

### 新增

- 向量化回測引擎（N1 海選加速，零新依賴／vectorbt 因強降 pandas 改自寫）：optimizer 全自動
  掃描改走 numpy/pandas 向量化訊號，**實測 42 組 × 500 根 K 棒從 64.9s → 0.375s（約 173×）**。
  新增 `backend/services/vectorized_engine.py`（9 個策略各一個整段向量化訊號產生器 +
  `run_vectorized`）。把 `backtest_engine` 的資金模擬與績效計算抽成共用核心
  `_simulate_from_signals`，事件式 `_run_on_df` 與向量化引擎共用同一份 → 兩路徑結果保證一致。
  optimizer 有向量化版本就走快路徑、沒有則自動退回事件式（永不漏算）。附
  `tests/test_vectorized_engine.py` 對拍測試（每策略比對向量化 vs 事件式的 EV/報酬/回撤/
  資金曲線完全一致）。Bot 即時交易仍走事件式 `generate_signal`，**不受影響**。

- 延伸績效分析（導入 **quantstats**）：回測結果新增風險調整後指標（Sharpe / Sortino /
  Calmar / 年化波動 / CAGR）與一鍵 HTML 績效報表（資金曲線、回撤、月報酬表）。後端
  `backend/services/analytics.py`（純函式 `returns_from_equity`／`extended_metrics`／
  `tearsheet_html`，全 try/except 防爆、quantstats 缺失或極短序列回 None 不崩）、在
  `backtest_engine.run_backtest` 單筆回測結果附 `extended`（**不**進 optimizer 海選迴圈，
  不拖慢掃描）、新端點 `GET /backtest-runs/{id}/report` 從已存的 `equity_curve` 產報表。
  前端 `StrategyWorkbench` 結果卡顯示 Sharpe/Sortino + 「開啟完整績效報表」、EV 歷史每列
  加 📊 報表按鈕；`api.reportUrl(id)`。附 `tests/test_analytics.py` 4 測。

- 新策略 **ADX 趨勢**（導入 **pandas-ta-classic**）：用 ADX 趨勢強度 + DI 方向判多空，
  ADX 低（盤整）不追。`backend/strategies/adx_trend.py` + `backend/strategies/indicators.py`
  （pandas-ta-classic 薄封裝，缺 high/low 自動退回 close 防呆），註冊進策略表、加入
  `optimizer.py` 掃描網格與前端策略清單。pandas-ta-classic 為「可選用指標庫」，現有 8 策略
  不動。附 `tests/test_strategies.py` 4 測（上升/下降/資料不足/盤整）。

- 圖表水位線「拖曳即改風控」（藍圖 Phase 1 未來擴充項落地）：在 K 線圖上直接拖曳
  止損 / 追蹤止盈水位線，放開即把新價格換算成百分比存回後端 Bot。進場均價線是真實
  成交價、不可拖。後端新增 `PUT /bots/{id}/risk`（`backend/routers/bots.py` 的
  `RiskUpdate` + `update_bot_risk`）：用 `exclude_unset` 只改「有帶」的欄位（拖一條
  線不會洗掉其他風控）、百分比驗證 0<x<1、帶 null 可關閉該機制。前端
  `LightweightChart.jsx` 對 editable 線疊可拖把手（`priceToCoordinate`/`coordinateToPrice`
  換算、rAF 讓把手黏在線上）、`utils/priceLines.js` 新增純函式 `priceToPct` 與線的
  拖曳中繼資料（botId/field/refPrice）、`api.js` 加 `updateBotRisk`，`App.jsx` 與
  `ChartGrid.jsx` 接上 `onPriceLineDrag`。附 `tests/test_bot_risk.py` 4 測試、
  `priceLines.test.jsx` 新增 6 測試。後端 97 綠、前端 37 綠。

### 移除

- 清除死碼：刪除已無人引用的 `frontend/src/TradingViewChart.jsx`（已被原生
  `LightweightChart` 取代）與 `frontend/src/components/CreateBotForm.jsx`（Dashboard
  改版後不再手填建 Bot）。

- 改版 Phase 4：全自動護欄 / 模式 B 自動部署（藍圖見 `docs/redesign/phase-4-automation.md`）。「自動駕駛」：
  盤前排程跑 AI 海選，對 EV + 勝率**同時**超標的策略無人工確認自動建 Bot。層層設防：
  - 後端 `backend/services/automation.py`：純函式 `plan_deployments`（EV/勝率雙門檻 + 同標的去重 +
    名額上限 `max−active`，好測）；編排 `run_auto_deploy`（重用 `screener` 海選 + 既有建 Bot/`start_bot`
    流程 + `notify` 通知，支援 `force` 略過總開關、`dry_run` 只預覽不寫 DB）。
  - 後端 `backend/routers/automation.py`：`GET /automation`（看規則與名額狀態）、`POST /automation/run`
    （手動觸發，`?dry_run=true` 預覽 / `?force=true` 略過總開關，方便不等盤前就驗證）。
  - `bot_manager.schedule_auto_deploy(hour)` 掛每日盤前 cron job；`main.py` 啟動時掛載（是否真的部署
    仍由總開關控制）。
  - `config.py` / `.env.example` 新增 `AUTO_DEPLOY_ENABLED`（**預設關**）/`EV_THRESHOLD`/
    `WINRATE_THRESHOLD`/`MAX_BOTS`/`CASH_PER_BOT`/`HOUR`。
  - **安全**：自動化總開關與實盤雙閘**獨立**（開自動化 ≠ 開實盤）；自動建的 Bot 下單仍經
    `alpaca_client.submit_market_order` 雙閘把關，預設 Paper，本階段完全不碰那道安全閥。
  - 測試：`tests/test_automation.py` 5 測試（純函式雙門檻/去重/名額 + GET/dry_run API）。後端 93 綠。

### 變更

- 改版 Phase 3：佈局清理 + 深藍沉浸主題（藍圖見 `docs/redesign/phase-3-ui-theme.md`）。捨棄亮色「精緻
  淺色金融」，全面改用**深海軍藍**基底，讓圖表水位線與獲利（青綠）/虧損（洋紅）數據更跳脫、長時間
  盯盤不刺眼。改動：
  - `theme.js`：`palette.mode` 轉 `dark`，`NEON` **沿用匯出名與鍵名只改值**（cyan→亮藍主動作、
    magenta→黃金點綴、green→青綠獲利、red→洋紅虧損），卡片/按鈕/輸入框/分頁改深藍面板與冷光邊框，
    既有 `import { NEON }` 的 Header/StrategyWorkbench 不用動就換上新色。
  - `index.css`：頁面底改深海軍藍 + 冷色光暈、`color-scheme: dark`、捲軸/selection 配深底。
  - `App.jsx`：儀表板移除「建立 Bot」表單（`CreateBotForm`，AI 架構下改由「AI 探勘」一鍵 Deploy 建
    Bot），頂部改放「AI 市場燈號」提示卡引導前往探勘分頁；連帶移除已成死碼的 `handleCreate`/`form`
    狀態。`CreateBotForm.jsx` 元件檔保留備用。
  - 前端 build + 31 測試綠。（`BotAvatar` 米白徽章在深底下暫未調色，列為後續微調。）

### 新增

- 改版 Phase 2：AI 策略探勘 / 漏斗式海選（模式 A，藍圖見 `docs/redesign/phase-2-ai-recommendations.md`）。
  讓系統幫你做最繁瑣的「海選、回測、算 EV」，把決策權（Deploy）留給你。核心是**漏斗式篩選**
  （funnel）以保護本機算力：
  - 後端 `backend/services/screener.py`：三層漏斗——第一層純 pandas 量能粗篩（最新量 > 近 20 日均量
    × `SCREENER_VOLUME_RATIO`，取量比前 `SCREENER_TOP_N`）；第二層只對 survivors 的新聞標題請本機
    Ollama 打多空情緒分（best-effort，連不上就跳過）；第三層重用 `optimizer.run_auto_backtest`
    挑每檔最佳策略 + EV。純函式 `volume_ratio`/`passes_volume_filter`/`parse_sentiment`/`parse_watchlist`
    好測。
  - 後端 `backend/services/llm.py`：抽出共用 LLM 低階工具（`get_client`/`complete`/`cloud_blocked`
    /`friendly_err`），讓**外送安全閥**只有一份定義；`backend/routers/recommendations.py` 新增
    `GET /ai-recommendations`（依 EV 排序、含漏斗各層統計、5 分鐘記憶體快取，`?refresh=true` 強制重算）。
  - `config.py` / `.env.example` 新增 `SCREENER_WATCHLIST` / `SCREENER_VOLUME_RATIO` / `SCREENER_TOP_N`。
  - 前端 `components/RecommendationsPanel.jsx`：「AI 探勘」分頁，海選結果渲染成卡片（EV 當頭條 +
    勝率/回撤 + 情緒燈號），「一鍵部署」重用既有 `createBot` + `startBot`（全程 Paper）；`api.js` 加
    `getRecommendations`、`App.jsx` 加分頁與 `handleDeploy`。
  - 測試：後端 `tests/test_screener.py` 7 測試（純函式 + API 整合）。後端 88 綠、前端 31 綠。

- 改版 Phase 1：圖表引擎換成原生 `lightweight-charts`（藍圖見 `docs/redesign/phase-1-charting.md`）。
  廢除 TradingView `<iframe>` widget，改用資料雙向綁定的原生蠟燭圖，讓後端算出的風控水位線能直接畫
  在圖上。內容：
  - 後端新增 `GET /bars/{symbol}?days=&source=`（`backend/routers/bars.py`，重用 `market_data.get_bars`，
    `_to_candles` 純函式把 DataFrame 轉成 lightweight-charts 的 candle 陣列、跳過 NaN）；`/bots` 清單
    加 `avg_entry_price`（best-effort 查 Alpaca 持倉，空手/離線回 None，給圖表畫進場線/止損線）。
  - 前端新增 `LightweightChart.jsx`（v5 `addSeries(CandlestickSeries)`、`ResizeObserver` 自適應、接
    `useLiveQuote` 即時更新最後一根 K 棒、`priceLines` prop 畫水位線）；`utils/priceLines.js`
    （`buildBotPriceLines` 依 Bot 風控算進場均價/止損/追蹤止盈三條線、`findBotForSymbol` 配對）；
    `components/ChartGrid.jsx`（2x2 多視窗網格，每格自帶代號輸入與水位線）；`api.js` 加 `getBars`。
  - K 線分頁加「單一 / 2x2 四格」佈局切換（`App.jsx`）。
  - 測試：後端 `tests/test_bars.py` 3 測試（純函式 + API 整合），前端 `utils/priceLines.test.jsx`
    7 測試。後端 81 綠、前端 31 綠。舊 `TradingViewChart.jsx` 已無人引用（暫留）。

- 改版藍圖文件 `docs/redesign/`：把根目錄 `需求更新.md`（AI 驅動量化交易終端機需求）深化、對齊
  專案現況、拆成 4 個可獨立施工的階段。`README.md`（總藍圖：核心需求/設計 Why/成本算力/**現況 vs
  需求缺口對照表**，標出每項可重用的既有檔案）、`phase-1-charting.md`（lightweight-charts 換掉
  TradingView iframe + 水位線 + 網格）、`phase-2-ai-recommendations.md`（漏斗式篩選 volume→Ollama
  情緒 + `GET /ai-recommendations` + 探勘分頁 + 一鍵 Deploy）、`phase-3-ui-theme.md`（移除建 Bot
  表單改純監控中心 + 深藍主題）、`phase-4-automation.md`（模式 B：EV 閾值排程自動建 Bot）。純文件，
  尚未動程式；後續一階段一階段改版，各階段完成再更新本檔。

- 全自動掃描最佳策略（一鍵最強）：使用者只要選股票按一顆按鈕，程式自己把「8 種策略 ×
  各自參數網格」全跑一遍，依期望值 EV 排名挑出冠軍。後端 `backend/services/optimizer.py`
  （`PARAM_GRIDS` 各策略參數網格、`run_auto_backtest()`；關鍵效能設計：歷史資料只抓一次，
  所有組合共用同一份 df 跑 `backtest_engine._run_on_df`，不重複連線）、
  `backend/routers/backtest.py` 新增 `POST /auto-backtest`（每個策略的最佳組合各存一筆
  `BacktestRun`、全場冠軍標記 `is_good=True` 進好策略榜，回完整排行榜摘要）。前端
  `components/AutoBacktestPanel.jsx`（冠軍金色強調卡 + 完整 EV 排行榜，自管狀態）、
  `api.js` 新增 `autoBacktest()`，掛在儀表板分頁。無新增資料表（沿用 `BacktestRun`，免遷移）。

### 變更

- 前端視覺改版為「精緻淺色金融」風（像高級財經刊物 / 私人銀行對帳單）：拿掉霓虹發光與
  玻璃模糊，改走乾淨白卡 + 髮絲線邊框 + 大方留白 + 襯線標題的安靜高級感。字體換 Fraunces
  （襯線大標）/ Manrope（內文）/ IBM Plex Mono（金融數字），色調收斂為森林綠主色 + 黃銅金
  點綴 + 漲綠跌紅。改動：`theme.js`（重寫主題，沿用 `NEON` 匯出名以免動既有 import）、
  `index.css`（米白底 + 暖色光暈 + 進場浮現動畫）、`index.html`（換字體）、`Header.jsx`
  （襯線字標 + 金色菱形標記）、`App.jsx`（主容器進場動畫）。
- Bot 頭像重新設計：由「霓虹深色 NFT 風」改為「米白徽章 / 紀念幣」風——暖白紙感圓底 +
  墨線勾勒幾何小機器人 + 單一典雅點綴色（`BotAvatar.jsx`，維持 seed 雜湊決定部件的隨機但
  固定特性）。

- 基本面 / 財報 / 新聞（yfinance）：前端新增「基本面」分頁，查股票代號即顯示公司基本資料
  （市值/PE/EPS/產業/簡介…）、財報三表（損益/資產負債/現金流，可切年度/季度）、配息與分割
  歷史、相關新聞。後端 `backend/services/fundamentals.py`（抽出 `_clean`／`_statement_to_records`
  ／`_normalize_news` 純函式，處理 NaN/numpy/Timestamp 不能進 JSON 的問題、相容新舊版 yfinance
  新聞結構）、`backend/routers/fundamentals.py`（`GET /fundamentals/{symbol}` 及
  `/financials`(?period=annual|quarterly)、`/news`、`/actions`）。前端
  `components/FundamentalsPanel.jsx` + `utils/number.js`（大數字縮寫 T/B/M/K）。附
  `tests/test_fundamentals.py` 6 測試、`utils/number.test.jsx` 5 測試。後端 75 綠、前端 24 綠。

- 即時報價 WebSocket 推送：前端 K 線圖分頁新增即時報價，價格依漲/跌變色、即時跳動。
  架構為「後端單一連線 → 扇出多個前端」（避開 Alpaca 免費版一帳戶一連線限制）：
  後端 `backend/services/quote_stream.py`（`QuoteHub`：訂閱簿記 + 背景輪詢，沒人看時自動停、
  用 `asyncio.to_thread` 拉價不阻塞迴圈）、`backend/routers/quotes.py`（WebSocket `/ws/quotes`
  + 一次性 `GET /quotes/{symbol}`）。前端 `hooks/useLiveQuote.js`（含斷線自動重連/退訂）、
  `components/LiveQuote.jsx`、`utils/quote.js`。採「輪詢+WS推送」版（穩、收盤不會像當機），
  資料源已抽象，未來可無痛換成 Alpaca 真 tick 串流而前端不動。輪詢間隔由 `QUOTE_POLL_INTERVAL_SEC`
  設定（預設 5 秒）。附 `tests/test_quotes.py` 4 測試（訂閱簿記 3 + WebSocket 推送整合 1）、
  `utils/quote.test.jsx` 6 測試。後端 69 綠、前端 19 綠。

- 第二資料源 yfinance（OpenBB 輕量替代）：原想裝 OpenBB，但實測其 core 要求 `fastapi ^0.128.0`
  會頂升本專案鎖的 `fastapi==0.121.2`、且整包拉幾十個 provider 擴充，風險高。改裝免金鑰的
  `yfinance==1.4.1`（OpenBB 底層也用它），寫成與 `alpaca_client.get_bars` **完全同契約**的
  `backend/services/yfinance_client.py`（含可離線測試的純函式 `_normalize`）。新增
  `backend/services/market_data.py` 當資料源分派器（`source="alpaca"`（預設）/`"yfinance"`）。
  回測接上：`run_backtest` 加選填 `source` 參數、`POST /backtest` 請求模型加選填 `source`，
  **預設仍走 Alpaca、向後相容**；Bot 即時交易路徑不動（先研究、不碰下單）。附
  `tests/test_yfinance_client.py` 3 測試（欄位契約／排序索引／空資料）。
### 安全

- **LLM 外送閘 `LLM_ALLOW_CLOUD`（預設 false）**：助手會把策略方案/回測歷史/探討筆記
  注入 prompt，若 `LLM_BASE_URL` 指向外部雲端，這些資料就會送出本機。仿實盤雙閘精神，
  預設只允許本機（localhost/127.0.0.1）；用雲端供應商須明確設 `LLM_ALLOW_CLOUD=true`。
  非本機且未開閘時 `/chat`、`/chat/postmortem` 直接 400 擋下（`chat.py` `_cloud_blocked`）。

### 變更

- `.claude/settings.json`（機器專屬，含 `bgIsolation`）移出版本控管：改放
  `.claude/settings.local.json`、`.gitignore` 加 `.claude/settings.json`／`settings.local.json`。

### 文件

- README 全面更新至現況：技術棧補 Alembic／Discord、進度表改為 Phase 1–4 ✅
  並新增 Phase 5（規劃中），策略 4→7 種、API/專案結構/測試指令對齊現況。
- CLAUDE.md 開發階段表：Phase 3／4 標完成、新增 Phase 5 列。
- 新增 `docs/roadmap-strategy-workbench.md`：Phase 5 設計藍圖（策略產生 Skill、
  右側策略工作台 + Python 一鍵回測 + 期望值 EV 最優、Claude 思考助手讀回測歷史變聰明、
  `StrategyPreset`／`BacktestRun` 資料模型、全程 Paper 安全鐵則、建置順序與驗證）。

### 新增

- Phase 5—探討（檢討）檔案記憶：路標索引 + 內容檔。新增 `backend/services/explorations.py`，
  把思考助手每次事後檢討寫成 `explorations/run-XXXX-策略-標的.md`，並用 `explorations/INDEX.md`
  當「路標索引」（探討主檔案）。`/chat/postmortem` 改成**兩段式**：先讀路標讓模型挑相關的過去
  探討（挑檔失敗自動回退：同策略優先、再取最近）→ 讀那幾篇內容 → 再寫新檢討；接著寫回探討檔
  + 更新路標 + 存 DB 摘要。`/chat` 一般對話也注入路標當提示。**防路徑穿越**（只准讀資料夾內
  的 .md）。檔案為知識主體、進 git、用 run_id 連結，不動 DB schema。附 `tests/test_explorations.py`
  5 測試（寫檔往返／同 run_id 不重覆／防穿越／路標解析／回退挑檔），`tests/` 全套 62 綠。

- Phase 5 步驟 5—思考助手改用本機 LLM（OpenAI 相容，預設 Ollama，完全免費）：因付費考量，
  從 Anthropic 付費 API 改成 **OpenAI 相容介面**，預設指向本機 Ollama；換供應商（Gemini／Groq…）
  只改 `.env` 三行（`LLM_BASE_URL`／`LLM_API_KEY`／`LLM_MODEL`），程式不動。`config.py` 加 `LLM_*`
  與 `EXPLORATIONS_DIR`；`requirements.txt` 換 `openai==2.40.0`（移除 anthropic）；`.env.example`
  列出 Ollama／Gemini／Groq 三種設定。捨棄 tool-use，改成**預先注入回測歷史**（小型/本機模型更穩）。
  未設定 LLM 或連不上 → 優雅回 400 + Ollama 啟動提示，不崩潰。附 `tests/test_chat.py` 4 測試。

- Phase 5 步驟 4—前端策略工作台（先不接 Claude）：新增右側面板
  `components/StrategyWorkbench.jsx`，可收合（收合剩細邊條）、可橫向拖曳拉寬
  （左緣 6px 把手，寬度 clamp 320–720，記 localStorage），玻璃風 + NEON 青。
  四分區：①策略方案（presets 新增/改名/調參/收藏/刪除）②一鍵回測結果卡
  （**EV 當頭條**，EV<0 提示檢討）③回測歷史（依 EV 排序、收藏標星）④Claude 助手聊天區
  （每筆回測「總結這次錯在哪」按鈕）。`App.jsx` 外層改橫向 flex（左主內容 flex:1
  + 右工作台）。`api.js` 加 presets／backtest-runs／sendChat／postmortem 呼叫。
  後端新增 `routers/chat.py`：`POST /chat`、`POST /chat/postmortem` 先回 **stub**
  （步驟 5 接真 Anthropic API），已掛 `main.py`。前端 build 通過、Vitest 13 綠、
  後端 pytest 53 綠。

- Phase 5 步驟 3—策略方案／回測紀錄資料層 + API：新增 2 張表 `strategy_presets`
  （`StrategyPreset`：可命名策略草稿，CRUD/收藏）、`backtest_runs`（`BacktestRun`：每次
  回測存一筆當 Claude 記憶，含 EV 全套 metrics、`claude_postmortem` 欄位）。走 Alembic
  遷移 `42855ad7c572`（batch 模式，接 head）。新增 `routers/presets.py`：
  `GET/POST/PUT/DELETE /presets`、`POST /presets/{id}/backtest`（Python 跑回測→存紀錄→回
  結果）、`GET /backtest-runs`（**依 EV 由高到低排序**、可篩 favorite）、
  `GET /backtest-runs/{id}`、`PUT /backtest-runs/{id}/favorite`。已掛上 `main.py`。
  附 `tests/test_presets.py` 3 測試（CRUD 往返、404、EV 排序+收藏篩選），`tests/` 全套 53 綠。

- Phase 5 步驟 2—回測引擎加期望值（EV）指標：`services/backtest_engine.py` 的
  `_run_on_df` 在原本（總報酬／最大回撤／勝率／Buy&Hold）之外新增 `num_wins`／
  `num_losses`／`loss_rate_pct`／`avg_win`／`avg_loss`／**`expected_value`（EV／筆）**／
  `expectancy_pct`（EV 佔本金%）／`profit_factor`（總賺/總賠，無虧損回 None）。
  純函式、欄位純增量不破壞既有回傳。附 2 個手算驗證測試（兩輪一賺一賠驗 EV=100、
  無虧損驗 profit_factor=None），`tests/` 全套 50 個全綠。
  選策略改看 EV 不只看勝率（防「高勝率但一次大賠」陷阱）。

- Phase 5 步驟 1—策略產生 Skill（`.claude/skills/strategy-builder/`）：本專案第一個自製
  Skill，依漸進式揭露拆成 `SKILL.md`（5 步流程）＋ `references/`（6 落地點與命名規則、
  避坑清單）＋ `assets/`（策略/文件/測試三骨架）。把「人類講的交易策略」一條龍變成
  已註冊、有文件、有測試的策略模組。
- Phase 5 步驟 1 驗證產物—威廉指標策略 `williams_r`（`WilliamsRStrategy`）：純 pandas
  自算 Williams %R（用 close 近似高低點），超賣(<-80)買、超買(>-20)賣、資料不足/無波動
  HOLD。完成 6 落地點（策略檔＋註冊＋前端 `constants.js`＋`docs/strategies/williams_r.md`
  ＋`tests/test_williams_r.py` 3 情境）。`tests/` 全套 48 個全綠。

- Phase 4 收尾—監聽狀態前端可視化：`models/bot.py` 新增 `last_checked_at`，
  `bot_manager` 每輪成功檢查後更新（新增 `_mark_checked`）。`GET /bots` 回傳值加上
  `peak_price`／`last_checked_at`。前端 Bot 卡片新增一行「持倉中·峰值 $X · N 秒前檢查」
  （`utils/botStats.js` 加純函式 `formatCheckedAgo`／`holdingText`，附 6 個前端測試）。
  附 Alembic 遷移 `b2c3d4e5f6a7_add_bot_last_checked_at`。
- Phase 4 收尾—通知擴充 Discord：`services/notifier.py` 重構成多管道（LINE + Discord），
  各管道獨立、任一失敗不影響其他。Discord 走最簡單的 Webhook（`DISCORD_WEBHOOK_URL`，
  `.env.example` 已補欄位說明），沒設定就靜默跳過。附 3 個測試（mock requests，不真發）。

### 文件

- 新增 `docs/phase4-paper-checklist.md`：Phase 4 Paper 連續實跑驗收清單，
  涵蓋排程／開市判斷／風控出場／重啟恢復／通知／績效／多 Bot 並發，逐項「預期 vs 實際」打勾。
- 新增 `docs/financial-services-reference.md`：摘錄 Anthropic `financial-services`
  repo 對本專案有用的部分（Skill 寫法、slash command 模式、選股篩選條件、
  未來 AI 輔助層方向）。完整副本放本機 `D:\reference\`，不納入 git。

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
