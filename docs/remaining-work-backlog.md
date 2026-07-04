# 未完成工作 Backlog（餵 AI 實作用，完整詳細步驟）

> 本檔是 Albee Stock 主線 Phase 1~11 + redesign 子軌全完成後，剩餘未做工作的單一真相來源。
> 每項寫到「可直接餵 AI 照做」的詳細度：現況 / 檔案路徑 / 函式簽章 / step / DoD / 測試指令。
>
> **任何 AI（或人）拿本檔開工前，必讀並遵守** [`ai-implementation-guardrails.md`](ai-implementation-guardrails.md)：
> 一次一步、永遠對齊原目標、收工對 DoD、更新 `CHANGELOG.md`。
>
> 通用鐵則（節錄，全項適用）：
> - **絕不** commit `.env` / API key；所有交易先走 **Paper**，不碰實盤雙閘（`ALPACA_BASE_URL` 實盤網址 + `ALLOW_LIVE_TRADING=true`）。
> - DB schema 變更**只走 Alembic**（`revision --autogenerate` → 人工檢查 → `upgrade head`），不手動 `ALTER TABLE`；SQLite 已開 `render_as_batch=True`。
> - **「回測=實盤」鐵則**：環境因子只進「訊號層」，成交永遠走次根開盤含成本；挑冠軍/設門檻一律看 OOS。
> - 程式碼加**中文註解**；策略模組鬆耦合；前端顏色吃 `theme.js`（`palette`/`NEON`），**不寫死 hex**。
> - 每次有意義變更更新 `CHANGELOG.md`「未發布」區塊。

最後更新：2026-07-04。狀態基準：`origin/develop`（A/B/C/E/F/G 全完成；H 程式完成剩 2 項人工驗收；D 剩 step-05 兩週觀察）。
完成順序（歷史）：B -> C -> A -> H(程式) -> D(step-01~04) -> E -> F -> G；剩餘：H 人工驗收 2 項 + D step-05 觀察期

---

## 盤點總表（依價值排序）

| # | 項目 | 類型 | 阻塞？ | 價值 |
|---|------|------|--------|------|
| A | Phase 11 macro 層真資料驗證（step-05 收尾） | 驗證/決策 | — | ✅ 已完成（2026-06-11，誠實砍除） |
| B | `/positions` 端點 + 前端持倉/未實現損益卡 | 後端+前端 | — | ✅ 已完成（2026-06-11，`13ef4bb`） |
| C | `test_run_dry_run` pre-existing 失敗修掉 | bugfix | — | ✅ 已完成（2026-06-11，`13ef4bb`） |
| H | 維運安全軌（真錢前必備：券商端止損/心跳/自動降級） | 後端+設定 | 無 | **最高（電腦掛掉直接賠錢的洞）** |
| D | Phase 12：策略自動探勘入庫管線 | 大 feature | 無 | 🔶 step-01~04 已實作（2026-06-11）；step-05 兩週觀察待開跑 |
| E | 前端 UX 零碎：亮色模式/排行榜排序/Skeleton/補測試 | 前端 | 無 | ✅ 已完成（2026-06-11，四項全落地） |
| F | `ui-ux-pro-max` skill CLI（`search.py`/CSV） | 工具 | 無 | ✅ 已完成（2026-06-12，vendor 上游 MIT repo） |
| G | 文件漂移：`workflow-diagrams.md`/`CLAUDE.md` 結構樹停在 Phase 6–7 | 文件 | 無 | ✅ 已完成（2026-06-11，補 Phase 8–11 + 圖 5） |

**建議先做順序**：H（真錢前必備、無阻塞，出自
[`reference/one-person-company-gap-analysis.md`](reference/one-person-company-gap-analysis.md) 第四部分優先序）→ D/E/F/G 依需求挑。

---

## A. Phase 11 macro 層真資料驗證（step-05 收尾）✅ 已完成（2026-06-11）

> **結論：誠實砍除。** 取得 FRED key、灌入真序列（41,604 筆觀測）後，以
> `scripts/validate_layers.py SPY QQQ AAPL MSFT NVDA` 跑 walk-forward：macro 列
> **worth=False、folds=207、Δ=-101.68**（baseline 91.17 → candidate -10.51）。
> 依下方 step 4 的 `worth=False` 分支執行：移除 `MacroOverlayStrategy`/`validate_macro_layer`、
> CLI 取下 macro 列、整檔刪 `tests/test_macro_layer.py`；FRED 資料層保留。
> 詳見 `CHANGELOG.md` 未發布區塊。以下原始步驟留作歷史紀錄。

### 現況
首跑 `scripts\validate_layers.py SPY` 判 macro 層 `worth=False`。原因：未填 `FRED_API_KEY`，
`macro_features` 各欄全 NaN，`MacroOverlayStrategy` 的煞車只剩 orderflow `pressure_ratio<0.5` 在動，
每根下跌都觸發、過度抑制進場 → EV 崩。**這是驗證框架正確殺掉「未證明加分」的層**，非 bug。
要真評估 macro 價值，必須先灌入真 FRED 序列再重跑。

### 涉及檔
- `backend/services/layer_validation.py`（`MacroOverlayStrategy` / `_macro_risk_off` / `_build_features` / `validate_macro_layer`）
- `scripts/validate_layers.py`（CLI 印 macro 列）
- `backend/routers/macro.py`（`POST /macro/refresh` 已存在，行 55）
- `.env`（填 key）

### Step
1. 申請聖路易聯準會免費 key，`.env` 填 `FRED_API_KEY=...`（**絕不 commit**）。
2. 啟後端 `venv\Scripts\uvicorn.exe backend.main:app --reload`，呼叫 `POST /macro/refresh`
   灌入序列（fed funds / unemployment / CPI / yield curve / VIX）；回應 `{"refreshed":..., "total":N}` 確認非 0。
3. 重跑 `venv\Scripts\python.exe scripts\validate_layers.py SPY`（建議再加幾檔大型權值股 / ETF 增加 folds）。
4. 判讀 macro 列 `worth / folds / Δ(improvement)`：
   - **`worth=True`** → 留 `MacroOverlayStrategy`，把 folds/Δ 數據寫進 `CHANGELOG.md` + Phase 11 README step-05 註記。
   - **仍 `worth=False`** → **誠實砍**（沿用 Phase 7「沒加分就砍」紀律）：
     - 從 `layer_validation.py` 移除 `MacroOverlayStrategy` / `validate_macro_layer` 並從 `validate_symbol`/`validate_layers` 取下 macro 池；
     - `scripts/validate_layers.py` 印表迴圈移除 `"macro"`；
     - 調整 `tests/test_macro_layer.py`（保留純函式單測或整檔刪，視保留範圍）；
     - `CHANGELOG.md` 記錄「真資料下仍無加分 → 砍除」決策。

### DoD
- CLI 用**真 FRED 資料**印出 macro 層 verdict（folds≥min_folds）。
- 去留決策落 `CHANGELOG.md`；保留則附數據，砍除則程式/測試/文件同步清乾淨。

---

## B. `/positions` 端點 + 前端持倉卡（最高價值）★ ✅ 已完成（2026-06-11）

> **結論：已落地**（commit `13ef4bb`）。後端 `alpaca_client.list_positions()` +
> 唯讀 `GET /positions`（無金鑰優雅回 `[]`）+ `tests/test_positions.py`；
> 前端 `api.getPositions()` + `PositionsCard.jsx`（含損益符號色、吃 theme）+
> RTL 測試，已掛進 Dashboard。詳見 `CHANGELOG.md`。以下原始步驟留作歷史紀錄。

### 現況
`backend/services/alpaca_client.py:91` 只有 `get_position(symbol)`（單檔，延遲初始化 + try 接住例外回 None）。
**無列出全部持倉的端點**，前端 Dashboard 只看得到帳戶現金/購買力，看不到手上部位與浮動損益。
這是 backlog 中價值最高、無阻塞、Paper 即可驗的缺口。

### Step（後端）
1. `backend/services/alpaca_client.py`：加 `list_positions()`，包 alpaca-py `self.trading.get_all_positions()`，
   仿 `get_position` 樣式（延遲初始化 + try，失敗回 `[]`）。中文註解。
   ```python
   def list_positions(self):
       """列出目前所有持倉。連線/金鑰失敗時回空清單（優雅降級）。"""
       try:
           return self.trading.get_all_positions()
       except Exception:
           return []
   ```
2. 新增 `backend/routers/positions.py`：唯讀 `GET /positions`。把每個 alpaca position 物件映成 dict：
   `symbol / qty / avg_entry_price / current_price / market_value / unrealized_pl / unrealized_plpc`
   （欄位名照 alpaca-py Position 屬性；數字轉 float）。無金鑰/失敗 → 回 `[]`（仿既有 router 降級風格，
   參考 `routers/factors.py` 唯讀端點體例）。
3. `backend/main.py`：`include_router(positions.router)`（仿既有掛載）。
4. 新增 `tests/test_positions.py`：monkeypatch `alpaca_client.list_positions` 回假持倉清單 →
   驗 `GET /positions` 回傳形狀/欄位/數字型別（不連網）。仿 `tests/test_api.py` 的 TestClient 用法。

### Step（前端）
5. `frontend/src/api.js`：加 `getPositions()`（讀 `VITE_API_URL`，仿既有 fetch 包裝）。
6. 新增 `frontend/src/components/PositionsCard.jsx`：表格列出各持倉，浮動損益用
   `utils/number.js` 的 `signedMoney`（行 46）/ `signOf`（行 30）帶 +/- 號 + 漲跌色；
   顏色吃 `theme`/`NEON`，**不寫死 hex**。掛進 Dashboard 頁（`pages/Dashboard*`，放 `AccountCard` 旁）。
7. 新增 `frontend/src/components/PositionsCard.test.jsx`（Vitest + RTL）：假 positions → 驗渲染 + 損益符號色。

### DoD
- `GET /positions` 回各檔部位 + 浮動損益；無金鑰時不崩、回空。
- Dashboard 看得到持倉卡。`pytest tests\test_positions.py -q` 綠；`npm run test`（PositionsCard）綠。
- Paper 模式手動驗：有部位時顯示正確。

### 測試指令
```powershell
venv\Scripts\python.exe -m pytest tests\test_positions.py -q
cd frontend && npm run test
```

---

## C. 修 `test_run_dry_run` pre-existing 失敗 ✅ 已完成（2026-06-11）

> **結論：已修復**（commit `13ef4bb`，與 B 同一 PR）。全測 `pytest tests -q` 0 失敗。
> 以下原始步驟留作歷史紀錄。

### 現況
`tests/test_automation.py::test_run_dry_run` 在 clean develop 上就失敗（`planned=[]`——AAPL
過門檻卻沒進 planned 清單）。與 Phase 11 無關，是「353 過 / 1 失敗」的那 1 個。

### Step
1. 讀 `tests/test_automation.py::test_run_dry_run` + `backend/services/automation.py` 的 dry-run 路徑，
   對照測試的 monkeypatch（回測結果/門檻）與 automation 把候選放進 `planned` 的條件。
2. 釐清是**測試過期**（automation 簽章/門檻/OOS 欄名漂移，測試 stub 沒跟上）還是 **automation 真 bug**。
3. 對應修：測試過期 → 修測試 stub/斷言；真 bug → 修 `automation.py`（守「門檻比 OOS」鐵則）。

### DoD
- `venv\Scripts\python.exe -m pytest tests\test_automation.py -q` 綠。
- 全 `venv\Scripts\python.exe -m pytest tests -q` **0 失敗**（注意：跑 `tests` 目錄，別跑 bare pytest——
  `backend/test_connection.py` 會在 import 時連 Alpaca 並 `SystemExit` 觸發 INTERNALERROR）。

---

## H. 維運安全軌（真錢前必備）★ ✅ 程式已完成（2026-06-11），剩 2 項人工驗收

> **結論：Step 1~7 全部落地**（feature/ops-safety-track 分支，一 step 一聚焦 commit，
> 全套件 397 passed、Alembic 三個遷移已套用）。詳見 `CHANGELOG.md` 未發布區塊。
> **剩餘人工驗收（程式做不了的）**：
> 1. **H1 Paper 端到端驗證**：開市時建一隻帶 stop_loss 的 Bot 跑一輪 → Alpaca 後台
>    看到 GTC stop 單 → 殺後端進程確認單仍掛著 → 重啟確認不重複掛。
> 2. **H2 dead-man 接線 + 演練**：到 healthchecks.io 註冊、ping URL 填 `.env`、
>    照 [`guides/deadman-switch-runbook.md`](guides/deadman-switch-runbook.md) 演練一次
>    （停後端 2 小時收到警報才算數）。
> 以下原始契約留作歷史紀錄。

> 出自 [`reference/one-person-company-gap-analysis.md`](reference/one-person-company-gap-analysis.md)
> 第三/四部分：缺口 1（止損掛本機輪詢最危險）、缺口 2（無心跳監控）、缺口 3+4（有晉升沒降級、
> 無 tracking error 對帳）。三條鏈彼此獨立：H1（Step 1→2→3）、H2（Step 4→5）、H3（Step 6→7）。
> 設計決策與完整 step 契約見本節；一 step 一聚焦 commit。

### H1. 券商端止損（Step 1~3）——電腦掛掉止損仍有效

**設計**：券商端為主、本機為備。進場仍走 `submit_market_order`（市價、雙閘不碰），
成交後另掛一張 **GTC 保護賣單**：`trailing_stop_pct` 有設用 Alpaca 原生 trailing stop
（`trail_percent`，券商端自追盤中最高價）；否則 `stop_loss_pct` 用 stop 單。
本機 `check_exit` 保留當備援；本機出場**先撤保護單再賣**（撤不掉＝券商端已成交→回填）。
每輪 reconcile 自癒。v1 **不做止盈託管**（OCO 複雜、止盈晚 60 秒不致命）。
**不改回測引擎**：Bot 層 TP/SL 本來就不在回測裡，盤中觸發/跳空落差由 H3 tracking error 量化。

**四個陷阱（實作必處理）**：
1. Alpaca stop/trailing 只支援**整股** → 掛保護單的 Bot 進場改 `whole_share_qty`（floor；0 股→DecisionLog 跳過）。
2. 券商端掛著 sell stop 時股數被保留，本機直接市價賣會被拒 → **cancel-before-sell**。
3. 券商端觸發成交本機不知道 → `_settle_broker_exit` 回填 TradeLog/DecisionLog（否則 H3 資料源錯）。
4. 保護單在進場單成交前掛會失敗 → 掛單 best-effort，失敗交下一輪 reconcile。

- **Step 1（`services/alpaca_client.py` + `tests/test_safety_valve.py`）**：
  抽 `_assert_live_allowed()`（雙閘共用）；加 `submit_stop_order(symbol, qty, stop_price,
  side="sell", time_in_force="gtc")`、`submit_trailing_stop_order(symbol, qty, trail_percent, ...)`、
  `cancel_order(order_id)->bool`（已成交/查無回 False 不丟例外）、`get_order(order_id)`、
  `get_open_orders(symbol=None)->list`（失敗回 `[]`）。測試：雙閘對三種單型一致。
- **Step 2（新 `services/protective_orders.py` + `models/bot.py` + Alembic + 新測試）**：
  純函式 `whole_share_qty(trade_amount, price)->int`、
  `plan_protective_order(entry_price, *, stop_loss_pct, trailing_stop_pct)->dict|None`
  （trailing 優先；stop_price round 2 位）、`order_matches_plan(...)->bool`（容差比對）。
  `bots` 加 `protective_order_id`（String nullable）。
- **Step 3（`bots/bot_manager.py` + `config.py` + `tests/test_bot_manager.py`）**：
  `BROKER_STOP_ENABLED`（**預設 true**）。四個內部函式：`_place_protective_order`（進場後掛、
  id 落 DB、失敗 notify 不擋主流程）、`_ensure_protective_order`（`_handle_holding` 開頭自癒）、
  `_cancel_protective_order`（本機賣前撤；False→放棄本機賣）、`_settle_broker_exit`
  （空手+order id→查 filled→補 TradeLog/DecisionLog+notify+清 peak/id）。
  `_handle_flat` 整股取整；`BROKER_STOP_ENABLED=False` 行為與現狀完全一致（回歸測試保證）。

**DoD**：全測綠；Paper 手動驗——建帶 stop_loss 的 Bot → Alpaca 後台見 GTC stop 單 →
**殺後端進程，單仍掛著** → 重啟 reconcile 不重複掛。

### H2. 心跳 + dead-man switch（Step 4~5）——系統死了會有人知道

**設計**：兩個 job 分工——每日日報（給人看）+ 每 30 分外側 ping（給機器看）。
外側警報用 **healthchecks.io 免費版**（period=1h、grace=1h；警報必須在系統外側）。

- **Step 4（新 `services/heartbeat.py` + `config.py` + `bot_manager.py` + `main.py` + 新測試）**：
  `build_heartbeat_message(...)` 純函式（💓 活著｜持倉 X 檔｜啟用 Bot Y｜今日決策 N｜權益 $Z）；
  `run_daily_heartbeat()`（查詢失敗以 '?' 帶過，**心跳永不崩**、不依賴開市）；
  `ping_deadman()`（GET timeout=10；URL 空直接 return）。config：`HEARTBEAT_PING_URL`（空=關）/
  `HEARTBEAT_HOUR`（8）/ `HEARTBEAT_PING_INTERVAL_MIN`（30）。排程仿 `schedule_auto_deploy` 體例。
- **Step 5（`.env.example` + 新 `docs/guides/deadman-switch-runbook.md` + `docs/README.md` 索引）**：
  healthchecks.io 註冊/建 check/綁 Discord 步驟；警報排查清單；**每月演練**
  （停後端 2h 驗警報真響——沒演練過的 dead-man switch 等於沒有）。不把後端 port 暴露公網。

**DoD**：手動 `run_daily_heartbeat()` Discord 收到日報；實際演練停後端 → 收到外側警報。

### H3. tracking error 對帳 + 自動降級（Step 6~7）——上線後唯一的品管

**設計**：Paper 每回合**已實現報酬率%**（滾動近 10 回合均值，≥5 回合才比）vs
Opportunity 的 `oos_expectancy_pct`（**用 % 不用美元**——回測複利 initial_cash=10000、
Paper 固定 trade_amount，美元不可比）。`paper < oos × 0.5` 為一次違規（只在有新回合的日子計數）；
**連續 3 次→自動停 Bot**（is_active=False + 移除排程 + DecisionLog + notify）。
**不平倉、不撤保護單**（持倉保護不中斷，砍倉由人決定）；降級單向不自動恢復；與 promotion 狀態機正交。

- **Step 6（`services/performance.py` + `services/optimizer.py` + `models/opportunity.py` +
  `services/opportunity_scan.py` + Alembic + `tests/test_performance.py`）**：
  純函式 `compute_round_trip_returns(trades)->list[dict]`（平均成本法配對，回每回合
  profit/entry_cost/return_pct/closed_at）；optimizer 結果加
  `metrics["oos_expectancy_pct"] = oos_m["expectancy_pct"]`（`optimizer.py:167-173` 旁）；
  `opportunities` 加 `oos_expectancy_pct`（Float nullable），scan 讀寫帶上。
  不改 `compute_bot_stats` 既有輸出；不回填歷史 Opportunity（掃描自然更新）。
- **Step 7（新 `services/tracking.py` + `models/bot.py` 四欄 + Alembic + `config.py` +
  `models/decision_log.py` + `bot_manager.py` + `main.py` + 新測試）**：
  bots 加 `tracking_breach_count`（Int default 0）/ `tracking_last_rt_count`（Int default 0）/
  `demoted_at`（DateTime nullable）/ `demote_reason`（String nullable）。
  純函式 `evaluate_tracking(returns_pct, oos_expectancy_pct, *, min_round_trips=5, window=10,
  demote_ratio=0.5)->dict`（comparable=False 不冤殺；oos≤0 視門檻 0）；
  `run_tracking_check()` 每日跑（回合沒增加跳過；違規累計、回升歸零）；`_demote_bot`。
  config：`TRACKING_MIN_ROUND_TRIPS=5` / `TRACKING_WINDOW=10` / `TRACKING_DEMOTE_RATIO=0.5` /
  `TRACKING_DEMOTE_AFTER=3` / `TRACKING_CHECK_HOUR=9`。`decision_log.py` 加 `ACTION_DEMOTED = "demoted"`。

**DoD**：全測綠（monkeypatch 驗連 3 次新樣本違規才降、降級後 cancel 未被呼叫）；Alembic `upgrade head` 過。

### 測試指令（全項通用）
```powershell
venv\Scripts\python.exe -m pytest tests -q   # 跑 tests 目錄，勿 bare pytest
venv\Scripts\alembic.exe upgrade head        # 動 schema 的 step
```

---

## D. Phase 12：策略自動探勘入庫管線 🔶 step-01~04 已實作（2026-06-11）

> **2026-06-11 更新：step-01~04 程式全落地**——
> step-01 collector 通電 guide + 邊界測試（`a8ec500`）、step-02 探勘橋 `discovery.py`
> （`c0727fa`）、step-03 自動批次驗證 `auto_validate.py`（判準零修改、連續 3 次失敗才
> rejected）、step-04 漏斗報表（`/company/overview` `discovery_funnel` + 心跳待審行 +
> 戰情漏斗卡）。**剩 step-05 兩週觀察**：在常駐機器上全開
> （feeds + `DISCOVERY_ENABLED` + `AUTO_VALIDATE_ENABLED`）連跑 14 天，數據回填
> [`history/phase-12-strategy-discovery/review-e2e.md`](history/phase-12-strategy-discovery/review-e2e.md)
> 模板 → 留 / 降級 / 砍三選一。藍圖：[`history/phase-12-strategy-discovery/`](history/phase-12-strategy-discovery/README.md)。

### 觀察期開跑前 checklist（在常駐機器，照順序做）

> 管線預設全關；下面每一項缺一個，對應段就靜默不跑（設計如此，不會報錯）。
> 另參 [`guides/home-boot-checklist.md`](guides/home-boot-checklist.md)（開機基礎）與
> [`guides/collector-feeds-guide.md`](guides/collector-feeds-guide.md)（feed 挑選 + robots 檢查）。

**1. 程式環境**
- [ ] `git pull`（develop 已含 step-01~04）
- [ ] `setup.bat`（依賴 + `alembic upgrade head`）

**2. `.env` 必填（缺哪項哪段不跑）**
- [ ] `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` / `ALPACA_BASE_URL`（paper）——
      auto_validate 回測抓 K 線走 `DATA_SOURCE=alpaca`（預設）；不想用金鑰可改 `DATA_SOURCE=yfinance`
- [ ] `COLLECTOR_RSS_FEEDS`（照 feeds guide 挑 2~3 源）+ `COLLECTOR_INTERVAL_MIN=60` → 收料段
- [ ] `DISCOVERY_ENABLED=true` → 探勘橋（`DISCOVERY_HOUR` 預設 7 可不動）
- [ ] `AUTO_VALIDATE_ENABLED=true` → 自動驗證（`AUTO_VALIDATE_HOUR=8` / `AUTO_VALIDATE_SYMBOL=SPY` 預設可不動）
- [ ] `LLM_BASE_URL=http://localhost:11434/v1` + `LLM_MODEL=llama3.1`（`LLM_ALLOW_CLOUD` **維持 false**，素材不外送）
- [ ] 通知擇一：`DISCORD_WEBHOOK_URL` 或 LINE token——心跳「validated 待審」提醒要送得出去，否則人在迴路斷線

**3. 要開（常駐）的程式**（家用電腦方案；或改用免費 VM 24/7 常駐，
見 [`guides/free-vm-deployment.md`](guides/free-vm-deployment.md)——Oracle A1 免費 24GB 跑得動 Ollama）
- [ ] `ollama serve` + `ollama pull llama3.1`——探勘橋每日 7 點要用；連不上 = 整批跳過不誤殺，但等於那天沒跑
- [ ] 後端 `start_backend.bat`（uvicorn）——APScheduler 活在後端行程裡。
      **2026-06-11 起前提放寬：不必 24/7，一天至少開機一次（有網路）即可**——
      開機補跑（`CATCHUP_ON_BOOT`，預設開）會把當天該跑而沒跑的每日 job
      （discovery / auto_validate / 領導股回測 / 心跳 / tracking）立刻補齊，
      同日去重不重跑；`start_backend.bat` 內建看門狗，崩潰 10 秒後自動重啟
- [ ] （選配）healthchecks.io ping URL 填 `HEARTBEAT_PING_URL`——順便補 H2 欠的演練

**4. 串接驗通（開跑日一次性）**
- [ ] `venv\Scripts\python.exe backend\test_connection.py`（Alpaca 金鑰有效）
- [ ] 開 `http://127.0.0.1:8000/docs` 打 `GET /company/overview`，確認 `discovery_funnel` 區塊在
- [ ] （可選）手動各跑一輪驗通路，不等隔天排程：
      ```powershell
      venv\Scripts\python.exe -c "from backend.services.collector import run_collector_scan; print(run_collector_scan())"
      venv\Scripts\python.exe -c "from backend.services.discovery import run_discovery_batch; print(run_discovery_batch())"
      venv\Scripts\python.exe -c "from backend.services.auto_validate import run_auto_validate; print(run_auto_validate())"
      ```

**5. 起跑儀式**
- [ ] 快照 `discovery_funnel` JSON 貼進 review-e2e.md「觀察設定」、填起迄日（起日 +14 天）
- [ ] 兩週內人只做 LibraryPage promote/reject，**不**手動推其他狀態、**不**調 OOS 門檻（判準凍結）
- [ ] 迄日再快照、回填數據、留/降級/砍三選一

### 現況
Phase 11 README「不在本 Phase 範圍」明記「策略自動探勘入庫 → 排 Phase 12」。
`backend/services/collector.py`（Phase 10 step-04 蒐集員）已存在但開關預設關（`COLLECTOR_INTERVAL_MIN=0`、
沒設 `COLLECTOR_RSS_FEEDS` 跳過）、半手動。`strategy_generator`（Phase 8）已能產候選。
Phase 12 = 把「raw 素材 → 候選策略 → 自動回測（OOS 閘）→ 人在迴路核准入庫」串成自動化。

### Step（高層；**需先寫藍圖才開工**）
1. 新增 `docs/phase-12-strategy-discovery/README.md` 藍圖（體例同 Phase 11：原目標錨點 / step 表 /
   每步 DoD / 誠實邊界 / 團隊編組）。逐步契約檔 `step-0N-*.md`。
2. 打開 `collector` 自動掃描（`COLLECTOR_RSS_FEEDS` + `COLLECTOR_INTERVAL_MIN`），守 robots/節流/UA。
3. raw find（`raw_strategy_finds`）→ `strategy_generator` 產候選策略參數（本機 Ollama，守外送閘）。
4. 候選**自動走既有 OOS 閘**（`optimizer` 以 `oos_expected_value` 排名 + `layer_validation`）→
   **人在迴路核准**（沿用 Phase 8 `promotion` 審核）才入知識庫。
5. 全程 Paper、不碰雙閘；每筆決策落 `DecisionLog`。

### DoD
- 先有藍圖 + 逐步 DoD 才動程式（本項在此檔僅記入口，不展開實作）。

> **注意**：此項大、需獨立規劃會談。開工前先把藍圖寫完並對齊原目標。

---

## E. 前端 UX 零碎 ✅ 已完成（2026-06-11）

> 四項全落地：E1 亮色模式（`buildTheme(mode)` + `body[data-mode]` CSS 變數 + sidebar 切換鈕
> + localStorage）、E2 排行榜 `TableSortLabel`+`aria-sort`、E3 三元件 Skeleton、
> E4 補 `AccountCard`/`BacktestResultCard` 測試（前端 111 tests 全綠）。原始契約留作歷史紀錄。

1. **亮色模式切換**：`frontend/src/theme.js` 拆 light/dark 兩套 palette + 切換鈕（存 localStorage）；
   全站對比再過一遍（**深底寫死 hex 的坑要清**——換淺底時深色文字會隱形，反之亦然）。
2. **排行榜欄位排序**：`AutoBacktestPanel` 排行榜目前固定依 EV，比照 `TradesTable` 加
   `TableSortLabel` + `aria-sort`（可排 EV / 勝率 / PF 等欄）。
3. **Skeleton 全面化**：`AccountCard` / `BotList` / `TradesTable` 載入態用 MUI `<Skeleton>` 取代空白/純文字。
4. **補元件測試**：現有 `ConfirmDialog` / `BotList` / `EditBotDialog` + 純函式工具有測試，其餘元件
   （`PositionsCard`〔做完 B 後〕/ `AccountCard` / `RecommendationsPanel` 等）逐步補 Vitest + RTL。

### DoD
- 各項自帶 Vitest；顏色吃 `theme`/`NEON` 不寫死 hex；`npm run test` 綠。

---

## F. `ui-ux-pro-max` skill CLI ✅ 已完成（2026-06-12）

> **結論：vendor 上游開源檔案，不自己造資料。** 此 skill 出自
> [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)
> （MIT），把上游 `scripts/`（search.py + core.py + design_system.py，純 stdlib）與
> `data/` 全套 CSV（含 stacks/，排除未引用的 `draft.csv`/`_sync_all.py`）搬進
> `.claude/skills/ui-ux-pro-max/`，附 `LICENSE-upstream.txt` 署名。
> Windows 驗通：`venv\Scripts\python.exe ...\search.py "animation accessibility" --domain ux`
> 出正確結果；script 自帶 UTF-8 stdout 修正不踩 cp950 坑。SKILL.md 適配註記已同步
> （「CLI 不可用」→ 本專案跑法）。以下原始契約留作歷史紀錄。

### 現況
`.claude/skills/ui-ux-pro-max` 的規則文字已夠用，但未隨附 `search.py` / 規則 CSV，
skill 文件提到的 CLI 查詢無法實際跑。

### Step
- 補 `.claude/skills/ui-ux-pro-max/search.py` + 規則 CSV，讓查詢 CLI 能跑（讀 `docs/guides/skill-guidelines.md` 守則）。
- 低優先：純文字規則已可用，CLI 只是便利。

### DoD
- `search.py` 能對規則 CSV 做關鍵字查詢並印結果。

---

## G. 文件漂移修正 ✅ 已完成（2026-06-11）

> `CLAUDE.md` 結構樹補齊 Phase 8–11 + backlog H 模組；`workflow-diagrams.md` 加
> 「圖 5：Phase 8–11 知識庫 → AI 公司軌」。原始契約留作歷史紀錄。

### 現況
`docs/reference/workflow-diagrams.md` 與 `CLAUDE.md` 的「專案結構」樹仍停在 Phase 6–7，
漏畫/漏列 Phase 8–11 已落地模組（知識庫/組合進化、前端工作站、AI 公司、總經資料地基）。

### Step
- 補 Phase 8/9/10/11 的 services/models/routers/pages 到 `CLAUDE.md` 結構樹。
- `docs/reference/workflow-diagrams.md` 的 Mermaid 圖補上 Phase 8–11 的資料流節點。
- 純文件、無程式變更。

### DoD
- 結構樹與工作流圖反映 `origin/develop` 實際模組，無漏列。
