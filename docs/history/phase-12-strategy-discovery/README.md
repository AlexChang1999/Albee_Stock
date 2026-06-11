# Phase 12 — 策略自動探勘入庫管線（Strategy Discovery Pipeline）

> **文件狀態：藍圖階段（尚未開工）。** 把「raw 素材 → 候選策略 → 自動 OOS 驗證 → 人在迴路核准入庫」
> 串成一條自動化管線。零件幾乎都在（Phase 8 知識庫、Phase 10 蒐集員），本 Phase 是**接水管**，
> 不是造新引擎。
> **開工前必讀 [`../../ai-implementation-guardrails.md`](../../ai-implementation-guardrails.md)（防漂移 + 防 slop 合約）。**
> **強依賴 Phase 8（知識庫 candidate→validated→curated）/ Phase 10 step-04（collector 蒐集員）
> ——前置已完成，可開工。**
>
> 撰寫日期：2026-06-11。

---

## 〇、原目標錨點（為什麼做）

出自 [`../../remaining-work-backlog.md`](../../remaining-work-backlog.md) D 項與 Phase 11 README
「不在本 Phase 範圍」明記「策略自動探勘入庫 → 排 Phase 12」：

> Phase 12 = 把「raw 素材 → 候選策略 → 自動回測（OOS 閘）→ 人在迴路核准入庫」串成自動化。

使用者願景（Phase 10 原話延伸）：「開機 AI 就一直跑、一直找規律篩出合適策略」——Phase 10 蓋了
收料口（collector）與展示面（戰情頁），但**水管中段沒接**：raw 素材躺在收件匣等人手動策展，
候選策略要人手動觸發驗證。本 Phase 把中段自動化，**人只留在最後一道閘（晉升 curated）**。

---

## 壹、現況盤點（誠實）

| 管線段 | 現況 | 已有零件 | 缺口 → 哪一步補 |
|---|---|---|---|
| 收料（RSS 爬蟲） | ⚠️ 程式在、開關預設關、半手動 | `services/collector.py`（parse_rss/dedup/upsert/run_collector_scan）、`models/raw_strategy_find.py`（status: new→triaged→built→discarded） | 通電 + 驗收節流 → step-01 |
| raw → 候選 | ❌ 全手動（人讀收件匣再自己開 propose） | `strategy_generator.propose_params`（LLM 提案既有策略參數 → StrategyKnowledge candidate）、`routers/knowledge.py` POST /knowledge/propose | 自動橋接 → step-02 |
| 候選 → 驗證 | ⚠️ 有管線、要人逐筆按 | `evolution.validate_candidate`（walk-forward OOS → validated/rejected） | 自動批次驗證 → step-03 |
| 驗證 → 入庫 | ✅ 人在迴路已完整 | `/knowledge/{id}/promote`（人工晉升 curated）、LibraryPage 策展 UI | 漏斗可視化 + 提醒 → step-04 |
| 全程審計 | ⚠️ 交易有 DecisionLog，管線沒有 | `models/decision_log.py` | 管線事件落 log → step-02/03 內含 |

> ⚠️ **瓶頸與 Phase 10 相同：不在「多收素材」，在「證明不是運氣」。** 自動化只加速「產生候選 →
> 樣本外淘汰」的循環；**淘汰率高是健康的**（大部分網路策略點子過不了 OOS 閘是預期結果，不是 bug）。

---

## 貳、目標架構

```
RSS feeds（使用者自填，預設關）
   │  step-01：collector 通電（COLLECTOR_RSS_FEEDS + COLLECTOR_INTERVAL_MIN）
   ▼
raw_strategy_finds（status=new）
   │  step-02：探勘橋 discovery.py——本機 Ollama 讀素材 →
   │           strategy_generator 產候選（StrategyKnowledge candidate）
   │           raw find 標 triaged/built；產不出的標 discarded
   ▼
StrategyKnowledge（status=candidate）
   │  step-03：自動驗證排程——evolution.validate_candidate 批次跑
   │           walk-forward OOS 閘 → validated / rejected（全自動、有節流）
   ▼
StrategyKnowledge（status=validated）
   │  step-04：人在迴路（唯一人工閘，沿用既有 /knowledge/{id}/promote）
   │           漏斗報表進戰情頁 + notifier 提醒「有 N 筆 validated 待審」
   ▼
StrategyKnowledge（status=curated) → 既有 automation 模式 B 可部署 Paper Bot
```

**人工關卡不變**：晉升 curated 仍只能由人觸發；真錢仍受董事會核准 + 實盤雙閘把關。
本 Phase **不新增任何下單路徑**。

---

## 參、施工路線（5 步）

| 步驟 | 文件 | 主題 | 依賴 |
|------|------|------|------|
| 1 | [step-01-collector-power-on.md](step-01-collector-power-on.md) | collector 通電 + 禮貌驗收（robots/節流/UA/重複率） | Phase 10 step-04 |
| 2 | [step-02-discovery-bridge.md](step-02-discovery-bridge.md) | 探勘橋：raw find → LLM 產候選（自動 triage） | step-01、Phase 8 step-02 |
| 3 | [step-03-auto-validation.md](step-03-auto-validation.md) | 候選自動批次驗證（OOS 閘排程化） | step-02、Phase 8 step-04 |
| 4 | [step-04-funnel-report-hil.md](step-04-funnel-report-hil.md) | 漏斗報表 + 待審提醒（人在迴路收口） | step-03、Phase 10 step-01 |
| 5 | [step-05-e2e-honest-review.md](step-05-e2e-honest-review.md) | 端到端驗收 + 誠實去留檢討 | step-01~04 |

> **一次一步、一步一聚焦 commit，永遠對齊原目標。** step-01 先跑兩週真 feed 再開 step-02
> 也可以（有真素材才知道 LLM 提案橋要處理什麼髒資料）。

---

## 肆、明確界線（防 slop / 防漂移）

- **全程 Paper、雙閘不碰**：本 Phase 連 `submit_market_order` 都不該 import。
- **LLM 只在一個點出手**（step-02 讀素材產參數提案），走 `llm.py`、本機 Ollama、
  `LLM_ALLOW_CLOUD` 維持關；策略素材**不外送雲端**。
- **LLM 只提案「既有策略的參數」**（沿用 `strategy_generator` 的合約），**不自動生成新策略程式碼**
  ——新策略模組仍走人工 `strategy-builder` skill（人讀過素材後自己決定）。
- **挑選一律 OOS**：自動驗證沿用 `evolution.validate_candidate`，只看樣本外；不另立寬鬆標準。
- **淘汰是常態**：rejected 不刪、留統計（淘汰率是管線健康指標，step-05 驗收用）。
- **節流與禮貌**：收料守 robots.txt/UA/間隔；LLM 與回測批次有上限（不能因為自動化就把
  CPU 跑滿、把來源打爆）。
- **不重造**：收料用 `collector`、提案用 `strategy_generator`、驗證用 `evolution`、
  通知用 `notifier`、審計用 `DecisionLog`。
- schema 變更走 **Alembic**（`render_as_batch=True`）。
- **預設全關**：`COLLECTOR_INTERVAL_MIN=0`、探勘橋與自動驗證各自有開關且預設關——
  使用者明確填設定才通電（與 collector/political 同一哲學）。
- 中文註解；每步更新 `CHANGELOG.md`。

---

## 伍、完成定義（Phase DoD）

1. 填好 feeds 後，系統能**無人工介入**地：收料 → 產候選 → OOS 驗證 → 把 validated 排進待審清單。
2. 人在 LibraryPage 一鍵晉升/退回（既有 UI，不重做）。
3. 漏斗每段有計數可看（raw N → candidate N → validated N → curated N + 淘汰率）。
4. 全部排程預設關、開關都在 `.env`；關掉後行為與 Phase 11 收工時完全一致（回歸測試保證）。
5. step-05 誠實檢討：跑滿兩週，若「curated 增量 = 0 且 LLM 提案 OOS 通過率 < 既有網格掃描」，
   記錄結論並考慮降級（管線留著、排程關閉），不硬留。
