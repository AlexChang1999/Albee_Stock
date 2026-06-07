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

- **Phase 7 step-04~06：分數凱利部位 + meta-labeling 二級過濾 + 事件驅動風險閘**——藍圖 [`docs/phase-7-adaptive-regime/`](docs/phase-7-adaptive-regime/README.md)。
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

- **Phase 7 step-07：★防過擬合驗證框架（橫跨全部的鐵律）**——藍圖 [`docs/phase-7-adaptive-regime/step-07-anti-overfitting-validation.md`](docs/phase-7-adaptive-regime/step-07-anti-overfitting-validation.md)。
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

- **Phase 7 step-01~03：自適應市場狀態（區塊 2：狀態→選策略）**——藍圖 [`docs/phase-7-adaptive-regime/`](docs/phase-7-adaptive-regime/README.md)。
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
