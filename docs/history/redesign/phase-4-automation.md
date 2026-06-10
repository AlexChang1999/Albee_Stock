# Phase 4 — 全自動護欄（模式 B 自動駕駛）

> 目標：設「全局自動化規則」（EV 閾值 + 勝率門檻），在 APScheduler 盤前掃描中達標即自動建 Bot。
> 為何最後做：風險最高，須在前三階段（圖表可視化 + AI 推薦人工把關 + 監控中心）都穩定、且使用者
> 對模式 A 推薦建立信任後，才開放系統無人工確認自動配資。
> 回到總藍圖：[README.md](README.md)
>
> **狀態：✅ 已完成（2026-06-03）**。落地檔案：`config.py`/`.env.example` 加 `AUTO_DEPLOY_*` 規則
> （總開關預設關）、`backend/services/automation.py`（純函式 `plan_deployments` 雙門檻+去重+名額、
> 編排 `run_auto_deploy` 支援 force/dry_run）、`backend/routers/automation.py`（`GET /automation`
> 看規則名額、`POST /automation/run` 手動觸發）、`bot_manager.schedule_auto_deploy`（每日盤前 cron）、
> `main.py` 啟動掛載。實盤雙閘**完全不動**、自動部署全程 Paper。測試後端 93 綠（+5）。
> 未做（留後續，doc 未要求）：~~前端自動化規則面板~~（✅ 已補，監控中心 `AutomationPanel`：唯讀規則 + 手動試跑）、
> 規則改用 DB 表（目前走 `.env`，仍留後續——超出殘項範圍）。

---

## 一、現況

- 完全無模式 B：無全局自動化規則、無 EV 閾值自動建 Bot。目前全手動 `POST /bots`。
- 已有 EV 海選：`backend/services/optimizer.run_auto_backtest` + Phase 2 的 `screener` 漏斗。
- 已有排程：`backend/bots/bot_manager.py`（`BackgroundScheduler`，目前只排 Bot 定時檢查；
  `backend/main.py` `_resume_active_bots()` 重啟恢復）。
- 已有建 Bot 流程：`backend/routers/bots.py`。

## 二、缺口

1. 無「全局自動化規則」資料/設定（閾值、配資上限、最大同時 Bot 數）。
2. 無盤前掃描排程 job。
3. 無「達標自動 create_bot + 下單」串接。

---

## 三、要做的事

### 3.1 全局自動化規則
- 規則設定（先求簡單，可 `.env` 或一張 `automation_rules` 表，走 Alembic）：
  - `auto_deploy_enabled`（總開關，預設 `false`）
  - `ev_threshold`（如 150）、`winrate_threshold`（如 0.55）
  - `max_concurrent_bots`、`cash_per_bot`（配資上限，防一次梭哈）
- 預設**關閉**；使用者明確開啟才生效。

### 3.2 盤前掃描排程
- `bot_manager.py`（或新 `services/automation.py`）加一個 APScheduler cron job（盤前時刻）：
  1. 跑 Phase 2 漏斗 + EV 海選 → 得推薦清單。
  2. 篩 `EV > ev_threshold AND winrate > winrate_threshold` 且未超 `max_concurrent_bots`。
  3. 達標者用 `cash_per_bot` 自動 `create_bot` + `start_bot` 掛排程。
  4. 發通知（沿用 `services/notifier.py`，LINE/Discord）記錄自動建了什麼。

### 3.3 安全
- **實盤雙閘安全閥完全不動**：自動建的 Bot 下單一樣經 `alpaca_client.submit_market_order`，
  須 `ALPACA_BASE_URL` 實盤 + `ALLOW_LIVE_TRADING=true` 才送真錢，否則 Paper。
- 自動化總開關 `auto_deploy_enabled` 與實盤閘**獨立**：開自動化 ≠ 開實盤，預設都 Paper。

## 四、接點（重用既有）

- 海選/漏斗：`optimizer.run_auto_backtest`、Phase 2 `screener`。
- 排程：`backend/bots/bot_manager.py`（`scheduler`）。
- 建 Bot：`backend/routers/bots.py` 的建立邏輯。
- 通知：`backend/services/notifier.py`。
- 安全閥：`backend/services/alpaca_client.submit_market_order`（**不改**）。

## 五、驗證

1. 模擬 EV 超標 → 排程 job 自動建 Bot 且掛排程；EV 未達 → 不建。
2. `auto_deploy_enabled=false` 時排程不自動建任何 Bot。
3. `max_concurrent_bots` 上限生效（已達上限不再自動建）。
4. 自動建 Bot 全程 Paper（除非雙閘明確開實盤）；發出通知。
5. 後端 pytest 綠（補 `tests/test_automation.py`）。

## 六、完成後

更新 `CHANGELOG.md`「未發布」`### 新增`：模式 B 全局自動化規則 + 盤前掃描自動建 Bot
（附改動檔名、Alembic 遷移版本、測試數）。同步把 CLAUDE.md 開發階段表 Phase 5/6 狀態更新。
