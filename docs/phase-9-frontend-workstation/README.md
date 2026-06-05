# Phase 9 — 專業前端工作站（左側導覽 + 多頁面）

> 把目前「全擠在儀表板一個分頁 + 右側工作台」的 UI，重構成左側 sidebar 分區的專業量化終端機。
> **開工前必讀 [`../ai-implementation-guardrails.md`](../ai-implementation-guardrails.md)。**
> **排在 Phase 6/7/8 之後做**（使用者選照階段順序）；內部仍先做最簡單的「現有資料」頁面。
>
> 撰寫日期：2026-06-05。

---

## 〇、為什麼要做 + 現況痛點

| 痛點 | 現況（讀碼實證） |
|------|------------------|
| 儀表板過載 | `App.jsx` tab 0 同時塞 AccountCard + AI 燈號 + BotList + AutoBacktestPanel + BacktestPanel + TradesTable |
| 資料埋太深 | 回測歷史 / 策略方案只在右側 `StrategyWorkbench` 折疊面板裡 |
| 探討無前端 | `explorations` 只被 `chat.py` 內部用，**沒有 GET 端點、沒有任何頁面** |
| 導覽太薄 | 只有上方 4 個 Tabs（儀表板 / AI 探勘 / K 線圖 / 基本面） |

使用者決定：改成**左側 sidebar 導覽 + 路由多頁面**（專業終端機標配）。

---

## 壹、推薦資訊架構（IA — 左側 sidebar 導覽）

```
┌── 監控中心   Dashboard      帳戶總覽 + AI 燈號 + 服役中 Bot（瘦身，移走回測面板）
│   交易紀錄   /trades        ← GET /trades（已存在）｜加 bot/symbol/side/日期 篩選
│   回測歷史   /backtest-runs ← GET /backtest-runs（已存在）｜全頁 EV 榜 + equity 曲線 + 收藏
│   策略方案   /presets       ← GET /presets（已存在）｜CRUD + 一鍵回測
│   探討檢討   /explorations  ← 需新增 GET /explorations（小端點，重用服務）
│   決策審計   /decisions     ← Phase 6 step-08 的 GET /bots/{id}/decisions
│   狀態洞察   /regime        ← Phase 7（選配，依完成度）
│   進化實驗室 /evolution     ← Phase 8 候選 / 驗證 / 組合 / 晉升
│   策略知識庫 /library       ← Phase 8 知識庫（理論 / 場景 / 使用時機）
└── 思考助手   抽屜或 /assistant ← 沿用現有 chat（從右側工作台改放）
```

> 灰底項依賴前面 phase（決策審計→P6、狀態洞察→P7、進化/知識庫→P8）；前置沒做完的頁面**不要先做**（護欄第柒節）。

---

## 貳、施工路線（8 步；先現有資料、後依賴前面 phase）

| 步驟 | 文件 | 主題 | 依賴 |
|------|------|------|------|
| 1 | [step-01-navigation-shell.md](step-01-navigation-shell.md) | 導覽重構（Tabs→sidebar+路由）+ Dashboard 瘦身 | — |
| 2 | [step-02-trades-page.md](step-02-trades-page.md) | 交易紀錄頁（+ 篩選） | 現有資料 |
| 3 | [step-03-backtest-runs-page.md](step-03-backtest-runs-page.md) | 回測歷史 / EV 榜頁 | 現有資料 |
| 4 | [step-04-presets-page.md](step-04-presets-page.md) | 策略方案頁 | 現有資料 |
| 5 | [step-05-explorations-page.md](step-05-explorations-page.md) | 探討/檢討頁 + 新增 GET 端點 | 小端點 |
| 6 | [step-06-decisions-page.md](step-06-decisions-page.md) | 決策審計頁 | Phase 6 step-08 |
| 7 | [step-07-evolution-library-pages.md](step-07-evolution-library-pages.md) | 進化實驗室 + 策略知識庫頁 | Phase 8 |
| 8 | [step-08-assistant-relocate.md](step-08-assistant-relocate.md) | 思考助手改抽屜 / 獨立頁 + 拆 StrategyWorkbench | — |

> step-01 一次定案技術選型（`react-router` vs 輕量自管路由），後續頁面照同一套骨架長。

---

## 參、明確界線（防 slop / 防漂移）

- **不在 Phase 6/7/8 對應後端完成前，做依賴它們的頁面**（決策審計 / 狀態洞察 / 進化 / 知識庫）。
- **不重造**資料呼叫——一律經 `frontend/src/api.js`，新端點加在那裡。
- **沿用既有元件 / 工具**（`Stat`、`utils/number.js`、`theme.js` 色票、`ConfirmDialog`），不另立一套樣式。
- 重構導覽屬「行為不變的搬移」——**先搬、測試綠，再加新功能**，不混在一起。
- 每步一頁、一聚焦 commit；不一次端出全部頁面。
