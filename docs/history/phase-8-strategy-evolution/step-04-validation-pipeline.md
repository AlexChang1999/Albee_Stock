# 步驟 4 — 自動驗證管線（OOS + 防過擬合）

> 開工前讀 [AI 實作護欄合約](../../ai-implementation-guardrails.md)。回到 [Phase 8 索引](README.md)。
> **這步是整個 Phase 8 能不能信的關鍵守門。**

## 目標

任何候選策略（生成的 or 組合的）要進策展庫前，**一律跑同一條嚴格驗證管線**，
只有在**樣本外真的加分**的才通過。把「自我進化」與「自我過擬合」分開的唯一防線。

## 概念

walk-forward 驗證式策展。直接重用 Phase 6/7 的成果，**不自寫驗證邏輯**。

## 改動（只做這些）

- 新增 `backend/services/evolution.py`：`validate_candidate(knowledge_row) -> dict`：
  1. 用 `market_data.get_bars`（同源同回看，呼應原目標鐵則 3）。
  2. 跑 **Phase 6 含成本 + 隔日成交** 的回測、**OOS 切分**（Phase 6 step-04 的 `split_train_test`）。
  3. 跑 **Phase 7 step-07** 的 `walk_forward` / `is_layer_worth_it`，判定是否「在 OOS 真加分」。
  4. 寫回 `StrategyKnowledge.oos_metrics` + 更新 `status`（validated / rejected）。
- 端點 `POST /knowledge/{id}/validate`。

## 重用既有（強制——不要重造）

- `backtest_engine._run_on_df`（含 Phase 6 成本 / 隔日）。
- `optimizer`（若要搜參數）。
- Phase 6 `split_train_test`、Phase 7 `validation.walk_forward` / `is_layer_worth_it`。

## 不要做（防 slop / 防漂移）

- **不要**自寫一套新的回測 / 切分 / 評分——這正是 slop 重災區，全部用 Phase 6/7 既有函式。
- **不要**用樣本內指標判定通過（違反原目標鐵則 2）。
- **不要**在 Phase 6/7 對應步驟還沒實作時硬上——**前置未完成就停、就問**（護欄第柒節）。

## 測試 / 完成定義

- `tests/test_evolution.py`：monkeypatch 一個「OOS 加分」與一個「OOS 不加分」的候選，驗證前者 validated、後者 rejected。
- 驗證判定鍵讀的是 OOS / walk-forward，不是 in-sample；`pytest tests/ -q` 全綠。
