# 步驟 3 — 策略組合引擎（Ensemble）

> 開工前讀 [AI 實作護欄合約](../ai-implementation-guardrails.md)。回到 [Phase 8 索引](README.md)。
> **這步是使用者最強調的「整合 / 結合策略」。**

## 目標

把多個**已驗證**子策略的訊號，聚合成一個複合策略（CompositeStrategy），形成新的、可回測的單一策略。
這是「蒐集很多策略 → 整合」的程式落地。

## 概念

策略組合 / 集成（Ensemble / Strategy Combination）。聚合方式（先簡單）：
- **投票（majority vote）**：多數子策略同向才出手。
- **加權（weighted）**：依各子策略 OOS EV 給權重。
- **狀態切換（regime-switch）**：依 Phase 7 當下狀態選用對應子策略（與 Phase 7 step-03 銜接）。

## 改動（只做這些）

- 新增 `backend/strategies/composite.py`：`CompositeStrategy(BaseStrategy)`，
  建構子吃「子策略清單 + 聚合方式」，`generate_signal(df)` 內部呼叫各子策略再聚合。
- 聚合邏輯抽成**純函式**（`aggregate_signals(signals, method, weights) -> Signal`），好單測。
- 註冊進 `STRATEGY_REGISTRY`（鍵如 `composite`），讓既有回測 / Bot 流程**零改動**就能跑它。

## 重用既有

- `BaseStrategy` 介面、`get_strategy` / `STRATEGY_REGISTRY`、`Signal` 列舉（`backend/strategies/`）。
- 子策略一律用既有 8 種（透過 `get_strategy`），**不重寫指標**。

## 不要做（防 slop）

- **不要**為組合引擎發明新的訊號型別 / 新的回測路徑——複合策略就是一個普通 `BaseStrategy`，照走 `_run_on_df`。
- **不要**先做複雜聚合（如機器學習 stacking）；先投票 / 加權 / 狀態切換三種，證明有效再說。
- **不要**讓子策略各自抓資料——統一吃傳入的同一份 `df`（呼應「回測=實盤、資料只抓一次」）。

## 測試 / 完成定義

- `tests/test_composite.py`：`aggregate_signals` 純函式（投票 / 加權 / 平手 / 全 HOLD）；CompositeStrategy 能被 `get_strategy` 實例化並產生訊號。
- 複合策略能直接丟進 `_run_on_df` 跑出 metrics；`pytest tests/ -q` 全綠。
