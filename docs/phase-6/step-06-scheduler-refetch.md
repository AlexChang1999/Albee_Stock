# 步驟 6 — 排程每輪重查 Bot

> 修 **P7**（排程持有過期 ORM 物件）。回到 [Phase 6 索引](README.md)。

## 目標

讓「修改 Bot 設定 / 拖曳水位線改風控」對**執行中**的 Bot 立即生效，不必重啟後端。

## 問題（現況）

`bot_manager.start_bot` 把 `args=[bot]` 鎖死在排程建立的那一刻：

```python
self.scheduler.add_job(run_bot_once, "interval", args=[bot], ...)
```

`run_bot_once` 之後每次跑，讀的 `bot.strategy` / `bot.params` / `bot.take_profit_pct` …都是**那顆舊物件**的值。
只有 `_persist_peak` / `_mark_checked` 例外（它們有用 `bot.id` 重查）。
後果：使用者用 `PUT /bots/{id}/risk` 拖曳水位線改了止損，執行中的排程毫無反應，直到後端重啟——
這讓 Phase 1「拖曳水位線連動風控」對運作中的 Bot 形同失效。

## 改動

1. **`backend/bots/bot_manager.py`** 的 `start_bot`：`add_job` 改傳 **`args=[bot.id]`**（整數），不再傳 ORM 物件。
2. `run_bot_once(bot_id: int, ignore_market_hours=False)`：函式開頭用 `bot_id` 開 session 重查最新 Bot：
   - 查不到（已被刪）→ 移除該 job（`bot_manager.stop_bot(bot_id)`）並 return，避免殭屍排程。
   - 查到 → 用這顆**新鮮的** Bot 跑後續邏輯。
3. **`backend/routers/bots.py`** 的 `run_bot_now`：改傳 `bot.id` 給 `run_bot_once`。
4. 連帶簡化：`_persist_peak` / `_mark_checked` 既然 run 內已是新鮮物件，可直接在同一 session 更新（視重構幅度，保持小改動亦可）。

## 重用既有

- `SessionLocal` 重查慣例（`_persist_peak` / `_mark_checked` 已在用）。
- `bot_manager.stop_bot`（移除殭屍 job）。

## 測試

- 改 `tests/test_bot_manager.py`：建 Bot → 排程 → 改風控（DB）→ 跑一次，驗證用的是**新風控值**（monkeypatch `check_exit` 斷言收到的門檻是新值）。
- 刪除 Bot 後再觸發一次 → 安全 no-op，且該 job 被移除。

## 驗收

- 啟動 Bot → `PUT /bots/{id}/risk` 改止損 → 下一輪檢查即用新門檻（搭配 [步驟 8](step-08-decision-audit-log.md) 的 `decisions` 可直接看到）。
- 刪除執行中的 Bot 後，排程不再殘留、不再對已刪 Bot 報錯。
