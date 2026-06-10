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

最後更新：2026-06-10。狀態基準：`origin/develop`（Phase 11 全落地，353 tests 過、1 個 pre-existing 失敗）。

---

## 盤點總表（依價值排序）

| # | 項目 | 類型 | 阻塞？ | 價值 |
|---|------|------|--------|------|
| A | Phase 11 macro 層真資料驗證（step-05 收尾） | 驗證/決策 | 待 FRED key | 高（決定一層去留） |
| B | `/positions` 端點 + 前端持倉/未實現損益卡 | 後端+前端 | 無 | **最高（最大缺口）** |
| C | `test_run_dry_run` pre-existing 失敗修掉 | bugfix | 無 | 中（CI 乾淨） |
| D | Phase 12：策略自動探勘入庫管線 | 大 feature | 無 | 中（長線） |
| E | 前端 UX 零碎：亮色模式/排行榜排序/Skeleton/補測試 | 前端 | 無 | 低~中 |
| F | `ui-ux-pro-max` skill CLI（`search.py`/CSV） | 工具 | 無 | 低 |
| G | 文件漂移：`workflow-diagrams.md`/`CLAUDE.md` 結構樹停在 Phase 6–7 | 文件 | 無 | 低 |

**建議先做順序**：B（最大缺口、無阻塞）→ C（小、CI 乾淨）→ A（需先有 FRED key）→ D/E/F/G 依需求挑。

---

## A. Phase 11 macro 層真資料驗證（step-05 收尾）

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

## B. `/positions` 端點 + 前端持倉卡（最高價值）★

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

## C. 修 `test_run_dry_run` pre-existing 失敗

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

## D. Phase 12：策略自動探勘入庫管線（大 feature，長線）

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

## E. 前端 UX 零碎（低~中價值，逐項獨立、互不阻塞）

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

## F. `ui-ux-pro-max` skill CLI

### 現況
`.claude/skills/ui-ux-pro-max` 的規則文字已夠用，但未隨附 `search.py` / 規則 CSV，
skill 文件提到的 CLI 查詢無法實際跑。

### Step
- 補 `.claude/skills/ui-ux-pro-max/search.py` + 規則 CSV，讓查詢 CLI 能跑（讀 `docs/skill-guidelines.md` 守則）。
- 低優先：純文字規則已可用，CLI 只是便利。

### DoD
- `search.py` 能對規則 CSV 做關鍵字查詢並印結果。

---

## G. 文件漂移修正

### 現況
`docs/workflow-diagrams.md` 與 `CLAUDE.md` 的「專案結構」樹仍停在 Phase 6–7，
漏畫/漏列 Phase 8–11 已落地模組（知識庫/組合進化、前端工作站、AI 公司、總經資料地基）。

### Step
- 補 Phase 8/9/10/11 的 services/models/routers/pages 到 `CLAUDE.md` 結構樹。
- `docs/workflow-diagrams.md` 的 Mermaid 圖補上 Phase 8–11 的資料流節點。
- 純文件、無程式變更。

### DoD
- 結構樹與工作流圖反映 `origin/develop` 實際模組，無漏列。
