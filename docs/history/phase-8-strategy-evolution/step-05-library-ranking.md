# 步驟 5 — 策略庫排行 + 使用時機說明

> 開工前讀 [AI 實作護欄合約](../../ai-implementation-guardrails.md)。回到 [Phase 8 索引](README.md)。

## 目標

把通過驗證的策略排成榜（依 OOS EV），並為每個附上**「使用時機說明」**——
回答使用者願景裡的「給他們使用時機說明」。

## 概念

策展（curation）+ 狀態親和性（regime affinity，來自 Phase 7）+ LLM 寫的人類可讀說明。

## 改動（只做這些）

- `backend/routers/knowledge.py` 加 `GET /knowledge/ranking`（依 `oos_metrics.expected_value` 排序，可篩 status）。
- 新增 `usage_note` 產生：用 Phase 7 的狀態親和性（這策略在哪種市場狀態 OOS 最好）+ LLM 寫一句白話「何時用」。
  寫回 `StrategyKnowledge.usage_note` / `regime_affinity`。
- 「好策略一鍵轉 Bot」：**重用** `createBot` + `startBot` 流程（不另造部署邏輯）。

## 重用既有

- `backtest_runs` 依 EV 排序的既有寫法（`routers/presets.py`）。
- Phase 7 step-03 的狀態→策略對照（狀態親和性來源）。
- `llm.complete`（寫 usage_note，受外送閘約束）。
- 既有建 Bot / 啟動流程（`routers/bots.py`）。

## 不要做（防 slop）

- **不要**用樣本內 EV 排序（一律 OOS）。
- **不要**自造新的「部署」路徑——轉 Bot 走既有 createBot+startBot。
- **不要**把 usage_note 寫成 LLM 長篇大論——一兩句、可執行。

## 測試 / 完成定義

- `tests/test_knowledge.py` 擴充：ranking 依 OOS EV 排序、篩 status；usage_note 寫入往返（monkeypatch LLM）。
- `pytest tests/ -q` 全綠。
