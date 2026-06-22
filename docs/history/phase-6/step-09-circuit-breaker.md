# 步驟 9 — 組合回撤熔斷

> 修 **P6 後半**（無全域風險開關）。回到 [Phase 6 索引](README.md)。

## 目標

給整個帳戶一個「自動剎車」：當總權益從峰值回落超過門檻，**暫停所有新增曝險**
（新買進 + 自動部署），但既有持倉的風控出場照常運作。這是跑真錢的最後一道安全網。

## 問題（現況）

系統只有「單一 Bot 單一持倉」層級的風控（`risk_manager.check_exit`）。
**沒有任何組合 / 帳戶層級的總開關**：若市場整體崩跌、多個 Bot 同時受傷，沒有機制喊停新進場，
只能眼睜睜看它繼續開新倉加碼風險。

## 改動

1. 新增純函式 **`portfolio_circuit_breaker(equity_now, equity_peak, max_dd_pct) -> bool`**
   （回傳「是否該熔斷」）。
2. **`backend/config.py`** 新增 `PORTFOLIO_MAX_DRAWDOWN_PCT`（預設例如 `20`）。
3. 帳戶權益峰值持久化（小表 `portfolio_state`，或重用既有設定表；每輪用 `get_account().portfolio_value` 更新峰值）。
4. 檢查點（只擋**新增曝險**，不碰出場）：
   - **`backend/bots/bot_manager.py`** 的 `_handle_flat` 買進前：熔斷觸發 → 跳過買進，記 `skipped_circuit_breaker`（[步驟 8](step-08-decision-audit-log.md)）。
   - **`backend/services/automation.py`** 的 `run_auto_deploy` 開頭：熔斷觸發 → 不建任何 Bot，回摘要說明。
   - 觸發時 `notify` 一次（避免每輪洗版，可加去抖）。
   - **既有持倉的 `check_exit`（止損 / 追蹤 / 止盈）完全不受影響**——熔斷只擋進、不擋出。

## 重用既有

- `alpaca_client.get_account()`（取 `portfolio_value`）。
- `notify`、[步驟 8](step-08-decision-audit-log.md) 的 `DecisionLog`。

## 測試

- `portfolio_circuit_breaker` 純函式：未達門檻 / 剛好門檻 / 超過門檻 / 峰值為 0 等邊界。
- `run_auto_deploy`：模擬權益跌破門檻時不建任何 Bot。
- `_handle_flat`：熔斷時跳過買進、但 `_handle_holding` 的出場仍會執行。

## 驗收

- 模擬帳戶權益跌破 `PORTFOLIO_MAX_DRAWDOWN_PCT`，確認**新買進 / 自動部署被擋**、**既有風控出場照跑**。
- 熔斷期間 `decisions` 留下 `skipped_circuit_breaker` 紀錄，且發出一次通知。
