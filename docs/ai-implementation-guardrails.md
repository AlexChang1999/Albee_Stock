# AI 實作護欄合約（Anti-Drift & Anti-Slop Contract）

> **這份文件的唯一目的**：當任何 AI（或人）拿 `docs/history/phase-*/` 的藍圖去**自己 coding** 時，
> 確保它 **(1) 不偏離原目標、(2) 不產生 vibe slop**。
>
> **使用方式（強制）**：每個 coding session —
> **開工前**讀「原目標錨點」+ 對應的 step 合約；**coding 中**遵守「反 slop 規則」；**收工前**逐項對「完成定義 DoD」。
> 三道關卡缺一不可。本檔是所有 phase 步驟檔的共同前言，步驟檔只補「步驟專屬」內容。

---

## 〇、什麼是 vibe slop / 目標漂移（先認得敵人）

| 敵人 | 長相 | 為什麼致命 |
|------|------|-----------|
| **目標漂移** | 做著做著開始解決「沒人要求的問題」、加「順手覺得該有」的功能 | 離原目標越來越遠，最後交出一個不是使用者要的東西 |
| **臆測性通用化** | 為「未來可能用到」加抽象層 / config 旗標 / 參數 / 介面 | 增加複雜度、沒人用、變成維護負擔 |
| **重造輪子** | 沒查既有就自己寫一個 `get_bars` / 算 EV / 格式化數字 | 與既有實作分岔，雙份邏輯遲早不一致 |
| **範圍蔓延** | 一個 commit 夾雜重構 + 修 bug + 新功能 + 改格式 | 無法 review、無法回溯、藏 bug |
| **假綠** | 測試沒跑 / 跑不過就說「完成」；或刪測試讓它過 | 在會說謊的基礎上繼續蓋樓 |
| **註解 / 死碼噪音** | 註解掉的舊碼、TODO 堆、用不到的 import / 參數、複製貼上的樣板 | 讓讀者分不清什麼還活著 |
| **領域不誠實** | 樣本內挑冠軍、回測零成本、偷看未來、只看勝率 | 這個專案最大的虧錢來源（見第伍節） |

---

## 壹、原目標錨點（North Star）— 每次開工先重讀

> **Albee Stock 的終局：一台可被信任、最終能託付真錢的本機自動交易機器人。**
> 核心信條：**「回測看到的 EV」必須是「實盤拿得到的 EV」的誠實估計，且每一筆自動決策都可追溯、可熔斷。**

不可違反的鐵則（任何 phase、任何步驟都適用）：
1. **全程 Paper**；實盤雙閘（`config.IS_PAPER` + `ALLOW_LIVE_TRADING`）**絕不更動**，由 `alpaca_client.submit_market_order` 把關。
2. **EV 看樣本外（OOS）+ 含成本**，不看樣本內、不只看勝率。
3. **回測 = 實盤**：同資料源、同回看長度、同執行語意。
4. **零成本 / 免費 / 本機優先**：Ollama、yfinance、Alpaca Paper；外送雲端要過 `LLM_ALLOW_CLOUD` 閘。
5. **鬆耦合**：策略 / 服務能獨立增刪改；純函式優先、好測試。
6. **中文註解**幫助學習；每次有意義變更更新 `CHANGELOG.md`。

> **自檢句（每個改動都要能回答）**：「這一行 / 這個檔，是在服務上面哪一條鐵則？」
> **答不出來 → 不要寫。** 這是防漂移的第一道、也是最重要一道閘。

---

## 貳、三層防漂移檢查（強制流程）

### 開工前（Before）
1. 讀 `CLAUDE.md`（專案上下文、慣例、踩過的坑）。
2. 讀**這份合約**的第壹、伍節。
3. 讀**你要做的那一個 step 檔**（只做那一步，不順手做下一步）。
4. 確認這步「屬於哪個 phase、依賴哪些前置」——**前置沒完成就不要開始**（例：Phase 8 依賴 Phase 6 OOS + Phase 7 step-07）。
5. 用 Grep/Glob **先找既有可重用的東西**（見第參節），找到就用、不要重造。

### Coding 中（During）
- **只動該 step 指名的檔**。想動別的 → 停下來，記成待辦，不要順手改。
- 寫任何新函式前，先問：「既有有沒有？」「這步的驗收需要它嗎？」兩個都過才寫。
- **不加**沒被要求的 config 旗標 / 抽象層 / 參數 / 介面 / 「未來擴充點」。
- 配合周圍程式風格（命名、註解密度、檔案長度），不自創一套。

### 收工前（After）
- 逐項對該 step 的**完成定義 DoD**（第陸節通用 + 步驟專屬）。
- 跑**完整測試**（後端 `pytest tests/ -q`、動到前端則 `npm run test`），**全綠才算完成**。
- 自我 review diff：有沒有死碼 / 註解掉的碼 / 用不到的 import / 偷加的範圍？有 → 刪。
- 更新 `CHANGELOG.md` 未發布區塊（一句話講清楚改了什麼、為什麼）。
- **一步一聚焦 commit**；不夾帶無關變更。

---

## 參、重用優先：既有可重用清單（先查這裡，別重造）

> 動手寫「資料 / 回測 / 指標 / 通知 / LLM / 數字格式」相關的東西前，**先看這張表有沒有現成的**。

| 你想做 | 用既有的 | 路徑 |
|--------|----------|------|
| 抓 K 線（可選資料源） | `market_data.get_bars(symbol, days, source)` | `backend/services/market_data.py` |
| 跑回測（純邏輯） | `backtest_engine._run_on_df(strategy, df, cash)` | `backend/services/backtest_engine.py` |
| 掃所有策略×參數挑 EV | `optimizer.run_auto_backtest(...)` | `backend/services/optimizer.py` |
| 風控出場判斷 | `risk_manager.check_exit(...)` | `backend/services/risk_manager.py` |
| 下單（唯一出口，含雙閘） | `alpaca_client.submit_market_order(...)` | `backend/services/alpaca_client.py` |
| 取得策略實例 / 策略清單 | `get_strategy(key, params)` / `STRATEGY_REGISTRY` | `backend/strategies/__init__.py` |
| LLM 呼叫（含外送閘） | `llm.get_client/complete/cloud_blocked` | `backend/services/llm.py` |
| 通知（多管道） | `notify(msg)` | `backend/services/notifier.py` |
| 探討檔案記憶（含防穿越） | `explorations.read_index/list_index_entries/read_exploration/write_exploration` | `backend/services/explorations.py` |
| 新策略一條龍落地 | `strategy-builder` skill | `.claude/skills/strategy-builder/` |
| 前端後端呼叫 | `api.*` | `frontend/src/api.js` |
| 數字縮寫 / 報價格式 | `utils/number.js` / `utils/quote.js` | `frontend/src/utils/` |
| schema 變更 | **Alembic**（`render_as_batch=True`），**不要手動 ALTER** | `alembic/` |

> 找不到才新增；新增時放對層（策略放 `strategies/`、業務邏輯放 `services/`、路由放 `routers/`）。

---

## 肆、範圍柵欄（一步一分支一 PR）

- **一個 step = 一個分支 = 一個聚焦 commit/PR**。不要把多步塞一起。
- 只動該 step「關鍵檔案」表列出的檔。要動表外的檔 = 範圍蔓延，先停、先問。
- **不做**「順手的大重構」——重構要單獨成步、單獨 commit、且行為不變 + 測試先綠。
- 新增依賴（pip / npm）要在 step 明確要求才裝，並評估 Windows 安裝風險（見 CLAUDE.md 踩坑）。

---

## 伍、領域誠實守則（這個專案的虧錢防線，最容易被 slop 掉）

寫任何「回測 / 海選 / 部署 / 部位 / 進化」相關碼時，逐條自檢：

- [ ] **無 look-ahead**：策略只能看 `df.iloc[:i+1]`；成交用次根價（Phase 6 step-03），不用當根收盤偷吃。
- [ ] **含成本**：回測走含手續費 / 滑價的路徑（Phase 6 step-02），不報零成本的虛高 EV。
- [ ] **樣本外**：挑冠軍 / 設門檻一律看 OOS（Phase 6 step-04 / Phase 7 step-07），不在整段歷史挑最佳。
- [ ] **EV 為主**：不用「勝率 90%」當賣點；高勝率負 EV 要明確標危險。
- [ ] **多重測試校正**：大量生成 / 搜尋策略時，套 Phase 7 step-07 的 walk-forward / purged CV / deflated 判定，**加不了分的層就砍掉**（砍掉也是成果，記進 CHANGELOG）。
- [ ] **情緒只當輔助**：LLM 情緒 / 事件當過濾閘，**不當主進場訊號**，連不上要 best-effort 不阻斷。
- [ ] **雙閘不碰**：任何下單路徑都經 `submit_market_order`；不繞過、不改安全閥。

---

## 陸、完成定義（Definition of Done，通用）

一個 step 只有**全部**滿足才算完成（步驟檔可再加專屬項）：

1. 行為符合該 step 的「驗收」一節。
2. **新增 / 改動都有測試**（純函式單元測試優先；碰網路 / LLM / DB 用 monkeypatch）。
3. `pytest tests/ -q` 全綠；動到前端則 `npm run test` 全綠；動到 schema 則 Alembic 遷移可 `upgrade head`。
4. diff 內**無死碼、無註解掉的碼、無用不到的 import/參數、無偷加的範圍**。
5. 配合既有風格與中文註解密度。
6. `CHANGELOG.md` 未發布區塊已更新。
7. 不確定的地方**已問、已釐清**，不是用猜的填上。

---

## 柒、不確定就停（Stop, don't invent）

遇到下列情況，**停下來問使用者**，不要自行發明：
- step 的需求有歧義、或與現況衝突。
- 要動 step 範圍外的檔、要新增依賴、要改既有公開行為 / API 契約。
- 發現該 step 的前置（依賴的 phase）其實還沒做完。
- 要刪除 / 覆寫不是你建立、且與描述不符的東西（先回報差異）。

> **寧可多問一句，不要多生一段沒人要的 slop。** 這正是「避免跟原目標差距太遠」的最後保險。

---

## 捌、每個 step 檔怎麼讀（它就是合約）

`docs/history/phase-*/step-*.md` 的固定結構就是這份合約的「逐步版」：
- **目標 / 概念**：這步要服務原目標的哪一條（對照第壹節）。
- **問題 / 改動**：只做這些，不多不少。
- **重用既有**：先用這些，別重造（對照第參節）。
- **測試 / 驗收**：DoD 的具體化（對照第陸節）。
- **風險 / 不要做**：常見 slop 陷阱，明令禁止。

> 拿到一個 step：照第貳節三層流程走，做完對 DoD，過了才動下一步。**一次一步，永遠對齊原目標。**
