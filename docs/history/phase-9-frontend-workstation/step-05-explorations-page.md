# 步驟 5 — 探討/檢討頁 + 新增讀取端點

> 開工前讀 [AI 實作護欄合約](../../ai-implementation-guardrails.md)。回到 [Phase 9 索引](README.md)。
> **這是唯一需要碰後端的前端步驟**（探討目前完全沒有 GET 端點）。

## 目標

把 `explorations/` 檔案記憶（LLM 事後檢討）做成可瀏覽的頁 `/explorations`：列出路標、點開讀某篇檢討內容。

## 改動（只做這些）

### 後端（小端點）
- 新增 `backend/routers/explorations.py`：
  - `GET /explorations`：回路標清單（重用 `explorations.list_index_entries()`）。
  - `GET /explorations/{name}`：回某篇內容（重用 `explorations.read_exploration(name)`，**防穿越已內建**；讀不到回 404）。
- 掛上 `main.py`。

### 前端
- `api.js` 加 `getExplorations()` / `getExploration(name)`。
- 新增 `frontend/src/pages/ExplorationsPage.jsx`：左清單 + 右 markdown 內容。

## 重用既有（強制）

- `explorations.list_index_entries` / `read_exploration`（**已有、含防穿越**，不要自己讀檔、不要自己拼路徑）。
- 既有 markdown 顯示方式（若無，用輕量渲染，不引重型依賴）。

## 不要做（防 slop / 防漂移）

- **不要**自己用 `open()` / 拼路徑讀探討檔——一律經服務層的防穿越函式（安全紅線）。
- **不要**讓這頁能「寫 / 改 / 刪」探討（檢討由 `chat/postmortem` 產生；這頁**唯讀**）。
- **不要**為這頁加搜尋 / 標籤等沒被要求的功能（先做「列 + 讀」）。

## 測試 / 完成定義

- 後端 `tests/test_explorations_api.py`：清單 / 讀內容往返、404、**防穿越**（`../` 之類被擋）。
- 前端頁面渲染 Vitest（monkeypatch api）。
- `pytest tests/ -q` + `npm run test` 全綠。
