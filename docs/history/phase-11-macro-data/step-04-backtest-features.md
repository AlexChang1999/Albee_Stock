# 步驟 4 — 回測引擎吃 `features`

> 讓回測引擎能把環境特徵餵給策略，但**不動成交鐵則**。回到 [Phase 11 索引](README.md)。

## 目標

回測引擎多接一條「環境特徵」輸入管線：策略想用 step-03 的 macro / 買賣壓特徵時拿得到；
**忽略 features 的舊策略照跑（完全向後相容）**。成交執行**仍只用價格**，不因環境特徵改變成交價。

## 改動構想

- `backend/services/backtest_engine.py`：`_run_on_df` / `run_backtest` 加**選用**參數
  `features: pd.DataFrame = None`：
  - `features` 與價格 `df` 同索引（每根 K 棒一列），以額外欄位傳給策略的訊號函式。
  - `features=None`（預設）→ 行為與現況**逐位元組相同**（舊策略 / 舊呼叫端零改動）。
- 成交仍走 `_simulate_from_signals`：訊號於**次根開盤**成交、含**手續費 / 滑價**、最後一根不成交。
  **環境特徵只能影響「要不要進場 / 部位」，不能影響成交價**（不動成本 / 隔日成交鐵則）。

## 重用現有

- `backtest_engine._run_on_df` 既有簽章——只**加**一個預設 `None` 的參數，不改既有參數順序 / 語意。
- `_simulate_from_signals`（成交模擬）原封不動，features 不接進成交層、只接進訊號層。
- step-03 的 `attach_macro_features` / `compute_orderflow` 產生 `features`；step-02 的 `bar_cache`
  供多年價格。

## 鐵則 / 風險

- **features 不得碰成交價**：環境因子只是「決策輸入」，成交永遠用次根開盤含成本——這是
  Phase 11 第 3 鐵則，也是「回測=實盤」的核心。違反就回到「零成本偷看未來報虛高 EV」的老坑。
- **向後相容是硬需求**：任何不傳 features 的既有測試 / 策略 / API 行為不可變。
- **features 對齊不可洩漏**：features 來自 step-03（已用 `released_at` 對齊），引擎只負責「傳遞」，
  不在引擎內重算對齊，避免兩處邏輯分岔。

## 驗收（DoD）

- 不傳 `features` 時，既有回測測試（`tests/test_backtest.py`）全綠、數字不變。
- 傳入合成 `features` 且策略讀用它時，訊號確實受影響、但成交價仍等於次根開盤（斷言成交價與
  features 無關）。
- 一個忽略 features 的舊策略，帶 / 不帶 features 跑出**完全相同**的結果（向後相容斷言）。
