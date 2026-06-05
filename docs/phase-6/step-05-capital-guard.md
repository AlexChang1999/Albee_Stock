# 步驟 5 — 組合層資金 / 購買力守門

> 修 **P6 前半**（無組合層資金控管）。回到 [Phase 6 索引](README.md)。

## 目標

讓系統在「建 Bot」與「下買單」前，先確認**帳戶真的付得起**，且永遠保留一筆現金緩衝。
防止模式 B 一次梭哈、並發下單互踩購買力。

## 問題（現況）

- 每個 Bot 各自 `qty = bot.trade_amount / current_price` all-in，彼此不知道對方花了多少。
- `automation.run_auto_deploy` 可一次建 5 個 Bot（`AUTO_DEPLOY_MAX_BOTS`），**完全不查帳戶現金**。
- 多個 Bot 幾乎同時排程觸發買進時，沒有任何「總曝險不超過購買力」的守門。

## 改動

1. 新增純函式 **`plan_capital(planned, available_cash, cash_per_bot, reserve_ratio) -> (approved, rejected)`**
   （建議放新檔 `backend/services/capital.py`，或 `automation.py`）：
   - 可動用額度 = `available_cash × (1 - reserve_ratio)`。
   - 依序核可 planned，逐筆扣 `cash_per_bot`，扣到不夠就把其餘歸入 `rejected`（附原因）。
2. **`backend/services/automation.py`** 的 `run_auto_deploy`：部署前查 `alpaca_client.get_account()` 的 `cash` / `buying_power`，
   套 `plan_capital`，只建 `approved` 的；`rejected` 列入回傳摘要與 `notify`。
3. **`backend/bots/bot_manager.py`** 的 `_handle_flat`：買進前 best-effort 查可用購買力，
   若 `qty × price > 可用購買力` 則跳過買進並記一筆審計（見 [步驟 8](step-08-decision-audit-log.md) 的 `skipped_no_buying_power`）。離線 / 查價失敗不阻斷（best-effort）。
4. **`backend/config.py`** 新增 `PORTFOLIO_CASH_RESERVE_RATIO`（預設例如 `0.2`，永遠留 20% 現金）。

## 重用既有

- `alpaca_client.get_account()`（已存在）。
- `automation.run_auto_deploy` 既有的 dry_run / 摘要結構（把 `rejected` 併進去即可）。

## 測試

- `plan_capital` 純函式：現金剛好夠 / 不夠 / 保留比例邊界 / cash_per_bot 為 0 等情境。
- `run_auto_deploy`：monkeypatch 假帳戶現金不足時，只建得起的數量、其餘進 `rejected`。

## 驗收

- 假帳戶現金設低，`POST /automation/run?dry_run=true` 的 `planned` 被資金守門砍到付得起的數量。
- 空手 Bot 在購買力不足時跳過買進，並在 `decisions` 留下 `skipped_no_buying_power` 紀錄。
