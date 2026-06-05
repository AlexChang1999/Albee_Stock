# Phase 6 — 可信度地基（Trustworthiness Foundation）

> 本資料夾是 Phase 6 的施工總藍圖：把現有「廣而淺」的系統，**收斂成一台將來能被信任、
> 可託付真錢的本機自動交易機器人**。原則一句話：**讓「回測看到的 EV」≈「實盤真的會發生的事」。**
>
> 撰寫日期：2026-06-05。施工原則沿用專案慣例：**一步一步改、每步獨立 commit + 測試、各自更新
> `CHANGELOG.md`、純函式 + monkeypatch 測試、schema 走 Alembic、中文註解、不破壞既有回傳（純增量）。**

---

## 〇、為什麼要做（不是長新功能，是補地基）

專案經過 5 個 Phase 的堆疊，功能面幾乎全數出貨：8 種策略、walk-forward 回測、風控出場、
雙軌 AI（模式 A 一鍵部署 / 模式 B 自動部署）、深藍終端機 UI、本機 LLM 助手、explorations 檔案記憶。

但完整讀過程式碼後，發現**作為「將來要跑真錢」的自動交易機器人，科學地基有 8 道致命縫隙**——
這些縫隙在 Paper 模式看不出來，一旦切實盤就會系統性虧損或行為不一致。

使用者已明確選定方向：
1. **先鞏固可信度**（正確性優先，不長新功能）。
2. **終局要跑真錢**（成本/風控/樣本外都要做到嚴謹）。
3. **把「算了卻沒人用」的 AI 情緒層真正接進決策**。

> 配套閱讀：[`../human-vs-ai-operation.md`](../human-vs-ai-operation.md) — AI 操作 vs 一般人操作的落差、
> 以及「是否真的拿去跑真盤」的分階段上線建議。Phase 6 正是這條上線路線的「階段 0」前置工程。

---

## 壹、已確認的根本問題（讀碼實證，非臆測）

| # | 問題 | 證據（檔案 / 行為） | 對「跑真錢」的後果 | 對應步驟 |
|---|------|------------------|-------------------|---------|
| P1 | **樣本內過擬合** | `optimizer.run_auto_backtest` 把 ~40 組參數在**整段歷史**跑、挑 EV 最高當冠軍；`screener`→`automation.plan_deployments` 直接部署這個冠軍 | 部署「對過去最會講故事」的參數，未來大機率失效。文件一直警告過擬合，optimizer 卻正在犯 | [步驟 4](step-04-out-of-sample-validation.md) |
| P2 | **回測零成本零滑價** | `backtest_engine._run_on_df` 用 `close` 價即時成交，無手續費/滑價/價差 | 高頻策略（RSI/KD）真實 EV 遠低於回測；`AUTO_DEPLOY_EV_THRESHOLD` 建立在虛高數字上 | [步驟 2](step-02-backtest-cost-model.md) |
| P3 | **執行語意偷看未來** | `_run_on_df` 在 `close[i]` 同時「決策＋成交」 | 實盤是收盤算訊號、下一個價才成交；回測比實盤樂觀 | [步驟 3](step-03-next-bar-execution.md) |
| P4 | **實盤與回測資料路徑分岔** | 實盤 `bot_manager._run_strategy` 寫死 `alpaca_client.get_bars(days=60)`；回測走 `market_data.get_bars(days=365, source=可選)` | **你回測的東西 ≠ 你實際交易的東西**（資料源不同、回看 60 vs 365） | [步驟 1](step-01-unify-data-path.md) |
| P5 | **死掉的 AI 情緒層** | `screen_watchlist` 算了 `sentiment` 卻只用 EV 排序；`plan_deployments` 完全忽略它 | 第二層 LLM 燒算力卻不影響任何決策（典型 vibe slop） | [步驟 7](step-07-sentiment-into-decision.md) |
| P6 | **無組合層資金/風控** | 每個 Bot 各自 all-in；`run_auto_deploy` 建多個 Bot 不檢查總購買力；無全域回撤熔斷 | 模式 B 可能配資超過帳戶現金、並發互踩、無剎車 | [步驟 5](step-05-capital-guard.md)、[步驟 9](step-09-circuit-breaker.md) |
| P7 | **排程持有過期 ORM 物件** | `start_bot` 把 `args=[bot]` 鎖死建立當下；`run_bot_once` 讀 `bot.strategy/params/風控` 都是舊值 | 改了風控/參數，執行中的排程仍用舊值直到重啟 | [步驟 6](step-06-scheduler-refetch.md) |
| P8 | **無決策審計軌跡** | 全靠 `print()` + `notify()`；只有 `last_checked_at` | 自動跑真錢卻無「為何在某時點買/不買」的持久紀錄 | [步驟 8](step-08-decision-audit-log.md) |

---

## 貳、北極星（再制訂的目標）

> **一台可被信任、最終能託付真錢的本機自動交易機器人——「回測看到的期望值」必須是「實盤拿得到的期望值」的誠實估計，且每一筆自動決策都可追溯、可熔斷。**

三條不可違反的底線（沿用專案鐵則、本 Phase 強化）：
1. **全程 Paper**，實盤雙閘（`IS_PAPER` + `ALLOW_LIVE_TRADING`）完全不動，由 `alpaca_client.submit_market_order` 把關。
2. **EV 看「樣本外（out-of-sample）」不看樣本內**；任何自動部署一律以 OOS + 含成本的 EV 為門檻。
3. **回測 = 實盤**：同一資料源、同一回看長度、同一執行語意，否則視為 bug。

---

## 參、目標架構（整理後的全貌）

收斂後的資料 / 決策流，**單一資料路徑、回測與實盤共用核心**：

```
                 ┌────────────────── 共用核心（single source of truth）──────────────────┐
                 │                                                                        │
 watchlist ─► market_data.get_bars(source=DATA_SOURCE) ─► strategies/<x>.generate_signal  │
                 │                    │                            │                       │
                 │             required_lookback()          Signal(BUY/SELL/HOLD)          │
                 │           （由策略參數推算，回測與實盤共用）                            │
                 └────────────────────┼────────────────────────────┼─────────────────────┘
                                      │                            │
        ┌──────────────────────────────┘                            └─────────────────────┐
        ▼ 回測路徑（研究 / 海選）                                        ▼ 實盤路徑（執行）
 backtest_engine._run_on_df                                     bot_manager.run_bot_once
   + 成本模型（步驟 2）                                            + 風控 check_exit
   + 隔日成交語意（步驟 3）                                         + submit_market_order（雙閘）
        │                                                          + 決策審計（步驟 8）
        ▼                                                          + 每輪重查 Bot（步驟 6）
 optimizer.run_auto_backtest                                            │
   + train/test 切分 → OOS EV 排名（步驟 4）                            │
        │                                                              │
        ▼                                                              │
 screener.screen_watchlist（漏斗：量能→情緒→OOS EV，步驟 7）             │
        │                                                              │
        ▼                                                              │
 automation.plan_deployments（OOS EV + 勝率 + 情緒 + 資金上限）─────────┘
   + 購買力守門（步驟 5）+ 組合回撤熔斷（步驟 9）
```

模組職責（邊界更清楚）：
- `strategies/`：純訊號，不碰錢、不碰網路。
- `market_data.py`：**唯一**抓 K 線入口（實盤也走這裡）。
- `backtest_engine.py`：純回測邏輯 + 成本模型。
- `optimizer.py`：參數搜尋 + 樣本外驗證。
- `screener.py` / `automation.py`：海選與自動部署的**編排**，決策規則抽成純函式好測。
- `bot_manager.py`：執行 + 排程，**每輪重查 Bot**。

---

## 肆、施工路線（10 步，依「風險削減 × 低耦合」排序）

| 步驟 | 文件 | 主題 | 修哪個問題 |
|------|------|------|-----------|
| 1 | [step-01-unify-data-path.md](step-01-unify-data-path.md) | 統一資料路徑：實盤 = 回測 | P4（+ P7 前置） |
| 2 | [step-02-backtest-cost-model.md](step-02-backtest-cost-model.md) | 回測成本模型（手續費 / 滑價） | P2 |
| 3 | [step-03-next-bar-execution.md](step-03-next-bar-execution.md) | 隔日成交語意 | P3 |
| 4 | [step-04-out-of-sample-validation.md](step-04-out-of-sample-validation.md) | 樣本外驗證：以 OOS EV 排名 ★核心 | P1 |
| 5 | [step-05-capital-guard.md](step-05-capital-guard.md) | 組合層資金 / 購買力守門 | P6（前半） |
| 6 | [step-06-scheduler-refetch.md](step-06-scheduler-refetch.md) | 排程每輪重查 Bot | P7 |
| 7 | [step-07-sentiment-into-decision.md](step-07-sentiment-into-decision.md) | AI 情緒真正進決策 | P5 |
| 8 | [step-08-decision-audit-log.md](step-08-decision-audit-log.md) | 決策審計軌跡 | P8 |
| 9 | [step-09-circuit-breaker.md](step-09-circuit-breaker.md) | 組合回撤熔斷 | P6（後半） |
| 10 | [step-10-architecture-cleanup.md](step-10-architecture-cleanup.md) | 架構與文件整理（無行為變更） | 技術債 |

---

## 伍、整個 Phase 完成後的「可信度驗收」

1. **回測誠實化**：同一策略 / 標的，比較 Phase 6 前後 EV，確認**下降且方向合理**（成本 + 隔日 + OOS 三重保守），於 CHANGELOG 記代表性數字。
2. **OOS 防過擬合**：跑 `POST /auto-backtest`，確認冠軍是 OOS EV 最高者；挑一個「in-sample 漂亮但 OOS 差」的組合確認它落榜。
3. **資料路徑一致**：同一 Bot 用 `/bots/{id}/run`（實盤路徑）與 `/backtest`（回測路徑）對同標的，確認同源同回看。
4. **參數即時生效**：啟動 Bot → `PUT /bots/{id}/risk` 改止損 → 下一輪 `decisions` 顯示用新門檻。
5. **資金守門**：假帳戶現金設低，`/automation/run?dry_run=true` 確認超額部署被砍。
6. **情緒入決策**：monkeypatch bearish 情緒，確認該標的被「情緒否決」、不進 deploy。
7. **熔斷**：模擬權益跌破門檻，確認新買進 / 自動部署被擋、既有風控出場照跑。
8. **實盤仍封鎖**：`GET /status` `live_armed:false`；全程 Paper。

---

## 陸、明確不在本 Phase 範圍（避免 scope creep / 再生 slop）

- 新增策略、實盤切換 UI、更多圖表 / 通知管道 → 延後（屬「擴功能」，與本 Phase「鞏固」目標相斥）。
- 把 LLM 從 best-effort 升級成決策**必要**條件 → 不做；情緒永遠是「輔」，EV（OOS + 含成本）永遠是「主」。
- 真錢實盤 → 不在本 Phase 動雙閘；本 Phase 是「**讓系統有資格將來被信任跑真錢**」的前置工程。
- 換 PostgreSQL、部署 / 容器化 → 與可信度無關，延後。
