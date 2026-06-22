# Phase 10 — AI 交易公司（編排層 + 戰情頁）

> **文件狀態：構想 / 藍圖階段。** 在現有「嚴謹引擎室」外，補上「前台收料 + 因子報表 + 董事會核准 +
> 常駐化」，組成一間**看得到的「AI 交易公司」**：六個角色把工作往上交，最後由老闆（使用者）在一頁
> 核准「哪個 Bot 可以從 Paper 晉升到真錢」。
> **開工前必讀 [`../ai-implementation-guardrails.md`](../../ai-implementation-guardrails.md)（防漂移 + 防 slop 合約）。**
> **強依賴 Phase 6（誠實 OOS）/ Phase 7 step-07（防過擬合）/ Phase 8（知識庫進化）/ Phase 9（前端工作站）
> ——前置沒做完不要開始本 Phase。**
>
> 撰寫日期：2026-06-08。

---

## 〇、使用者願景（原話釐清）

> 「開機 AI 就依本機算力一直跑策略機器人、一直找變化中的規律（量、震幅）篩出合適策略；由 AI 寫的程式
> 判斷哪支股票、量進多少、何時獲利了結。回到 2010 回測驗證會不會賺、勝率高不高，把影響的數據列成數值表。
> AI 主動問我要不要把某策略搬去真金帳戶。想用『一間 AI 公司』來做：市場蒐集員（上網找策略）、蒐集員主管
> （把影響因子列成數值表）、策略員（碰到哪些數值可進場）、策略主管（拿過去市場回測）、政治專討員
> （川普發文頻率/內容對股市的規律）、回測主管（決定哪些上交老闆）。每個 Bot 有自己的判斷準則
> （程式碼/比例/數據庫），我能讓 AI 編輯微調。」

本輪釐清（與使用者一問一答後定案）：
- 市場蒐集員用**爬蟲**收策略文章；**開機就常駐自跑**。
- 歷史股價**不爬**（用既有 yfinance API，回得到 2010；爬股價是反模式）。
- 政治專討員用 **Discord bot** 偵測川普貼文判讀（含發文頻率特徵）。
- 判讀政治文 / 文章摘要用**本機 Ollama**（免費、離線，`LLM_ALLOW_CLOUD` 維持關）。
- 架構走**路 A：編排層 + 戰情頁**，**不做**自治多代理（CrewAI 式）swarm。

---

## 壹、可行性結論（誠實）

**可行，且引擎室約 75% 已存在、且嚴謹**（OOS 防過擬合、含成本回測、組合風控、海選漏斗、模式 B 自動部署、
知識庫進化、本機 LLM 助手都在）。缺的是「前台收料 + 因子報表 + 董事會核准 + 常駐化」。

六個角色**不是六個自治 AI**，而是**既有服務上的「部門/關卡」**，LLM 只在安全的點出手（找點子、消化政治
情緒、事後檢討）。

| 公司角色 | 現況 | 已有零件 / 落在哪 | 缺口 → 哪一步補 |
|---|---|---|---|
| 策略員（偵測進場門檻） | ✅ 完整 | `strategies/`、`regime.py`、`meta_label.py` | 無（step-01 呈現） |
| 策略主管（拿歷史回測） | ✅ 完整、嚴謹 | `backtest_engine.py`、`optimizer.py`、`validation.py` | 無（step-01 呈現） |
| 回測主管（決定上交誰） | ✅ 半成品 | `screener.py`、`automation.py`、`evolution.py` | 機會清單持久化 → step-02 |
| 蒐集員主管（因子數值表） | ⚠️ 因子有算、不存表 | `regime_features.py`（7 因子） | 因子表 + 報表 → step-03 |
| 市場蒐集員（上網找策略） | ❌ 無網搜 | — | 爬蟲收料 → step-04 |
| 政治專討員（川普推文） | ❌ 只有新聞情緒打分 | `screener.py` sentiment | Discord 事件流 → step-05 |
| 老闆一頁核准進真錢 | ⚠️ 只能改 `.env` 重啟 | `alpaca_client.py` 雙閘、`EvolutionPage.jsx` 策展核准 | 董事會核准頁 → step-06 |
| 開機常駐自跑 | ⚠️ 記憶體排程、關 app 就停 | `bot_manager.py`（APScheduler） | step-02 掃描 + step-07 開機自啟 |
| 每個 Bot 準則可微調 | ✅ 半成品 | `presets.py`、`EditBotDialog` | 無（沿用既有編輯，不擴成任意程式碼） |
| 回到 2010 回測 | ⚠️ 設定切換即可 | `config.py` `DATA_SOURCE=yfinance` | 本 README 註記，非獨立步 |

> ⚠️ **瓶頸不在「多收策略 / 多接訊號」（很容易），在「證明它不是運氣 + 不偷看未來」。**
> 任何新來源（爬蟲、Discord、LLM 提案）產出的策略點子，**一律過 Phase 6 OOS + Phase 7 step-07 防過擬合閘**
> 才准進 Paper；進真錢再過 step-06 人工核准 + 既有實盤雙閘。**這是本 Phase 最重要的紀律。**

---

## 貳、目標架構（編排層，不是 swarm）

```
[市場蒐集員 step-04]        [政治專討員 step-05]
  爬蟲收策略文字              Discord 讀川普文 → 本機 Ollama 判讀
        │                          │ （事件/頻率分數，當煞車不當油門）
        ▼                          ▼
  strategy-builder            event_risk.assess_event_risk（既有，只縮部位/不開新倉）
   寫成策略模組                      │
        │                          │
        ▼                          ▼
 ┌──────────────────── 引擎室（已存在，鐵則守門）────────────────────────┐
 │ 策略員 strategies/ → 策略主管 optimizer/backtest_engine（含成本/隔日成交） │
 │ → 回測主管 validation 樣本外 OOS 防過擬合 → screener 漏斗 EV 閘           │
 └────────────────────────────────┬──────────────────────────────────────┘
        │ step-03 把過程因子落表（蒐集員主管報表，列成數值/表）
        ▼
  常駐探勘 + 機會清單（step-02，排名候選存 DB，好策略不漏掉、關 app 也留著）
        │
        ▼
  董事會核准頁（step-06：AI 主動提醒 → 老闆一頁核准 Bot 上真錢）
        │  ★ 核准只是「多一道人工閘」；真錢下單仍受 alpaca 實盤雙閘把關，UI 不繞過
        ▼
  公司戰情頁（step-01：把上面每個部門狀態畫成一頁，看得到的公司）
```

---

## 參、施工路線（7 步）

| 步驟 | 文件 | 主題 | 依賴 |
|------|------|------|------|
| 1 | [step-01-war-room-orchestrator.md](step-01-war-room-orchestrator.md) | 戰情室編排 + 公司戰情頁（看得到的公司） | Phase 9 |
| 2 | [step-02-continuous-scan-opportunities.md](step-02-continuous-scan-opportunities.md) | 常駐探勘 + 機會清單持久化 | Phase 6、step-01 |
| 3 | [step-03-factor-tables-report.md](step-03-factor-tables-report.md) | 因子數值表 + 報表（蒐集員主管） | Phase 7、step-01 |
| 4 | [step-04-market-collector-scraper.md](step-04-market-collector-scraper.md) | 市場蒐集員（爬蟲收料） | step-02、strategy-builder |
| 5 | [step-05-political-discord-watcher.md](step-05-political-discord-watcher.md) | 政治專討員（Discord 事件流） | Phase 7 event_risk |
| 6 | [step-06-boardroom-promotion.md](step-06-boardroom-promotion.md) | 董事會核准頁（Bot 進真錢，人在迴路） | step-01、Phase 8 策展 |
| 7 | [step-07-always-on-autostart.md](step-07-always-on-autostart.md) | 開機常駐化（Windows 自啟） | step-02 |

> **建議落地順序：01 → 02 → 06 →（骨幹打通）03 → 07 → 04 → 05。**
> 先把「看得到的公司 + 常駐機會清單 + 老闆核准頁」這條最有價值骨幹打通；爬蟲與政治員（最軟、最易 slop）
> 排最後，且一律走同一道 OOS 閘 + 人工核准。**一次一步、一步一分支一 commit，永遠對齊原目標。**

---

## 肆、明確界線（防 slop / 防漂移）

- **全程 Paper + 實盤雙閘絕不更動**；step-06 的 UI 核准 **≠** 放行真錢（真錢仍須
  `ALPACA_BASE_URL` 實盤 + `ALLOW_LIVE_TRADING=true`，由 `alpaca_client.submit_market_order` 把關）。
- 任何來源（爬蟲 / Discord / LLM）產出的策略點子，**一律過現有 OOS 驗證閘**才進 Paper。
- **EV 看樣本外 + 含成本**，不看樣本內、不只看勝率。
- **情緒 / 政治只當煞車輔助**，不當主進場訊號；連不上 best-effort 不阻斷。
- **不重造**：抓 K 線用 `market_data`、回測用 `backtest_engine`、LLM 用 `llm.py`、下單用
  `submit_market_order`、因子用 `regime_features`、通知用 `notify`。
- schema 變更走 **Alembic**（`render_as_batch=True`），不手動 ALTER。
- **不做自治多代理**：六角色是編排關卡 + 人在迴路，不是會自己亂跑、自我晉升的 agent swarm。
- 每加一層（蒐集 / 政治 / 報表）要能在 OOS 證明加分，加不了就砍（砍掉也記 `CHANGELOG`）。
- 中文註解；本機優先（Ollama / yfinance / Alpaca Paper）。
