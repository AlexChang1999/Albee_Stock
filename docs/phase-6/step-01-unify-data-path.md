# 步驟 1 — 統一資料路徑：實盤 = 回測

> 修 **P4**（實盤與回測資料路徑分岔），並為 [步驟 6](step-06-scheduler-refetch.md) 鋪路。
> 回到 [Phase 6 索引](README.md)。

## 目標

讓「實盤交易抓的 K 線」與「回測 / 海選抓的 K 線」**同源、同回看長度**。否則你回測驗證過的東西，
跟實盤真正在跑的東西不是同一回事——這是「回測 = 實盤」鐵則的第一道。

## 問題（現況）

- 實盤：`bot_manager._run_strategy` 寫死 `alpaca_client.get_bars(bot.symbol, days=60)`。
- 回測 / 海選：走 `market_data.get_bars(symbol, days=365, source=可選)`（已是契約一致的分派器）。

兩條路徑的**資料源不同**（實盤鎖死 Alpaca，回測可選 yfinance）、**回看長度不同**（60 vs 365）。
後果：`long_window=120` 的均線策略，實盤只有 60 根資料、長均線根本算不出來，行為與回測完全不同，靜默失準。

## 改動

1. **`backend/config.py`** 新增 `DATA_SOURCE`（預設 `"alpaca"`，可設 `"yfinance"`），作為**全系統唯一資料源設定**。
2. 新增純函式 **`required_lookback_days(strategy_key, params) -> int`**（建議放新檔 `backend/strategies/lookback.py`，或 `strategies/__init__.py`）：
   - 依各策略的關鍵參數（`long_window` / `slow+signal` / `period` / `k_period` …）推算「至少需要幾根 K 棒才算得準」，再換算成日曆天數（保留緩衝，例如 ×1.6 + 假日）。
   - 回測與實盤**共用此函式**算回看長度，徹底消滅 60 vs 365 的硬編碼。
3. **`backend/bots/bot_manager.py`** 的 `_run_strategy`：改走
   `market_data.get_bars(bot.symbol, days=required_lookback_days(bot.strategy, bot.params or {}), source=settings.DATA_SOURCE)`。
4. **`optimizer` / `screener` / `recommendations` / `backtest`** 的 `source` 預設改讀 `settings.DATA_SOURCE`（保留呼叫端可覆寫的參數，向後相容）。

## 重用既有

- `backend/services/market_data.py` 的 `get_bars`（契約一致的分派器，已存在）。
- `backend/services/yfinance_client.py`（已存在的免費資料源）。

## 測試

- `tests/test_lookback.py`（新）：各策略在不同參數下推算的回看天數，要 ≥ 該策略所需的最小資料量。
- 改 `tests/test_bot_manager.py`：monkeypatch `market_data.get_bars`，驗證實盤路徑**走 `market_data`、帶 `settings.DATA_SOURCE`、帶推算後的天數**（不再寫死 60、不再直接打 `alpaca_client.get_bars`）。

## 驗收

- 同一 Bot 用 `POST /bots/{id}/run`（實盤路徑）與 `POST /backtest`（回測路徑）對同標的，抓到的是**同源、回看天數一致**的資料。
- `DATA_SOURCE=yfinance` 時，實盤路徑也改吃 yfinance（不再被鎖死在 Alpaca）。
