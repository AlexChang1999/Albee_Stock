# Phase 16 — 短線 Swing / Intraday 轉型（M1~M12 藍圖 + 進度）

> **開工前必讀**：[`docs/ai-implementation-guardrails.md`](../../ai-implementation-guardrails.md)。
> 一次一個里程碑、對齊原目標、pytest 全綠 + CHANGELOG 才進下一個。
> 所有「挑冠軍 / 設門檻」一律 walk-forward OOS + 含成本 + 次根 bar 開盤成交（回測=實盤鐵則）。

## 原目標錨點

使用者 2026-07-02 需求（15 階段）：系統從「日線波段」轉型為「短線 swing / intraday swing」。
核心約束：
- 不預設哪個 timeframe / stop / R:R 最好——**全部回測，用 OOS 數據說話**。
- AI 決策層必須**可回測、可重現、可量化**，不可覆蓋核心策略訊號（只能否決/縮量/調出場）。
- 加不了分的層砍掉也是成果（比照 Phase 11 macro 層誠實砍除前例）。
- 失鎖行為：**只停新單、不自動平倉**（持倉靠券商端 GTC 保護單）。

## 進度總表

| 里程碑 | 內容 | 狀態 |
|--------|------|------|
| M1 | 選主鎖修復（租約制 + 定期驗鎖 + 下單第三閘 + 自動升降級） | ✅ 2026-07-02 完成 |
| M2 | 多 timeframe 資料地基（1Min~1Day 全鏈貫穿，預設 1Day 零改動相容） | ✅ 2026-07-02 完成 |
| M3 | Optimizer walk-forward 聚合 OOS + 排行榜擴充 + 排名守門 | ✅ 2026-07-02 完成（前端欄位顯示留 M3.5） |
| M3.5 | 前端 BacktestRuns / StockArena 顯示新欄位 | ⬜ 未開工 |
| M4 | 可插拔 ExitPolicy（ATR / Swing / VWAP stop + R:R） | ⬜ 未開工 |
| M5 | 進場趨勢過濾器框架（EMA 排列 / VWAP / ADX / HH-HL / BOS / regime） | ⬜ 未開工 |
| M6 | 大型研究矩陣批跑（timeframe × stop × R:R × filter 全比較） | ⬜ 未開工（長跑任務） |
| M7 | RS 模組 + 股票池 38→15~20 瘦身 | ⬜ 未開工 |
| M8 | Scanner 30 秒改造（單一掃描迴圈批次抓全池） | ⬜ 未開工（依賴 M6 定案 timeframe） |
| M9 | 4 支報告腳本進 scheduler（每週一自動健康檢查） | ⬜ 未開工 |
| M10 | AI Decision Layer（規則式可回測 entry gate + 動態出場） | ⬜ 未開工 |
| M11 | 資金流因子 60 天滿期 OOS 驗證（無加分即砍） | ⬜ 等收集滿（起算 2026-07-02 前後，約 2026-09 初到期） |
| M12 | 最終報告（timeframe/stop/R:R 比較 + 過擬合分析 + 上線組合建議） | ⬜ 未開工 |

---

## 已完成細節（M1~M3，2026-07-02）

### M1 選主鎖修復（唯一真金風險）

問題：舊版 PG session advisory lock 只在開機檢查一次；Neon 掐斷 idle 連線 → 鎖被悄悄釋放
→ 雙 leader 重複下單。

解法（租約制）：
- 新表 `scheduler_lease`（單列 id=1；holder_id/hostname/acquired_at/expires_at）。
  遷移 `2768500820b2`（此 rev 同時修復 Neon 幽靈 rev——某機器先建了表沒 commit 遷移檔，
  本檔用同 id 補建血緣）。
- `backend/services/scheduler_lock.py` 重寫：原子 UPDATE 搶租約（TTL 90s）、leader 每 30s
  續約驗鎖、失鎖**先立旗擋單**再卸排程、follower 每 30s 嘗試接手自動升級。
  時間用 DB 時鐘 UTC（`_db_now`），多機時鐘不同步不誤判。
- `alpaca_client._assert_live_allowed` 內加**第三閘** `assert_leader()`：非 leader 一律拒單
  （與實盤雙閘並列；SQLite 單機恆通過）。
- `main.py` lifespan 重構：leader-only 排程區塊抽成 `_promote_to_leader()`；
  無論輸贏都掛 lease daemon → VM 重啟後 TTL 內自動接手，零人工。
- `bot_manager.unschedule_outbound_jobs()`：降級時卸下所有對外 job，只留租約守護。
- 測試 `tests/test_scheduler_lock.py`：12 個（互搶/續約/過期接手/讓位/第三閘/升降級）。

### M2 多 timeframe 資料地基

支援 `1Min/5Min/15Min/30Min/1Hour/2Hour/4Hour/1Day`，預設 `"1Day"` 零改動相容：
- 新 `backend/services/timeframes.py`：單一事實來源（合法 key、年化基數
  `periods_per_year`、`bars_to_calendar_days`）。
- `alpaca_client.get_bars/get_bars_multi(+timeframe)`：映射 `TimeFrame(amount, Unit)`。
- `yfinance_client(+timeframe)`：interval 映射 + 歷史上限超限**誠實拋錯**
  （1m 僅 7 天、5m~30m 60 天、1h 730 天、無 2h/4h）。
- `market_data` 透傳；`bar_cache` 路徑加 timeframe 維度（1Day 沿用舊路徑零遷移；
  日內另存 `{source}/{timeframe}/`），日內「今天」永遠視為尾缺口重抓（盤中新 bar 進得來）。
- `lookback.required_lookback_bars` + `required_lookback_days(+timeframe)`。
- `analytics.extended_metrics(+timeframe)`：Sharpe/Sortino/波動用對年化基數；
  日內 calmar/cagr 誠實回 None（假日期索引會失真）。
- `backtest_engine.run_backtest(+timeframe)`：日內一律 alpaca 源；
  `_simulate_from_signals` 零改動（「次根 bar 開盤成交」語意自然泛化）。
- `bots.timeframe` 欄位（Alembic `d0d0c19d13b0`，server_default "1Day"）；
  `bot_manager._run_strategy` 實盤抓資料用 Bot 自己的 timeframe（回測=實盤鐵則）；
  `_drop_unclosed_today_bar` 泛化：日內盤中砍最後一根未收完 bar。
- 測試 `tests/test_timeframes.py`：12 個。

### M3 Optimizer walk-forward + 排行榜擴充

- `run_auto_backtest(+timeframe, +walk_forward=True)`：用既有 `validation.walk_forward_splits`
  滾動切分，`_wf_aggregate` 把**所有 fold 的 OOS round trips 串接聚合**
  （EV=總損益/總筆數、勝率、PF=總賺/總賠、MaxDD 取各 fold 最差、
  Sharpe/Sortino 由串接報酬重建 equity 算）。資料太短湊不出 fold → 誠實退回單次切分。
- 新欄位：`overfit_gap =(IS−OOS)/|IS|`（IS≤0 回 None）、`oos_num_round_trips`（跨折加總）、
  `oos_folds / oos_sharpe / oos_sortino / oos_profit_factor / oos_max_drawdown_pct`、
  `oos_avg_r_multiple`（留 None，M4 有 stop 資訊後回填）。
- **排名守門**（config：`OPTIMIZER_MIN_OOS_TRIPS=20`、`OPTIMIZER_MAX_OVERFIT_GAP=0.5`）：
  OOS 樣本不足或過擬合差距過大的組合直接沉底——回應「38 檔中 32 檔 OOS 樣本 1~2 筆
  是噪音」的教訓。
- `routers/backtest.py`：`AutoBacktestRequest` 加 timeframe/walk_forward；
  `_entry_summary` 回傳全部新欄位。BacktestRun.metrics 是 JSON，**無需遷移**。
- 測試 `tests/test_optimizer_walkforward.py`：6 個（聚合數學/gap 邊界/舊路徑相容/守門）。

---

## 待辦計畫書（M3.5~M12 —— 每節可直接當下個 session 的提示詞）

### M3.5 前端補顯示新欄位（半 session）

> 提示詞：BacktestRuns / StockArena / AutoBacktestPanel 顯示 M3 新欄位。
> 後端 `/auto-backtest` 的 `_entry_summary` 已回傳 `overfit_gap / oos_num_round_trips /
> oos_folds / oos_sharpe / oos_sortino / oos_profit_factor / oos_max_drawdown_pct / timeframe`。
> 改 `frontend/src/pages/StockArenaPage.jsx`、`BacktestRunsPage.jsx`、
> `components/AutoBacktestPanel.jsx`：排行榜表格加欄（Gap 用顏色警示：>0.5 紅）。
> 加 timeframe 下拉選單（選項取後端 `services/timeframes.py ALL_TIMEFRAMES`，
> 可硬列同一份清單於 `constants.js`）。顏色一律吃 theme/NEON，勿寫死 hex。
> 元件測試同層 `*.test.jsx`（Vitest+RTL）比照既有。

### M4 可插拔 ExitPolicy（一次 session）

> 提示詞：把「固定 % 止盈損」泛化為可插拔出場政策，回測與實盤共用同一份程式碼。
>
> 新 `backend/services/exit_policies.py`：
> ```python
> @dataclass
> class ExitPlan:
>     stop_price: float | None
>     target_price: float | None
>     trailing_pct: float | None
>     meta: dict  # 記依據（atr 值、swing low 位置…）供 DecisionLog
>
> class ExitPolicy(ABC):
>     key: str
>     def on_entry(self, df, i, entry_price) -> ExitPlan: ...
>     def on_bar(self, df, i, plan, state) -> ExitPlan: ...  # 預設回原 plan（M10 動態出場掛點）
>
> EXIT_POLICY_REGISTRY = {
>     "fixed_pct": FixedPctPolicy,   # 包既有行為（回歸基準，結果需與舊參數路徑全等）
>     "atr":       AtrStopPolicy,    # stop = entry − k×ATR(n)；target = entry + rr×k×ATR
>     "swing":     SwingLowPolicy,   # stop = 近 N 根 swing low − buffer
>     "vwap":      VwapStopPolicy,   # 日內：跌破 session VWAP 出場（僅日內框架）
> }
> ```
> R:R 內建：`target = entry + rr_multiple × (entry − stop)`，rr_multiple 為政策參數
> （之後 M6 掃 1.5/2/2.2/2.5/3/4）。Volume Profile stop **延後**（實作成本高，
> 先跑三種，M6 數據顯示不足再議）。
> - swing 高低點偵測放 `backend/strategies/indicators.py`（M5 BOS/HH-HL 共用，勿重造）。
> - `backtest_engine._simulate_from_signals(+exit_policy)`：逐 bar 檢查
>   `low ≤ stop → 以 stop 價成交（跳空穿越用 open，保守）`、`high ≥ target → target 價成交`，
>   含滑價；同一根同時破兩邊 → 保守先算 stop。既有 stop_loss_pct 等參數轉接 FixedPctPolicy。
> - 每筆交易記「初始風險 R = entry − stop」→ 回填 M3 的 `oos_avg_r_multiple`
>   （= 平均每筆損益 / R）。
> - 實盤側：`risk_manager.check_exit` 改吃同一 ExitPolicy；Bot 模型加
>   `exit_policy_key / exit_policy_params`（Alembic）；`protective_orders` 的 GTC stop 價
>   由 `ExitPlan.stop_price` 供給（自癒對帳沿用）。
> - 測試：各 policy 數學、intrabar 觸發順序、fixed_pct vs 舊路徑 bit-for-bit 回歸。

### M5 進場趨勢過濾器框架（一次 session；OOS 驗證屬 M6）

> 提示詞：新 `backend/services/trend_filters.py`：
> ```python
> class TrendFilter(ABC):
>     key: str
>     def allow_entry(self, df, i) -> tuple[bool, str]: ...
>
> FILTER_REGISTRY = {
>   "ema_stack",  # EMA20>EMA50>EMA200 多頭排列（EMA 用 pandas ewm）
>   "vwap_side",  # 價在 session VWAP 上（日內框架專用；日 K 回 True + reason 註明不適用）
>   "adx_min",    # ADX ≥ 門檻（復用 strategies/indicators.adx_components）
>   "hh_hl",      # 近 N swing 高低點 HH-HL 結構（復用 M4 swing 偵測）
>   "bos",        # break of structure：收盤突破前 swing high
>   "regime",     # 復用 services/regime.classify_regime == trending 才進
> }
> ```
> 訊號層掛點：`_run_on_df` / `_simulate_from_signals` 上游加
> `entry_filters: list[TrendFilter] | None`；BUY 被否決 → 記 HOLD + reason
> （實盤側進 DecisionLog，語意同 meta_label 否決）。
> 目的：避免下跌抄底 / 盤整被洗 / 空頭做多。**只建框架 + 單元測試**；
> 哪個 filter 上線由 M6 的 `layer_validation.is_layer_worth_it` OOS 判定，
> 加不了分就砍。

### M6 大型研究矩陣批跑（長跑任務，數小時~數天）

> 提示詞：新 `scripts/research_matrix.py`（唯讀分析 CLI，不下單）+
> `scripts/warm_cache.py`（分鐘 K 批次預熱）。
>
> 維度全積 timeframe(8)×strategy(11)×filter(7)×exit(4)×rr(6)×symbol(38) ≈ 10^5 不可全掃，
> 分三輪漏斗：
> 1. **Round 1 timeframe 海選**：全策略 × 全 timeframe × 無 filter × fixed_pct baseline，
>    walk-forward 聚合 OOS 排名 → 每 timeframe 留前 3 策略。
>    ⚠️ 先跑**核心 6 檔**（AMD/AVGO/INTC/ORCL/BAC/MS，stock_pool 體檢已證實）驗證
>    IEX 分鐘 K 資料品質（稀疏 bar 比例），品質 OK 再擴全池；
>    品質差 → 回報使用者決定是否上付費數據（Algo Trader Plus $99/月），先免費驗證不預付。
> 2. **Round 2 stop × R:R**：Round 1 存活組合 × 4 exit policies × rr∈{1.5,2,2.2,2.5,3,4}。
>    同時比較出場方式四型：只 SL / 只 Trailing / SL+Trailing / SL+Target(R:R)。
> 3. **Round 3 filter**：Round 2 冠軍 × 6 filters，逐層 `is_layer_worth_it` 判去留。
> - 預熱注意：200 req/min token bucket；38 檔 × 分鐘 K 多年要分批多小時抓，
>   `warm_cache.py` 支援斷點續跑（bar_cache 本身冪等）。
> - 結果落 `BacktestRun`（metrics JSON 加 `study_tag`）+ markdown 摘要進
>   `docs/reference/analysis-<日期>/` 與 explorations/。
> - 報表凡「日內多次進出」組合自動標註 **PDT**（實盤 <$25k 受限；paper 不受影響）。
> - 每輪產出後停下來給人看，再跑下一輪（人在迴路）。

### M7 RS 模組 + 股票池瘦身（半 session 程式 + 跑批）

> 提示詞：新 `backend/services/relative_strength.py`：
> `rs_score(symbol_df, benchmark_df, lookback_bars) -> float`
> （把 `scripts/fund_flow_report.py` 的「報酬 − SPY 報酬」邏輯泛化到個股，1/5/20 日多窗口）。
> 新 `backend/services/sectors.py`：38 檔手工 sector dict（半導體：NVDA/AMD/AVGO/TSM/
> INTC/QCOM/MU/AMAT/LRCX/ASML；能源：XOM/CVX/COP；金融：JPM/BAC/WFC/GS/MS…），
> yfinance sector 補洞。
> 擴充 `scripts/stock_pool_report.py`：walk-forward 聚合 OOS 排名 + **同 sector 只留
> RS 最強 3~4 檔** → 產出 15~20 檔建議清單（附完整依據表）。
> ⚠️ 只產建議，**人核准後才改 `.env AUTO_DEPLOY_KNOWLEDGE_SYMBOLS`**（人在迴路）。

### M8 Scanner 30 秒改造（一次 session；依賴 M6 定案 timeframe）

> 提示詞：掃描改「單一掃描迴圈」不是每 bot 各抓：
> - 現況：每 bot 一個 interval job 各自 get_bars → 30s × 38 bot = 76+ req/min 起跳，撞 200 上限。
> - 改法：`bot_manager` 一個 30s job → `market_data.get_bars_multi` 一次抓全池（1 req/scan
>   ≈ 2 req/min）→ 逐 bot 派發訊號評估。既有 per-bot job 保留給 1Day bot（300s 甜蜜點不變）。
> - 進場訊號**只用已收完 bar**（分鐘 K 一分鐘才一根新的；30s 掃的價值在出場管理）；
>   最新價走既有 `quote_stream.py` WebSocket，不耗 REST 配額。
> - 不需 async 重寫：APScheduler + 批次抓已足。VM 上量測單輪耗時（目標 <5s）+ CPU 記錄進報告。

### M9 報告腳本進 scheduler（半 session）

> 提示詞：4 支報告腳本（full_backtest_report / fund_flow_report / stock_pool_report /
> scan_frequency_study）各重構出 `run() -> str`（回 markdown 摘要）可呼叫介面，CLI 殼保留。
> `bot_manager.schedule_weekly_reports(...)`：每週一 08:00（台北）依序跑，
> 摘要走 `notifier.notify` 推播、全文落 `docs/reference/analysis-<日期>/`。
> 掛在 `main.py _promote_to_leader()`（leader-only）。heartbeat 沿用不動。
> 注意 cp950：報表寫檔一律 `encoding="utf-8"`。

### M10 AI Decision Layer（一次 session 框架 + 長跑驗證）

> 提示詞：規則式、可回測——**不用 LLM 即時喊單**。
> 新 `backend/services/decision_layer.py`：
> - `entry_score(df, i) -> DecisionVerdict(action: enter|skip|half_size, score, reasons)`。
>   特徵全部復用既有：ATR%（regime_features）、ADX（indicators）、volume z-score、
>   momentum、regime 信心（meta_label）。規則參數化、可進 PARAM_GRIDS 掃描。
> - 動態止盈損 = 實作 M4 的 `AdaptiveExitPolicy.on_bar()`：
>   波動率升 → 收緊 trailing；ADX 走強 → 放寬 target 續抱；動能衰竭（momentum 轉負
>   + 量縮）→ 提前出場。每次調整記進 `ExitPlan.meta`（可稽核）。
> - 上線判準：`layer_validation` baseline（無 layer）vs candidate（有 layer）
>   `is_layer_worth_it` OOS 過了才掛實盤。**AI 只能否決/縮量/調出場，不可反向、
>   不可覆蓋核心策略訊號**（與 meta_label 同約束）。

### M11 資金流因子驗證（等 60 天滿期）

> 提示詞：`orderflow_proxy` 的 `net_pressure` 累積滿 60 天後，
> 用 layer_validation 模式驗證「加資金流 gate」是否 OOS 加分：
> baseline = 無 gate，candidate = net_pressure 連續 N 日淨買壓才准進場。
> `is_layer_worth_it` 不過 → **直接移除因子收集**（比照 Phase 11 macro 層誠實砍除）。

### M12 最終報告（彙整）

> 提示詞：新 `scripts/final_report.py` 聚合 M6/M7/M10 產出，輸出使用者要的 13 項：
> 架構修改摘要、修改檔案清單、回測流程、walk-forward 結果、OOS 統計、
> timeframe 比較（1m~4h+1Day）、stop strategy 比較、R:R 比較、股票池縮減依據、
> 半導體 RS 篩選結果、scanner 效能分析、IS vs OOS 過擬合分析、
> **最終建議上線組合（策略×參數×timeframe×filter×exit×池，含 PDT 標註）**。
> 落 `docs/reference/analysis-<日期>/final-report.md` + explorations。

## 依賴順序

```
M3.5（獨立）    M4 ──→ M5 ──→ M6（長跑）──→ M8、M12
                M4 ──────────→ M10（驗證段跟 M6 一起跑）
M7（依賴 M3，已就緒）    M9（獨立）    M11（等 2026-09 滿期）
```

## 給下個 session 的開場提示詞

> 讀 `docs/history/phase-16-intraday-swing/README.md`（本檔）與
> `docs/ai-implementation-guardrails.md`，接續 Phase 16：M1~M3 已完成，
> 從 M3.5 + M4 開始（或依使用者指定）。每個里程碑完成後跑
> `venv\Scripts\python.exe -m pytest tests/ -q` 全綠 + 更新 CHANGELOG +
> 更新本檔進度表，才進下一個。
