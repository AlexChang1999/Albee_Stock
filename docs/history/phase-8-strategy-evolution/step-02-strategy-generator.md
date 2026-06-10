# 步驟 2 — 策略生成器（skill + LLM 提案）

> 開工前讀 [AI 實作護欄合約](../../ai-implementation-guardrails.md)。回到 [Phase 8 索引](README.md)。

## 目標

依知識庫的「理論 / 場景」描述，由 LLM **草擬**新候選策略或參數組，產出進「候選區」（`status=candidate`）。
**人在迴路**：草擬不等於上線，未過驗證（step-04）不准進策展庫。

## 概念

LLM 輔助策略研究迴路（LLM-assisted hypothesis generation）。生成只負責「提出假設」，不負責判斷好壞。

## 改動（只做這些）

- 新增 `backend/services/strategy_generator.py`：
  - `propose_params(strategy_key, scenario, n) -> list[dict]`：請 LLM 依場景描述建議幾組參數（限定既有 `STRATEGY_REGISTRY` 的策略鍵）。
  - 產出寫入 `StrategyKnowledge`（`status=candidate`），**不跑回測、不部署**。
- 新增端點 `POST /knowledge/propose`（觸發提案）。
- 「全新策略邏輯」（非既有 8 種的參數調整）→ 走既有 `strategy-builder` skill 由人驅動，**不在後端自動生成 .py**（避免自動寫碼失控）。

## 重用既有

- `llm.get_client/complete/cloud_blocked`（含外送安全閥，**沿用**不自寫 LLM 呼叫）。
- `chat.py` 注入記憶 / 解析 JSON 的慣例（`parse_*` 純函式）。
- `STRATEGY_REGISTRY`（提案只能用既有策略鍵）。

## 不要做（防 slop / 防漂移）

- **不要**讓後端自動生成並寫入新的策略 `.py` 檔（自動寫碼 = 失控源頭）；新策略邏輯一律走 skill + 人。
- **不要**讓生成器直接跑回測或部署（職責分離：生成 ≠ 驗證 ≠ 部署）。
- **不要**繞過 `LLM_ALLOW_CLOUD` 外送閘。
- LLM 連不上 → 優雅回 400，不阻斷其他功能（沿用 chat.py 慣例）。

## 測試 / 完成定義

- `tests/test_strategy_generator.py`：monkeypatch LLM 回傳，驗證解析出合法參數、寫入 candidate、非法策略鍵被擋。
- 空 / 連不上 LLM 回 400；`pytest tests/ -q` 全綠。
