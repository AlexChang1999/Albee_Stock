# Phase 5 Roadmap — 策略工作台 + Claude 思考助手 + 期望值最優

> 本文件是 Phase 5 的設計藍圖（規劃中，尚未實作）。目標：把「設計策略 → Python 回測 →
> 用期望值挑最優 → Claude 事後檢討 → 越來越聰明」串成閉環。
> 撰寫日期：2026-06-02。

---

## 一、總目標與分工

朝「自動化交易機器人」前進，Phase 5 落地三塊互相扣連的基礎：

1. **策略產生 Skill** — 把外部交易員的策略描述/數據丟給 Claude，自動變成本專案能跑的策略 `.py` + md 說明。
2. **右側「策略工作台」面板**（可收合、可橫向拉寬）— 管理策略方案、用 **Python 一鍵跑回測**、看含**期望值（EV）**的結果、收藏好策略。
3. **Claude 思考助手**（工作台內聊天區）— 只負責思考：制定策略、微調建議、按鈕「總結這次錯在哪」做事後檢討；讀回測歷史**越來越聰明**。

### 明確分工
- **Python（後端）做事**：跑回測、算指標、存資料庫。
- **Claude 做思考**：設計策略、調參數建議、事後檢討。**Claude 不跑回測**（回測按鈕直接打 Python `/backtest`）。
- **最優依據用「期望值 EV」不是勝率**：`EV/筆 = 勝率×平均賺 − 敗率×平均賠`；勝率仍顯示但非主角。

### 鐵則（不可違反）
全程 Paper；實盤雙閘安全閥（`config.py` `IS_PAPER`+`ALLOW_LIVE_TRADING`，由 `alpaca_client.submit_market_order` 把關）**完全不動**；Claude 工具**不開放任何下單/shell/寫實盤**。

> ⚠️ 「一週勝率 90%+」極危險（常小賺多次、一次大賠）。一律看 **EV** + 先回測 + Paper 驗證，慎防過度擬合。

---

## 二、資料模型（新增 2 張表，走 Alembic）

### `StrategyPreset` 策略方案
獨立於 Bot 的可命名方案，能單獨回測/收藏/比較。
- `id`、`name`（可改名）、`strategy_key`（對應 STRATEGY_REGISTRY）、`params`(JSON)、`symbol`、`is_favorite`(bool)、`notes`(text)、`created_at`。
- 出來好的方案可一鍵轉成 Bot 實跑（沿用現有 Bot 建立流程）。

### `BacktestRun` 回測紀錄
每次 Python 回測存一筆，當作 Claude 的記憶來源。
- `id`、`preset_id`(nullable)、`strategy_key`、`params`(JSON)、`symbol`、`period`、`metrics`(JSON：含 EV 全套)、`is_good`(bool 收藏)、`claude_postmortem`(text nullable)、`created_at`。

---

## 三、Part 1 — 策略產生 Skill（`.claude/skills/strategy-builder/`）

專案第一個自製 skill，依 `docs/skill-guidelines.md`（漸進式揭露）。

```
.claude/skills/strategy-builder/
├── SKILL.md                  # frontmatter（觸發詞）+ 5 步流程
├── references/
│   ├── how-to-register.md    # 6 落地點（3 程式 + doc + test + 命名一致）
│   └── common-pitfalls.md    # 避坑：過擬合/EV>勝率/必回測+Paper/純pandas/UTF-8/資料不足HOLD
└── assets/
    ├── strategy_template.py  # BaseStrategy 骨架（中文註解，仿 rsi.py）
    ├── strategy_doc_template.md
    └── test_template.py
```

**5 步流程**：① 產 `backend/strategies/<name>.py`（純 pandas、`generate_signal(df)->(Signal.X,中文)`、資料不足先 HOLD）② 註冊 `backend/strategies/__init__.py`（import+1 行）③ 前端 `frontend/src/constants.js` 加 `{value,label}`（value==註冊鍵）④ 文件 `docs/strategies/<name>.md` ⑤ 測試 `tests/test_<name>.py`（BUY/SELL/資料不足三情境 + UTF-8 guard）。結尾強制 `pytest` + `get_strategy('<name>',{})` 驗證。

**命名**：註冊鍵/檔名 snake_case；類別 PascalCase+`Strategy`；`name` 屬性==註冊鍵==doc 檔名；撞名 `_v2`。

---

## 四、Part 2 — 後端：回測引擎升級 + 工作台 API

### 4A. `backend/services/backtest_engine.py` 加 EV 指標
現有輸出（總報酬/最大回撤/勝率/Buy&Hold）**新增**：`num_wins`/`num_losses`、`win_rate`/`loss_rate`、`avg_win`/`avg_loss`、**`expected_value`（EV/筆）**、`profit_factor`（總賺/總賠）、`expectancy`。純函式、加單元測試（合成交易序列驗 EV 算對）。

### 4B. 策略方案 API `backend/routers/presets.py`
- `GET/POST/PUT/DELETE /presets`（改名/調參數/收藏）。
- `POST /presets/{id}/backtest`：Python 跑回測 → 算含 EV 指標 → 存一筆 `BacktestRun` → 回結果。
- `GET /backtest-runs`（依 **EV 排序**，可篩 favorite）、`GET /backtest-runs/{id}`。

### 4C. Claude 助手 API `backend/routers/chat.py`
- `POST /chat`，**無狀態**（前端送完整 `messages`）。
- config 加 `ANTHROPIC_API_KEY`（⚠️ 獨立付費、與 Claude Code 訂閱不同；空值→400 不崩潰）、`ANTHROPIC_MODEL`（預設 `claude-haiku-4-5-20251001`）。
- tool-use 迴圈 + **prompt caching**，上限 ~5 圈。
- **Claude 工具＝唯讀記憶 + 思考**：`list_presets`、`list_backtest_runs`（含 EV + postmortem）、`get_backtest_run`、`list_bots`、`get_account`、`get_status`、`draft_strategy_spec`、`suggest_param_tweaks`。
  - **不開放**：跑回測（Python 按鈕做）、任何下單/submit、start/stop bot、shell、寫實盤、碰 `ALLOW_LIVE_TRADING`。
- **事後檢討端點** `POST /chat/postmortem`：input=某 `BacktestRun` → Claude 以 **EV 角度**分析「錯在哪、怎麼改」→ 存回 `BacktestRun.claude_postmortem`（下次 `list_backtest_runs` 讀得到 → 越來越聰明）。

---

## 五、Part 3 — 前端：右側「策略工作台」面板

### `frontend/src/components/StrategyWorkbench.jsx`
可收合（收合剩細條 + 展開鈕）、**可橫向拉寬**（左緣 6px 拖曳把手，自製 onMouseDown/Move/Up，寬度 clamp 320–720，存 localStorage）。套 `theme.js` 玻璃風 + NEON 青。分區：

1. **策略方案**：列出 presets，可新增/改名/調參數/收藏/刪除。
2. **一鍵回測（Python）**：選方案 → 按「跑回測」→ `POST /presets/{id}/backtest` → 結果卡（**EV 當頭條**）。EV<0 → 提示「建議按『檢討』」。
3. **回測歷史/好策略榜**：`GET /backtest-runs` 依 EV 排序，收藏標星。
4. **Claude 助手**：聊天區 + 每筆回測旁「總結這次錯在哪」按鈕 → `POST /chat/postmortem`。

### `App.jsx`：外層改橫向 flex row（左主內容 `flex:1,minWidth:0` + 右 `<StrategyWorkbench>`）。
### `api.js`：加 presets / backtest-runs / sendChat / postmortem 等呼叫。

---

## 六、建置順序（小步可交付，每步獨立 commit + 測試）

1. **Skill 先做**（零執行風險）→ 產一支玩具策略 → `pytest` 綠。
2. **回測引擎加 EV 指標** + 單元測試（純後端）。
3. **資料模型 + presets/backtest-runs API**（2 表 + Alembic + CRUD/回測存檔 + 測試）。
4. **前端工作台（先不接 Claude）**：面板 + App 版面 + presets/回測/歷史 UI；`/chat` 先回 stub。
5. **接真 Claude**：加 `anthropic` 依賴/config/.env；唯讀記憶工具 + prompt caching；`/chat`、`/chat/postmortem`。
6. （選配）主動提醒、好策略一鍵轉 Bot、tool_calls 顯示。

## 七、驗證重點
- Skill 產 5 產物 → `pytest` 綠 → 可實例化。
- EV 指標：合成交易序列手算對得上。
- Python 流：建方案 → 跑回測 → 看 EV → 存歷史 → 依 EV 排序；面板拉寬/收合。
- Claude：`/chat` 讀歷史；`/chat/postmortem` 存檢討；空金鑰回 400。
- 實盤仍封鎖：`/status` `live_armed:false`；`chat.py` 無 `submit_market_order`／`ALLOW_LIVE_TRADING`。
