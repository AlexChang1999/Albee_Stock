# 步驟 1 — 策略知識庫資料模型

> 開工前讀 [AI 實作護欄合約](../../ai-implementation-guardrails.md)。回到 [Phase 8 索引](README.md)。

## 目標（服務原目標哪一條）

給「策略 + 它的理論 / 場景 / 使用時機 / 驗證狀態」一個持久家。這是「可成長策略庫」的容器，
也是後續組合、排序、審核的單一資料來源。

## 概念

策略知識庫（Strategy Knowledge Base）+ 驗證狀態機（candidate → validated → curated / rejected）。

## 改動（只做這些）

- 新增 model `StrategyKnowledge`（`backend/models/strategy_knowledge.py`）：
  `id`、`name`、`theory`（理論來源）、`scenario`（適用場景）、`usage_note`（使用時機說明）、
  `strategy_key`、`params`(JSON)、`composite_of`(JSON nullable，組合的子策略清單)、
  `status`（candidate/validated/curated/rejected）、`oos_metrics`(JSON nullable)、
  `regime_affinity`(JSON nullable，連 Phase 7 狀態)、`created_at`、`updated_at`。
- 走 **Alembic** 遷移（`render_as_batch=True`）。
- 新增 `backend/routers/knowledge.py`：`GET/POST/PUT/DELETE /knowledge`（基本 CRUD）。

## 重用既有

- `strategy_presets` / `backtest_runs` 的 model + router 寫法（照抄結構，別自創風格）。
- Alembic batch 遷移範例（`alembic/versions/` 既有 add-table 遷移）。

## 不要做（防 slop）

- **不要**一次塞滿用不到的欄位（如評分演算法中間值）——只放索引 / 顯示 / 驗證需要的。
- **不要**自己 `ALTER TABLE`，一律 Alembic。
- **不要**在這步就接生成 / 組合邏輯（那是 step-02/03）。

## 測試 / 完成定義（DoD 通用項見護欄第陸節）

- `tests/test_knowledge.py`：CRUD 往返、status 流轉、404。
- Alembic `upgrade head` 成功；`pytest tests/ -q` 全綠。
