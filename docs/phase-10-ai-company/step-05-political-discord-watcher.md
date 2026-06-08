# Phase 10 step-05 — 政治專討員（Discord 事件流）

> 開工前必讀 [`../ai-implementation-guardrails.md`](../ai-implementation-guardrails.md)。
> 依賴：Phase 7 `event_risk`（情緒當煞車）。

## 目標 / 概念

讓「政治專討員」用 Discord bot 偵測頻道內川普貼文 → 本機 Ollama 判讀 → 產出**事件 / 頻率分數** →
餵進**既有風險煞車**。定位是**煞車（降風險、縮部位、不開新倉），不是油門（不據此猜方向重壓）**。

## 問題 / 改動

- 新增 `backend/services/political.py`：純函式「貼文文字 + 時間戳 → 事件分數 / 頻率特徵」（好測）；
  判讀走本機 Ollama。
- 新增一個 Discord bot runner（`discord.py`，獨立常駐或排程拉取），`on_message` 取頻道新貼文 → 判讀 → 落表。
- 新增 model `backend/models/political_event.py`（來源 / 內容摘要 / 分數 / 時間戳 / 判讀）。
- 分數接 `event_risk.assess_event_risk` 的輸入（與既有 sentiment 管線同分工：否決 + 縮部位）。

## 重用既有

- `llm.get_client` / `llm.complete`（**本機 Ollama，守外送閘**，`cloud_blocked` 不繞過）。
- `services/event_risk.assess_event_risk`（**既有風險煞車，勿重造**）；`notify`。

## 測試 / 驗收（DoD）

- 純函式判讀 / 頻率測試用**固定樣本貼文**（monkeypatch LLM，不連網、不連 Discord）；`tests/test_political.py`。
- 驗「分數 → size_factor」確實接到 `event_risk`（縮部位 / 不開新倉），且無情緒時 best-effort 不阻斷。
- `pytest tests/ -q` 全綠；Alembic `upgrade head`。新依賴 `discord.py` 寫進 `requirements.txt`。

## 風險 / 不要做（★本步最危險）

- **來源難題**：Discord bot **只能讀「它所在的頻道」**，不會自己去 Truth Social / X 抓川普。需先有把川普
  貼文同步進來的 Discord 頻道（RSS→webhook / 鏡像頻道 / 或直接接 X API 跳過 Discord）。**藍圖先講清楚這前提。**
- **領域誠實**：「貼文 → 漲跌」**最易過擬合、無乾淨 point-in-time 對齊資料可誠實回測**（呼應 `event_risk`
  被標 non-verifiable）。**只當煞車、不當主進場訊號**；想當油門必須當「實驗、小錢、嚴格隔離」並先過 step-07。
- **不**重壓方向、**不**因為高頻發文就放大部位（factor 上限 1.0）。
