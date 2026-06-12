# Phase 11：總經環境資料地基

> **開工前必讀** [`../ai-implementation-guardrails.md`](../../ai-implementation-guardrails.md)。
> 一次一步、永遠對齊原目標；每步收工對 DoD、更新 `CHANGELOG.md`。

## 這個 Phase 服務的原目標

讓策略機器人用「**環境因素**」（非農就業、失業率、聯準會利率、CPI、公債殖利率、VIX、買賣量壓力）
跑**多年歷史**回測，挑出能在「看不到下一步」的真實市場獲利的策略。

盤點後的真相：執行機器（海選→回測→部署→董事會→實盤雙閘）大致蓋好了，但**「環境資料的大腦」整個缺**——
`grep` 整個 `backend/` 找不到 FRED / 非農 / 利率 / CPI。現況只有 OHLCV + 公司基本面。Phase 11 補這塊。

## 背景：盤點與決策（CEO 開工討論摘要）

### 鎖定決策

- **Phase 11 = 先補「環境資料大腦」**（總經地基）；策略自動探勘入庫記錄、排 Phase 12（見下方「不在本 Phase 範圍」）。
- **買賣量 = 總量 + 漲跌 tick 代理**（免費資料源沒有真實買 / 賣拆分）。
- **總經源 = FRED + yfinance max + 本機快取**（多年歷史走 yfinance；實盤仍走 `settings.DATA_SOURCE`）。

### 願景 vs 現況落差（本期主攻＝粗體）

| 願景 | 現況 | 本期做法 |
|------|------|----------|
| **總經因子（非農 / 失業 / 利率 / CPI）** | ❌ 完全沒有 | 接 FRED（step-01 ✅） |
| **買入量 vs 賣出量** | ❌ 免費只有總量 | 漲跌 tick 代理（step-03） |
| **抓整個歷史回測** | ⚠️ 預設 60–365 天、每次重抓 | yfinance max + 本機快取（step-02） |
| **環境因子進回測** | ❌ 引擎純價量 | 引擎吃 `features` 欄（step-04） |
| 爬網路策略 → 入庫 | ⚠️ 半手動、開關關 | 記錄到 Phase 12 |
| 機器人實盤獲利 | ✅ 管線齊、paper 安全 | 不動 |

> 文件漂移（另案處理，非本資料夾）：`docs/workflow-diagrams.md` 與 `CLAUDE.md` 結構樹仍停在 Phase 6–7，
> 漏畫 / 漏列 Phase 8–10 已落地的模組。

### 團隊編組（職能 → 擁有模組 → 本期交付）

| 角色 | 擁有模組 | 本期交付 |
|------|----------|----------|
| 總經資料工程師 | `fred_client` / `macro_data` / `macro_series` / `bar_cache` | FRED 接通 + 多年快取 + point-in-time（step-01~02） |
| 狀態訊號科學家 | `macro_features` / `orderflow_proxy` / `regime` | 環境因子 + 買賣壓代理 → 對齊 K 線特徵（step-03） |
| 回測工程師 | `backtest_engine` / `optimizer` / `screener` | 引擎吃 `features` + 多年回測走快取（step-04） |
| 驗證 QA | `validation` / `layer_validation` | macro 層 OOS 加分驗證 + 防洩漏單測（step-05） |
| 風控合規官 | `capital` / `circuit_breaker` / `promotion` / 雙閘 | 維持「只煞車不猜方向」，不動安全閥 |
| 量化探勘員 | `collector` / `strategy_generator` / `evolution` | Phase 12（本期僅記錄藍圖） |
| 前端戰情 | `pages/` / factors UI | 本期末選做：macro 面板（可延 Phase 12） |

## Phase 11 專屬鐵則（在通用鐵則之上）

1. **point-in-time（最重要）**：經濟數據公布有遞延（非農 M 月數據約 M+1 月第一個週五才公布）。
   回測在某日**只能看到那日已公布**的值。每筆同存「資料期間 `period_date`」與「市場知道日 `released_at`」，
   對齊一律用 `released_at`，**嚴禁用 `period_date` 偷看尚未公布的未來**。這是「回測=實盤」鐵則的延伸。
2. **免費 / 本機優先**：總經走 FRED（聖路易聯準會，免費 API key）；沒填 key → 整功能**靜默降級**，
   不影響其他功能（仿 `services/llm.py` 的優雅降級）。買賣量用免費資料拿得到的「總量 + 漲跌 tick 代理」。
3. **環境因子只當回測/決策的輸入特徵**，成交執行仍只用價格（不動成本/隔日成交鐵則）。
4. **沒加分就砍**：macro 特徵要在 walk-forward OOS 證明贏過純價量 baseline，否則記錄該砍（沿用 Phase 7 框架）。

## 步驟（每步 = 一個聚焦單元）

| step | 目標 | 關鍵檔（新增/改） | 驗收 | 狀態 |
|------|------|------------------|------|------|
| **01** | 總經資料接入 + 本機快取 + point-in-time | `services/fred_client.py`、`services/macro_data.py`、`models/macro_series.py`、`routers/macro.py`、`config.py`、Alembic | 防洩漏單測（公布前看不到）+ 無 key 優雅降級 | ✅ |
| **02** | 多年 OHLCV 本機快取（避免每次重抓） | `services/bar_cache.py`、`config.py` | 缺區間補抓、命中快取不重打 + 單測 | ✅ |
| **03** | 環境特徵 + 買賣壓代理 | `services/macro_features.py`、`services/orderflow_proxy.py` | as-of 用 `released_at` 對齊；`buy+sell==volume`、方向符合漲跌 + 單測 | ✅ |
| **04** | 回測引擎吃 `features` + 接 bar_cache | `services/backtest_engine.py`（加選用參數）、`optimizer.py`/`screener.py`（改吃快取） | 舊策略忽略 features 照跑（向後相容）+ 單測 | ✅ |
| **05** | macro 層 OOS 加分驗證 | `services/layer_validation.py`、`scripts/validate_layers.py` | 印出 `worth/folds/improvement`；沒加分如實標記 + 單測 | ✅ |

## 施工路線（step 藍圖檔）

每個 step = 一份契約文件：開工前讀「目標 / 改動構想 / 重用現有 / 風險 / 驗收（DoD）」，
一次一步、對齊原目標（體例同 [Phase 7](../phase-7-adaptive-regime/README.md)）。

| step | 文件 | 主題 | 狀態 |
|------|------|------|------|
| 1 | [step-01-macro-data-ingestion.md](step-01-macro-data-ingestion.md) | 總經接入 + 本機快取 + point-in-time | ✅ 已落地 |
| 2 | [step-02-bar-cache.md](step-02-bar-cache.md) | 多年 OHLCV 本機快取 | ✅ 已落地 |
| 3 | [step-03-macro-features-orderflow.md](step-03-macro-features-orderflow.md) | 環境特徵 + 買賣壓代理 | ✅ 已落地 |
| 4 | [step-04-backtest-features.md](step-04-backtest-features.md) | 回測引擎吃 `features` + 接 bar_cache | ✅ 已落地 |
| 5 | [step-05-macro-layer-validation.md](step-05-macro-layer-validation.md) | ★macro 層 OOS 加分驗證 | ✅ 已落地（首跑 SPY 判 worth=False，待真 FRED 資料） |

> 建議順序：**1（已完成）→ 2（多年快取）→ 3（特徵）→ 4（引擎接 features）→ 5（OOS 驗證，盡早建）**。
> step-5 是「能不能信」的關鍵——沒它，前 4 步只是用總經數據更精緻地騙自己。

### step 契約細節

- **step-01 重用**：`config.py`（設定分區慣例）、`database.Base`/`models/__init__.py`（模型註冊）、
  `routers/factors.py`（唯讀端點風格）、`services/llm.py`（無金鑰優雅降級）。
  **不要**：加沒用到的 config 旗標（沒 FRED key 即關，不另設 `MACRO_ENABLED`）。
- **step-02 重用**：`market_data.get_bars(symbol, days, source)` 當底層抓取，cache 只包在外層、不改其簽章。
- **step-03 重用**：`strategies/indicators.py`（OBV/MFI 類）、`regime_features.py`（特徵對齊風格）。
  **不要**：把買賣量當成真實 order flow 行銷（它是 tick 代理，誠實標註）。
- **step-04 重用**：`backtest_engine._run_on_df` 既有簽章，新參數 `features=None` 預設不改變行為。
  **不要**：讓 features 影響成交價（成交仍用次根開盤、含成本）。
- **step-05 重用**：`validation.walk_forward_splits` / `is_layer_worth_it`、`layer_validation` 的
  baseline-vs-candidate harness。**不要**：在整段歷史挑樣本內最佳。

## 不在本 Phase 範圍（誠實邊界）

- **真實買賣量**：免費資料源沒有，本期是 tick 代理；要真值得接付費 order-flow（Polygon/Databento）。
- **FRED ALFRED 真實 vintage**：v1 用「設定式發布落差」近似 point-in-time（保守、可測）；
  v2 再換真實歷史公布值，介面不變。
- **策略自動探勘入庫**：排在 Phase 12（`collector` 打開 + raw→候選→自動回測自動化）。
- **真錢**：不碰雙閘安全閥，全程 Paper。
