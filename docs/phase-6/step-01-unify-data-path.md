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

---

## 實作備註（2026-06-05 完成）

> 留給未來的人 / AI：本步驟落地時的決策與一個刻意保留的差異。

### 「回看天數一致」的詮釋（重要）

驗收寫「同源、**回看天數一致**」。落地時**沒有**讓回測也改用 `required_lookback_days`，原因：

- 回測要靠「夠多筆交易」才能算出可信的 EV，需要長歷史（現況 `days=365`）。
- 若回測也壓成 `required_lookback_days`（預設參數只有 ~50 天），樣本數會被砸爛、EV 失去意義——
  這反而違反北極星「EV 要誠實」。

因此本步驟真正修的是 P4 的根因：**資料源分岔 + 實盤死壓 60 < 策略所需**。落地策略為：

- **同源**：實盤與回測都走 `market_data.get_bars(source=settings.DATA_SOURCE)`。✅ 完全一致。
- **回看長度**：實盤改抓「策略所需的足量」（`required_lookback_days`，永遠 ≥ 所需，
  不再像舊版 60 可能 < 所需）；回測續用 365（更長、同樣 ≥ 所需）。
- 兩路因此**同源、且都涵蓋策略所需的最近視窗**；數字非逐字相等，但「實盤看得到的近期資料 ⊆ 回測看得到的」，
  不再有「實盤算不出、回測算得出」的失準。

> 若日後要求兩路逐字同天數，再單獨開一步處理（並想清楚對回測樣本數的衝擊），不在本步驟硬塞。

### 環境無 venv 的小坑

本次施工環境（背景 job）原本沒有 `venv/`、系統 Python 也缺依賴，跑 `pytest` 前需先
`python -m venv venv` + `pip install -r requirements.txt`（見 [`SETUP.md`](../../SETUP.md) 步驟 2）。
最終 `pytest tests/ -q` → **137 passed**。
