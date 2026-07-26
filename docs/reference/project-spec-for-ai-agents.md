# Albee Stock 專案規格書（給 AI Agent 讀）

> **這份文件的目的**：讓任何 AI agent（Claude Code、subagent、或其他 LLM 工具）在
> **只讀這一份**之後，就知道：(1) 本專案的架構怎麼設計、為什麼這樣設計；
> (2) 哪些是絕不能踩的雷區；(3) 如果要把工作拆給多個 subagent（開發／審查／QA／
> UI-UX／DevOps／前端），在 Claude Code 裡具體怎麼實作。
>
> **與其他文件的分工**：本檔是「一頁式總覽 + 導航」。細節不重複，指到出處：
> - 防偏離合約 → [`../ai-implementation-guardrails.md`](../ai-implementation-guardrails.md)（開工前必讀）
> - 完整踩坑史料 → [`dev-pitfalls-log.md`](dev-pitfalls-log.md)
> - 策略開發合約 → [`../../backend/strategies/CLAUDE.md`](../../backend/strategies/CLAUDE.md)
> - 專案上下文 / 檔案放置規範 → 根目錄 [`CLAUDE.md`](../../CLAUDE.md)

---

## 一、專案是什麼（North Star）

**Albee Stock = 美股多 Bot 自動交易策略系統。**
終局目標：一台**可被信任、最終能託付真錢**的本機自動交易機器人。

核心信條（所有設計決策的根）：

> **「回測看到的 EV（期望值）」必須是「實盤拿得到的 EV」的誠實估計，
> 且每一筆自動決策都可追溯、可熔斷。**

由此推導出六條鐵則，任何改動都必須能回答「這行程式在服務哪一條」：

1. **全程 Paper Trading**；實盤有雙閘安全閥 + leader lock 第三閘（見第四節）。
2. **EV 看樣本外（OOS）+ 含成本**；不看樣本內、不只看勝率。
3. **回測 = 實盤**：同資料源、同回看長度、同執行語意（隔日開盤成交）。
4. **零成本 / 本機優先**：Ollama 本機 LLM、yfinance、Alpaca Paper 免費版。
5. **鬆耦合**：策略 / 服務可獨立增刪改；純函式優先。
6. **中文註解**幫助學習；有意義變更必更新 `CHANGELOG.md`。

---

## 二、系統架構設計

### 2.1 技術棧

| 層 | 技術 | 備註 |
|----|------|------|
| 後端 | Python 3.13 + FastAPI | 入口 `backend/main.py`，從專案根 `uvicorn backend.main:app` |
| 前端 | React (Vite) + MUI 深藍主題 | `frontend/`，左側 sidebar + react-router 多頁 |
| 資料庫 | Neon 雲端 PostgreSQL（`.env` 沒填退回 SQLite） | schema 變更**只走 Alembic** |
| 交易 API | alpaca-py（官方新版） | 舊 alpaca-trade-api 已停維護，勿用 |
| 回測 | 自寫引擎 `backend/services/backtest_engine.py` | 含成本 + 隔日成交 + EV |
| LLM | OpenAI 相容 SDK → 本機 Ollama | 外送雲端要過 `LLM_ALLOW_CLOUD` 閘 |
| 排程 | APScheduler | 多機共用 DB 靠 `scheduler_lock.py` 選主 |
| 部署 | 本機 Windows 11 開發；Oracle Micro VM 跑 24/7 | VM 追 `main` 分支，非 develop |

### 2.2 後端分層（誰放哪、誰呼叫誰）

```
routers/    API 路由（薄，只做 HTTP 進出 + 驗參）
   ↓ 呼叫
services/   業務邏輯（回測引擎、資料源、風控、通知、LLM…）
   ↓ 使用
strategies/ 交易策略（純訊號產生器，一策略一檔）
models/     SQLAlchemy 資料模型（改欄位走 Alembic）
bots/       bot_manager（Bot 啟停/排程/每輪重查最新設定）
```

分層規則：

- **策略只產訊號**（`generate_signal(df) -> (BUY/SELL/HOLD, 中文原因)`），
  不下單、不碰 API、不管部位。成交與資金由回測引擎 / 實盤 Bot 負責。
- **下單唯一出口** = `services/alpaca_client.submit_market_order`（內含雙閘）。
  任何新功能都不得繞過它自己呼叫 Alpaca 下單。
- **資料唯一出口** = `services/market_data.get_bars(symbol, days, source)`。
  回測與實盤都走這條，**不要**另寫一條抓資料的路（會破壞「回測=實盤」）。
- 回看長度由 `strategies/lookback.required_lookback_days(...)` 統一推算，
  不要在實盤端寫死天數。
- 新增檔案放哪，照根目錄 `CLAUDE.md`「檔案放置規範」表；測試進扁平 `tests/`。

### 2.3 資料流（一筆自動交易怎麼發生）

```
排程喚醒 Bot → market_data 抓 K 線（lookback 統一算回看）
  → 策略 generate_signal 產訊號
  → risk_manager 檢查止盈/止損/追蹤止損
  → capital.plan_capital 組合層資金守門
  → circuit_breaker 回撤熔斷（只擋進不擋出）
  → alpaca_client.submit_market_order（雙閘 + leader lock）
  → DecisionLog 落審計軌跡（含「沒下單」的決策也要記）
  → notifier 推播（LINE / Discord）
```

回測走同一套語意：訊號於第 i 根收盤算出 → 第 i+1 根**開盤價**成交、
含手續費/滑價、最後一根不成交。挑冠軍一律看 `oos_expected_value`。

### 2.4 前端結構

- `App.jsx` 是路由編排層（state + handler 用 `<Outlet context>` 下發）。
- 頁面在 `pages/`、區塊元件在 `components/`（測試同層 `*.test.jsx`）、
  純函式在 `utils/`、API 呼叫集中 `api.js`（讀 `VITE_API_URL`）。
- 顏色**一律吃 `theme.js`**（深藍主題 + NEON 色票），不寫死 hex。

---

## 三、雷區地圖（AI 最常炸的地方，按致命度排序）

> 完整史料（症狀/根因/commit）見 [`dev-pitfalls-log.md`](dev-pitfalls-log.md)。
> 這裡列「動手前必記」的濃縮版。

### 🔴 致命級（炸了 = 回測造假 / 燒真錢）

1. **偷看未來（look-ahead）**：策略只能用 `df.iloc[:i+1]`；成交用次根開盤價。
   「右側確認 N 根」要真的延遲 N 根才認定。違反 = 回測 EV 全是假的。
2. **樣本內挑冠軍**：optimizer / automation / screener 的排名與門檻
   **只看 OOS**。在整段歷史挑最佳 = 過擬合，實盤必虧。
3. **零成本回測**：必走含手續費/滑價路徑（`_simulate_from_signals`）。
4. **繞過雙閘**：實盤下單需「`ALPACA_BASE_URL` 實盤網址」+「`ALLOW_LIVE_TRADING=true`」
   同時成立，且非 leader 一律拒單。**任何 AI 都不得修改這三道閘**。
5. **資料路徑分岔**：實盤端寫死 `alpaca_client.get_bars(days=60)` 之類
   = 回測與實盤看到不同世界。一律走 `market_data.get_bars` + `lookback`。

### 🟠 高風險級（炸了 = 系統壞 / 資料毀）

6. **手動 ALTER TABLE**：schema 變更只走 Alembic
   （`alembic revision --autogenerate` → 人工檢查 → `upgrade head`）。
   SQLite 需 `render_as_batch=True`（已設）；PG 與 SQLite 的 boolean/connect_args 行為不同。
7. **測試打到真 DB**：TestClient 必須 override DB dependency，
   否則跨測試污染（踩過，commit `6b461b5`）。
8. **模組頂層建外部 client**：alpaca-py 建 client 即驗金鑰，CI 無金鑰光 import 就崩。
   外部 client 一律延遲初始化（property）。
9. **雙機重複下單**：多機共用 Neon DB，排程靠 `scheduler_lock.py` 選主。
   新增排程任務必須尊重 leader lock，不可自開第二條排程。

### 🟡 常見級（炸了 = 功能壞 / 難查）

10. **Windows cp950**：印中文/emoji 會 `UnicodeEncodeError`。獨立腳本開頭加
    `sys.stdout.reconfigure(encoding="utf-8")`；`.bat` 存 UTF-8 with BOM。
11. **前端寫死 hex**：深藍底上深色字直接隱形。用 `theme` / `NEON` / `text.primary`。
12. **策略參數鍵名打錯**：`self.params.get("鍵", 預設)` 靜默回退預設不報錯；
    預設值必須 == `STRATEGY_PARAM_SPECS` 的 default。
13. **新策略漏落地點**：共 6 處（本體/`__init__.py` 四表/前端 constants/文件/測試/
    lookback+PARAM_GRIDS），漏 lookback 且需求 >60 根 → 實盤永遠 HOLD（靜默失準）。
14. **ta-lib**：Windows 裝不起來，指標用 pandas 自算。
15. **vibe slop**：目標漂移、臆測性通用化、順手重構、假綠測試——
    開工前讀 [`ai-implementation-guardrails.md`](../ai-implementation-guardrails.md)，
    一次一步、只動 step 指名的檔、收工對 DoD。

---

## 四、安全模型（三道閘，背下來）

| 閘 | 位置 | 條件 |
|----|------|------|
| 第一閘 | `.env` `ALPACA_BASE_URL` | 預設 paper 網址；實盤要換網址 |
| 第二閘 | `.env` `ALLOW_LIVE_TRADING` | 預設 false；true 才放行真錢單 |
| 第三閘 | `services/scheduler_lock.py` | 多機共用 DB 時，非 leader 一律拒單 |

三閘全部收斂在 `alpaca_client.submit_market_order` 把關。
另有 `LLM_ALLOW_CLOUD` 外送閘：策略資料預設不出本機。

---

## 五、開發工作流（每個 agent 都要遵守）

1. **開工前**：讀根目錄 `CLAUDE.md` + `docs/ai-implementation-guardrails.md`
   第壹、伍節 + 你要做的那個 step 檔。先 Grep 既有可重用清單，不重造輪子。
2. **Coding 中**：只動 step 指名的檔；不加沒被要求的抽象層/旗標；
   配合既有風格與中文註解密度。
3. **收工前**：`pytest tests/ -q` 全綠（動前端加 `npm run test`；
   動 schema 驗 `alembic upgrade head`）；diff 無死碼；更新 `CHANGELOG.md`；
   一步一聚焦 commit。
4. **不確定就停**：需求歧義、要動範圍外的檔、要加依賴、前置沒完成 → 先問，不猜。

驗證指令速查：

```powershell
venv\Scripts\python.exe -m pytest tests/ -q          # 後端測試
cd frontend; npm run test                             # 前端測試
venv\Scripts\uvicorn.exe backend.main:app --reload    # 起後端（從專案根）
venv\Scripts\alembic.exe upgrade head                 # 套遷移
```

> 注意：phase-16 基底本來就有 13 個既有測試失敗（歷史包袱），
> 跑測試看「你改的範圍有沒有新增失敗」，勿誤判成自己弄壞。

---

## 六、Subagent 分工實作（Claude Code）

### 6.1 Claude Code 的 subagent 機制

Claude Code 的 subagent = **`.claude/agents/` 夾裡的 Markdown 檔**，
一檔一個角色。主對話（orchestrator）可以：

- **自動委派**：Claude 讀每個 agent 檔的 `description`，任務匹配就自動派工。
- **手動指名**：使用者說「用 code-reviewer 審這個 diff」即強制指派。
- 每個 subagent 有**獨立 context window**（不吃主對話上下文，回報結論回來），
  適合把「噪音大的搜索/審查/測試」隔離出去，主對話只留結論。

檔案格式（YAML frontmatter + system prompt 本文）：

```markdown
---
name: code-reviewer            # 呼叫用的名字（kebab-case）
description: 審查 diff/PR。完成任何程式修改後主動使用。   # Claude 靠這行決定何時自動委派
tools: Read, Grep, Glob, Bash  # 白名單；省略 = 繼承全部工具
model: sonnet                  # 選填：haiku/sonnet/opus，省略 = 繼承主對話
---

你是本專案的程式碼審查員。審查前先讀 docs/ai-implementation-guardrails.md 第伍節…
（以下就是這個 agent 的 system prompt，寫角色守則）
```

放置位置：專案級 `.claude/agents/`（進 git、全隊共用）
或使用者級 `~/.claude/agents/`（跨專案個人用）。同名時專案級優先。

### 6.2 本專案建議的六個角色

| Agent 檔 | 職責 | tools 建議 | 關鍵守則（寫進該檔 system prompt） |
|----------|------|-----------|-----------------------------------|
| `dev-coder.md` | 照 step 契約實作後端功能 | 全部 | 開工前讀 guardrails + step 檔；只動指名檔案；重用第參節清單；策略類任務轉讀 `strategies/CLAUDE.md` |
| `code-reviewer.md` | 審 diff/PR | Read, Grep, Glob, Bash（唯讀為主） | 逐條對「領域誠實守則」：look-ahead？OOS？含成本？繞雙閘？死碼？一行一發現，嚴禁順手改碼 |
| `qa-tester.md` | 寫測試 + 跑驗證 | 全部 | 測試進扁平 `tests/`；TestClient 必 override DB；合成資料手構 K 棒不用隨機；BUY/SELL/資料不足三情境；記住 13 個歷史失敗基線 |
| `ui-ux.md` | 前端頁面/元件/UX 稽核 | 全部 | 顏色只吃 theme.js/NEON；元件測試同層 `*.test.jsx`；改版前讀 `docs/ux/ux-workflow.md`；API 走 `api.js` |
| `devops.md` | 部署/CI/VM/DB 遷移 | 全部 | VM 追 main 非 develop；schema 只走 Alembic；排程尊重 leader lock；`.bat` UTF-8 BOM + `%~dp0` 錨定；`.env` 絕不進 git |
| `frontend-dev.md` | React 功能開發 | 全部 | 同 ui-ux 技術守則 + 頁面地圖讀 `docs/reference/frontend-pages-map.md`；純函式抽 `utils/` 好測試 |

> 為什麼 code-reviewer 給唯讀工具：審查員不該邊審邊改（範圍蔓延 + 審改利益衝突）。
> 發現問題回報主對話，由 dev-coder 修。

### 6.3 建議協作流程（pipeline）

```
使用者需求
  → 主對話拆 step（或直接引用 docs/history/phase-*/step-*.md）
  → dev-coder / frontend-dev 實作（一步一分支）
  → qa-tester 補測試 + 跑全套驗證
  → code-reviewer 審 diff（對照雷區地圖 + 領域誠實守則）
  → 有發現 → 回 dev-coder 修 → 再審
  → 全綠 + 審過 → commit + CHANGELOG + PR
```

實務建議：

- **不要為拆而拆**：單檔小修直接主對話做完即可。subagent 值得用在
  「噪音大」（大範圍 grep、跑整套測試）或「需要獨立視角」（審查、QA）的環節。
- **平行開發要隔離**：多個 agent 同時改碼時各開 git worktree
  （踩過 worktree 殘留整包 repo 誤入 commit 的坑，commit `efc600d`）。
- **每個 agent 檔開頭都指回本規格書**：
  「開工前讀 `docs/reference/project-spec-for-ai-agents.md` 第三、五節」，
  讓雷區知識單一來源、不用每個 agent 檔複製一份。

### 6.4 建立步驟（實際操作）

```
1. mkdir .claude/agents（專案根；本專案已有 .claude/）
2. 每個角色建一個 .md 檔（格式見 6.1）
3. 重啟 Claude Code session（agent 檔在 session 啟動時載入）
4. 測試：對 Claude 說「用 code-reviewer 審查最近一次 commit」
5. agent 檔進 git（全隊/全機共用同一套守則）
```

也可用互動式指令 `/agents` 在 Claude Code 內建立與管理（會引導填
name/description/tools/prompt）。

---

## 七、快速導航（找東西先查這）

| 想知道 | 讀這裡 |
|--------|--------|
| 專案全貌 / 檔案放哪 | 根目錄 `CLAUDE.md` |
| 開工防漂移合約 + 可重用清單 | `docs/ai-implementation-guardrails.md` |
| 踩坑完整史料（含 commit） | `docs/reference/dev-pitfalls-log.md` |
| 新增策略 | `backend/strategies/CLAUDE.md` + `docs/guides/how-to-add-strategy.md` |
| 系統工作流圖（Mermaid） | `docs/reference/workflow-diagrams.md` |
| 前端 20 頁地圖 | `docs/reference/frontend-pages-map.md` |
| 雲端/地端誰跑什麼 | `docs/guides/cloud-local-division.md` |
| 剩餘工作 backlog | `docs/remaining-work-backlog.md` |
