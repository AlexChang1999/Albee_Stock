# Phase 11：總經環境資料地基

> **開工前必讀** [`../ai-implementation-guardrails.md`](../ai-implementation-guardrails.md)。
> 一次一步、永遠對齊原目標；每步收工對 DoD、更新 `CHANGELOG.md`。

## 這個 Phase 服務的原目標

讓策略機器人用「**環境因素**」（非農就業、失業率、聯準會利率、CPI、公債殖利率、VIX、買賣量壓力）
跑**多年歷史**回測，挑出能在「看不到下一步」的真實市場獲利的策略。

盤點後的真相：執行機器（海選→回測→部署→董事會→實盤雙閘）大致蓋好了，但**「環境資料的大腦」整個缺**——
`grep` 整個 `backend/` 找不到 FRED / 非農 / 利率 / CPI。現況只有 OHLCV + 公司基本面。Phase 11 補這塊。

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
| **01** | 總經資料接入 + 本機快取 + point-in-time | `services/fred_client.py`、`services/macro_data.py`、`models/macro_series.py`、`routers/macro.py`、`config.py`、Alembic | 防洩漏單測（公布前看不到）+ 無 key 優雅降級 | 🚧 |
| **02** | 多年 OHLCV 本機快取（避免每次重抓） | `services/bar_cache.py`、`config.py` | 缺區間補抓、命中快取不重打 + 單測 | ⬜ |
| **03** | 環境特徵 + 買賣壓代理 | `services/macro_features.py`、`services/orderflow_proxy.py` | as-of 用 `released_at` 對齊；`buy+sell==volume`、方向符合漲跌 + 單測 | ⬜ |
| **04** | 回測引擎吃 `features` | `services/backtest_engine.py`（加選用參數） | 舊策略忽略 features 照跑（向後相容）+ 單測 | ⬜ |
| **05** | macro 層 OOS 加分驗證 | `services/layer_validation.py`、`scripts/validate_layers.py` | 印出 `worth/folds/improvement`；沒加分如實標記 + 單測 | ⬜ |

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
