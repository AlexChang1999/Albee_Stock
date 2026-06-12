# Phase 10 step-02 — 常駐探勘 + 機會清單持久化

> 開工前必讀 [`../ai-implementation-guardrails.md`](../../ai-implementation-guardrails.md)。
> 依賴：Phase 6（誠實 OOS）、step-01。

## 目標 / 概念

補「**開機就一直收 + 好策略不漏掉**」：把海選改成**週期自動跑**，排名候選**存進 DB**，
名額滿時不再把第 6~N 名直接丟掉。服務「回測 = 實盤的誠實 EV」——候選一律存樣本外指標。

## 問題 / 改動

- 新增 model `backend/models/opportunity.py`（`symbol` / `strategy_key` / `params` / `oos_expected_value` /
  `oos_win_rate_pct` / `sentiment` / `scanned_at` / `status`：new/seen/deployed/expired），走 **Alembic 遷移**。
- `bot_manager` 加一個 APScheduler **週期 job**（間隔讀 config，預設盤中每 N 分鐘）呼叫
  `screener.screen_watchlist`，把結果 **upsert** 進 opportunity 表（同 symbol+strategy 更新、不重複）。
- 新增唯讀 `GET /opportunities`（依 OOS EV 排序，可 limit）；戰情頁（step-01）與董事會頁（step-06）取用。
- 發現「新的、超過提醒門檻」的候選 → `notify` 一次（去抖，不洗頻）。

## 重用既有

- `services/screener.screen_watchlist`、`optimizer.run_auto_backtest`（**勿重造海選 / 回測**）。
- 既有 APScheduler（`bot_manager`）；`notify`；`automation_config` 的門檻語意（一律比對 OOS）。

## 測試 / 驗收（DoD）

- 純函式「把 screener 結果轉成 upsert 清單」可單元測試（同標的更新、排序、status 流轉）。
- `tests/test_opportunity.py`（upsert 冪等、OOS 排序、提醒門檻）；端點往返測試。
- 週期 job 用 monkeypatch 驗「會呼叫 screener 並寫表」，**不真的連網**。
- Alembic `upgrade head` 可建表；`pytest tests/ -q` 全綠。

## 風險 / 不要做

- **不**在整段歷史挑樣本內最佳——候選 EV / 勝率一律存 OOS（Phase 6 step-04 鐵則）。
- **不**讓週期 job 自動建 Bot / 自動上真錢（那是 step-06 人工核准的事）；本步只「收集 + 排名 + 持久化」。
- **不**把掃描間隔設太密把本機算力 / Alpaca 額度榨乾（漏斗式：先量價粗篩、後才回測）。
