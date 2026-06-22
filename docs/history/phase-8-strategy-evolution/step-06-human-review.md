# 步驟 6 — 人在迴路審核流程

> 開工前讀 [AI 實作護欄合約](../../ai-implementation-guardrails.md)。回到 [Phase 8 索引](README.md)。

## 目標

把「晉升決定權留在人手上」做成明確流程：使用者檢閱通過驗證的候選 → 晉升為 curated / 退回 / 送部署，
並把「採用 / 淘汰理由」寫進記憶。這是「人在迴路」與防漂移的最後一道。

## 概念

human-in-the-loop curation。AI 只提案 + 驗證 + 排序；**狀態從 validated → curated 的那一步只能由人觸發**。

## 改動（只做這些）

- `backend/routers/knowledge.py` 加：
  - `POST /knowledge/{id}/promote`（validated → curated，**需人觸發**）。
  - `POST /knowledge/{id}/reject`（→ rejected，附理由）。
- 採用 / 淘汰理由用 **`explorations.write_exploration`** 風格留檔（重用既有檔案記憶，連結 knowledge id），形成可追溯軌跡。

## 重用既有

- `explorations` 檔案記憶（含 INDEX 路標、防穿越）——**沿用**，不另造記錄機制。
- 知識庫 status 流轉（step-01 定義）。

## 不要做（防 slop / 防漂移）

- **不要**讓系統自動把策略從 validated 升成 curated（違反「人在迴路」決策；護欄第柒節）。
- **不要**為審核發明複雜的工作流引擎——就是 promote / reject 兩個動作 + 留理由。

## 測試 / 完成定義

- `tests/test_knowledge.py` 擴充：promote / reject 狀態流轉正確；理由寫入 explorations 往返。
- 自動流程**到 validated 為止**，curated 一定要人觸發（測試斷言無自動晉升路徑）。
- `pytest tests/ -q` 全綠。
