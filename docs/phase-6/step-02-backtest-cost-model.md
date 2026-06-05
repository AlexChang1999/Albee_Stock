# 步驟 2 — 回測成本模型（手續費 / 滑價）

> 修 **P2**（回測零成本零滑價）。回到 [Phase 6 索引](README.md)。

## 目標

讓回測的每一筆買賣都吃到**真實世界的摩擦成本**，使 EV / profit factor / expectancy 變誠實。
這是「回測 ≈ 實盤」的核心一環：沒有成本的 EV 是行銷數字，不是可下注的數字。

## 問題（現況）

`backtest_engine._run_on_df` 用 `close` 價即時、零成本成交：
- 買進 `qty = cash / price`、賣出 `proceeds = position * price`，**沒有手續費、沒有滑價、沒有買賣價差**。
- 高頻策略（RSI / KD / stochastic）交易筆數多，真實成本侵蝕巨大，但回測完全看不到。
- 模式 B 的 `AUTO_DEPLOY_EV_THRESHOLD=150` 是拿這個虛高的 EV 在比，門檻形同虛設。

## 改動

1. **`backend/config.py`** 新增：
   - `BACKTEST_COMMISSION_BPS`（預設 `0`，Alpaca 美股免佣；保留欄位讓未來換券商 / 標的能調）。
   - `BACKTEST_SLIPPAGE_BPS`（預設例如 `5`，市價單的滑價 + 半個價差的保守估計，單位 basis point）。
2. **`backend/services/backtest_engine.py`** 的 `_run_on_df` 新增選填參數 `commission_bps` / `slippage_bps`：
   - 買進成交價 = `price × (1 + slippage_bps/1e4)`；賣出成交價 = `price × (1 - slippage_bps/1e4)`。
   - 每筆買 / 賣再各扣 `成交金額 × commission_bps/1e4` 的手續費。
   - 成本反映進 `profit` 與 `equity_curve` → **EV / profit_factor / expectancy 公式不動就自動變誠實**。
   - 回傳新增 `total_cost`（本次回測累計摩擦成本），讓前端 / 檢討看得到成本侵蝕多少。
3. `run_backtest`（及上層 `optimizer` / `presets backtest`）把 config 的兩個 bps 預設帶進 `_run_on_df`。

## 重用既有

- 所有上層回測（`run_backtest` / `optimizer.run_auto_backtest` / `presets/{id}/backtest`）都經過 `_run_on_df`，**改一處、全鏈受惠**，不需各別改。

## 測試

- 合成序列手算：同一序列「`slippage_bps=0` vs `=5`」的 EV 差額，要等於「交易筆數 × 預期每筆成本」。
- 高頻 vs 低頻策略：驗證高頻策略的 `total_cost` 明顯較高、EV 被侵蝕較多。
- `commission_bps>0` 時，買賣各扣一次手續費的金額正確。

## 驗收

- 回測結果出現 `total_cost`，且開啟滑價後既有策略 EV 普遍下降（**預期的誠實化**，CHANGELOG 須註明數字會變）。
- 一個原本「EV 微正」的高頻策略，加成本後若翻負，能正確顯示為負 EV（不再誤導部署）。
