# Phase 10 step-04 — 市場蒐集員（爬蟲收料）

> 開工前必讀 [`../ai-implementation-guardrails.md`](../../ai-implementation-guardrails.md)。
> 依賴：step-02（持久化骨架）、`strategy-builder` skill。

## 目標 / 概念

讓「市場蒐集員」定時從網路收**策略描述文字**進 DB，當人 / skill 把它寫成可跑策略的素材。
**爬蟲只負責收料、不負責驗證**——收回來的點子一律走既有引擎證明自己。

## 問題 / 改動

- 新增 `backend/services/collector.py`：**優先官方 API / RSS**（Reddit、部落格 RSS）；必要時靜態頁
  `requests` + `beautifulsoup4`。抽純函式「HTML / JSON → 策略素材 dict」好測。
- 新增 model `backend/models/raw_strategy_find.py`（來源 URL / 標題 / 摘要 / 抓取時間 /
  狀態：new/triaged/built/discarded）。
- 沿用 step-02 的 APScheduler 週期 job 機制加一個收料 job；發現新料 `notify`。
- **落地路徑**：收到的料 → 人 / `strategy-builder` skill 寫成 `strategies/<name>.py` → **過 OOS 閘**
  （optimizer / validation）→ 達標才進候選（step-02 機會清單）。本步**不自動寫策略碼、不自動部署**。

## 重用既有

- `notify`；step-02 週期 job 機制與 DB 模式；`strategy-builder` skill（**唯一**寫新策略碼的路徑）。
- 股價**不爬**——歷史 / 即時資料一律走既有 `market_data.get_bars`（yfinance 回得到 2010）。

## 測試 / 驗收（DoD）

- 純函式解析測試用**本地樣本 HTML / JSON**（不連網）；`tests/test_collector.py`（解析、去重、status 流轉）。
- 新依賴 `beautifulsoup4`（純 Python、Windows 安全）寫進 `requirements.txt`，step 明確要求才裝。
- `pytest tests/ -q` 全綠；Alembic `upgrade head`。

## 風險 / 不要做

- **不**爬股價（反模式：慢 / 易封 / 髒）——用 `market_data` / yfinance。
- **不**自動把爬來的文字變成上線策略（必經 strategy-builder + OOS 閘 + 人工）。
- **尊重 robots.txt / rate limit / 服務條款**；加 User-Agent 與節流，避免封 IP。best-effort，連不上不阻斷其他功能。
- **不**在這步引入重型爬蟲框架（scrapy / playwright）除非確有動態站需求——先用最輕的能跑就好。
