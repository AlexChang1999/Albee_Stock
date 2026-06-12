# Phase 10 step-06 — 董事會核准頁（Bot 進真錢，人在迴路）

> 開工前必讀 [`../ai-implementation-guardrails.md`](../../ai-implementation-guardrails.md)。
> 依賴：step-01（戰情頁）、Phase 8 人在迴路策展模式。

## 目標 / 概念

補「**老闆一頁核准 + AI 主動問**」：AI 偵測「某 Bot 表現達標、建議上真錢」→ 主動提醒 →
使用者在一頁**核准 / 退回**。呼應護欄「不確定就停、晉升一律人工」。

## 問題 / 改動

- 新增 model 欄位 / 表記錄 Bot 的**晉升狀態**（paper / proposed_live / approved_live / rejected）+ 理由，
  走 Alembic 遷移。
- 新增 `backend/routers/promotion.py`：`GET /promotions`（待核清單）、`POST /promotions/{bot_id}/propose`
  （系統提議，附達標證據：OOS EV、實盤 Paper 績效）、`/approve`、`/reject`（附理由）。
- AI **主動提醒**：沿用 `_build_reminders` 模式掃出「Paper 表現達標但未提議上真錢」者 + `notify`。
- 前端新增核准頁（比照 `EvolutionPage.jsx` 的晉升 / 退回 UX），掛 sidebar。

## 重用既有

- `routers/presets.py` 的 `_build_reminders` 提醒模式 + `notify`；`EvolutionPage.jsx` 策展 UX。
- `services/performance` 績效指標；機會清單（step-02）/ 戰情頁（step-01）。

## 測試 / 驗收（DoD）

- `tests/test_promotion.py`（狀態流轉 propose→approve/reject、冪等、理由寫入、提醒命中條件）。
- 前端 `PromotionPage.test.jsx`（待核渲染、核准 / 退回觸發）。
- `pytest tests/ -q`、`npm run test` 全綠；Alembic `upgrade head`。

## 風險 / 不要做（★安全紅線）

- **UI 核准是「多一道人工閘」，不是放行真錢的開關**。真錢下單仍須
  `ALPACA_BASE_URL` 實盤 + `ALLOW_LIVE_TRADING=true` 雙閘，由 `alpaca_client.submit_market_order` 把關。
  **本步完全不碰那道安全閥、不改 `alpaca_client`、不改 `.env` 語意。**
- **approved_live 只是「人已同意」的狀態旗標**；實際是否送真錢，仍是雙閘說了算（兩者 AND）。
- **不**做自動晉升路徑——一律人工點按。
