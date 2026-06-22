# Phase 14 — 公司可操作化 + 漏斗透明 + 個股策略擂台

> 觸發來源：使用者三個核心困惑——「每股一個 bot 一策略不是我要的」「蒐集到的是文字怎麼變策略、怎麼防 AI 唬爛」「蒐集很多只有 5 個晉升、其餘去哪了」。完整診斷與計畫見 plan 檔（`bot-5-ai-5-golden-wirth.md`）。

## 原目標錨點

系統其實**早就具備**「每檔股票用多策略回測 + 虛擬交易找最佳模型」的能力，問題不是缺功能，而是：

1. **整條探勘管線預設全關**（`COLLECTOR_INTERVAL_MIN=0`、`DISCOVERY_ENABLED`/`AUTO_VALIDATE_ENABLED`/`AUTO_DEPLOY_KNOWLEDGE_ENABLED`/`BOT_REVIEW_ENABLED`=false）→ 沒有東西在流動，看到的 ~5 curated 是手動種的。
2. **後端能力沒有前端入口**：collector 收料 / discovery 探勘橋 / auto-validate / auto-deploy / `/knowledge/deploy` 多為排程專用或孤兒端點，畫面上驅動不了。
3. **漏斗中途與淘汰項被前端藏起來**：rejected/discarded 都留有理由（`triage_note` / `oos_metrics`）但散落、不可見；LibraryPage 只給 curated/validated。

**決策（使用者拍板）**：① 管線採**人工逐步按鈕**推進（排程維持關閉，擬人操作）。② 每股策略**兩者都要**（auto-backtest 排名 + 部署成 paper bot 實跑）。③ 全部分階段。

## 做了什麼（對齊計畫）

### 後端
- **`force` 閘**：`run_discovery_batch` / `run_auto_validate` / `run_auto_deploy_knowledge` 加 `force=False`，只略過 `*_ENABLED` 提早返回，**其餘安全閘全留**（LLM 外送閘、判準零修改、paper-only）。`run_collector_scan` 改回統計 dict（給手動端點回報）。
- **`discovery.triage_one(db, find, client)`**：把單筆 triage 抽成共用純邏輯（防幻覺約束不變：只准既有策略 + 參數鎖 schema + 值夾範圍 + 信心門檻 + 不生成新碼）。`run_discovery_batch` 改用它。
- **新路由 `backend/routers/discovery.py`**（掛進 `main.py`）：`POST /discovery/run`、`/discovery/triage/{find_id}`、`/discovery/validate-batch`、`/discovery/auto-deploy`。
- **collector 路由**：`_serialize` 補 `triage_note`/`knowledge_id`；新增 `POST /collector/scan`。
- **knowledge 路由**：`/knowledge/{id}/validate` 加 `use_basket`——用 `AUTO_VALIDATE_SYMBOLS` 完整籃子 + `AUTO_VALIDATE_DAYS`，補上「人工驗證偷懶用單檔、自動驗證用 38 籃子」的嚴謹度落差。

### 前端
- **CompanyPage 漏斗卡 → 操作台**：5 顆「跑一次」鈕（收料 / 探勘 / 驗證 / 部署 / 審查），跑完重抓 overview，漏斗數字當場跳動；連結改指 `/funnel`。
- **CollectorPage**：每筆 new/triaged 加「🔬 試轉策略」鈕（打 `/discovery/triage/{id}`）、「探勘橋」決策欄（`triage_note` + 候選連結）、改寫防唬爛文案。
- **KnowledgeCard**：秀 `oos_metrics` 出處（驗證範圍籃子 N 檔 / walk-forward 折數 / 回看天數）。
- **EvolutionPage**：驗證預設完整籃子（與自動路徑同嚴謹度），可切單檔（快）。
- **新頁 FunnelPage（`/funnel`）**：兩條流水線各階段可點開看實際項目 + 淘汰理由（回答「其餘去哪了」）。
- **新頁 StockArenaPage（`/stock-arena`）**：輸入股票 → `/auto-backtest` 跑遍 9 策略排名 → 每列「部署成 paper bot」。
- **LibraryPage**：切換補 candidate/rejected；curated 卡加「部署到標的」鈕（`/knowledge/{id}/deploy`，補孤兒端點）。
- **BotReviewPage**：適配表加「依標的分組」檢視（每股策略競賽排名）。

## 誠實邊界（防 slop / 防漂移）

- **不開任何排程旗標**：本階段零改 `*_ENABLED` 預設；自動駕駛是日後另一階段（使用者已選人工逐步）。
- **手動端點不拆安全閘**：`force` 只跳過 `*_ENABLED`；LLM 外送閘 / paper-only / 驗證判準一字不改。
- **純呈現層不重算**：前端只顯示後端數字，EV / 驗證一律後端算。
- **零 schema 變更**：唯一資料面動作是把既有欄位 `triage_note`/`knowledge_id` 帶進 API 輸出（免 Alembic）。

## DoD（完成定義）

- [x] 後端 `force` + `triage_one` + 新路由 + collector scan/serialize + knowledge `use_basket`，`py_compile` + import 通過。
- [x] 前端 7 頁 + 1 元件 + api.js，`vite build` 乾淨、`eslint` 對新檔零錯。
- [x] 測試：`tests/test_discovery.py`（triage_one/force）、`test_discovery_api.py`（路由 + 404/400 閘）、`test_collector.py`（scan 回統計 + triage 欄位）、`test_auto_validate.py` / `test_auto_deploy_knowledge.py`（force 繞過）。
- [ ] 擬人 E2E 走查（plan 檔 Phase 5 步驟）：本機起前後端，逐關按鈕推進，FunnelPage 數字對齊 `/company/overview`。

## Phase 0 觀察基準（待回填）

開機讀 `GET /company/overview` 的 `discovery_funnel`，把 raw / knowledge 各狀態計數記進
`observation-baseline.md`，作為「東西去哪了」的真資料快照；之後每跑一關回填一次，證明數字真的在動。
