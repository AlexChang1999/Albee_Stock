# Step 02 — 探勘橋：raw find → LLM 產候選

## 原目標錨點
README 壹「raw → 候選：全手動」。把「人讀收件匣 → 人打 /knowledge/propose」自動化：
本機 Ollama 讀素材摘要，判斷它在講哪種既有策略 + 建議參數，自動產 StrategyKnowledge candidate。

## 涉及檔
- 新 `backend/services/discovery.py`（本步主角）
- `backend/config.py`：`DISCOVERY_ENABLED`（預設 false）、`DISCOVERY_BATCH_SIZE`（預設 5）、
  `DISCOVERY_HOUR`（預設 7，盤前跑）
- `backend/models/raw_strategy_find.py`：沿用 status 流轉（new→triaged/built/discarded），**不加欄位**
  （若需記「產了哪筆 knowledge」再加 `knowledge_id` nullable，走 Alembic）
- `backend/bots/bot_manager.py` 或 `main.py`：排程掛載（仿 `schedule_auto_deploy` 體例）
- 新 `tests/test_discovery.py`

## Step
1. 純函式 `triage_find(find, llm_reply) -> dict`：解析 LLM 回覆成
   `{strategy_key, params, confidence, reason}` 或 None（解析失敗/不相關）。
   prompt 合約：只准從**既有策略清單**挑（餵 `GET /strategies` 同源清單），只准提參數。
2. `run_discovery_batch(db)`：取 `status=new` 的 find 至多 BATCH_SIZE 筆 →
   逐筆走 `llm.py`（連不上 = 整批跳過、不標記、下次再來）→
   有提案 → 呼叫 `strategy_generator` 同路徑建 candidate、find 標 `built`；
   無提案 → find 標 `discarded`（reason 落 DecisionLog 風格的 audit 欄或 log）。
3. 排程：每日 `DISCOVERY_HOUR` 跑一次；`DISCOVERY_ENABLED=false` 完全不掛。
4. 測試：monkeypatch llm —— 正常提案/亂回 JSON/不相關素材/Ollama 連不上 四情境；
   重跑不重複產 candidate（同 find 不二次 triage）。

## DoD
- 全測綠；`DISCOVERY_ENABLED=false` 時行為與 step-01 收工完全一致。
- 收件匣素材經一夜自動變成 candidate（或 discarded），CollectorPage 看得到狀態流轉。
- 每筆 triage 決策可回查（誰、何時、為什麼 built/discarded）。

## 邊界
- LLM 只提「既有策略 + 參數」；回覆要求生成程式碼 = 直接 discard。
- 不外送雲端（`LLM_ALLOW_CLOUD` 不動）；素材內容不進 prompt 以外的任何外部服務。
- 一晚最多 BATCH_SIZE 筆（防 LLM 跑整夜）。
