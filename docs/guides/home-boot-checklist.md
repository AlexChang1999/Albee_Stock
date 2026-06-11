# 回家開機測試 checklist（Phase 12 step-01 通電）

> 目的：在家裡那台電腦把系統跑起來，開始 collector 真 feed 觀察（3~7 天）。
> `.env` 不進 git，家裡要**手動重填**——本檔列出最小必填清單與步驟。
> 真實金鑰/密碼只填進 `.env`，**絕不**貼進任何會 commit 的檔案或對話。

---

## ⚠️ 開始前最大缺口：資料庫還不是真雲端

外面那台的 `DATABASE_URL` 指向 `localhost:5432`（本機 PostgreSQL，名字叫
Cloud-Postgres 但**不在雲端**）。家裡那台連不到它。二選一：

| 方案 | 做法 | 結果 |
|------|------|------|
| **A. 真雲端 PG（建議，原規劃）** | 到 [Neon](https://neon.tech) 或 [Supabase](https://supabase.com) 免費註冊 → 建專案拿連線字串 → 照 [`setup-postgres-sync.md`](setup-postgres-sync.md) 在**外面那台**搬一次資料（Step 2~5，來源改成從本機 PG 搬） → 兩台 `.env` 填**同一個**雲端 `DATABASE_URL` | 兩台共享同一份資料 |
| **B. 家裡先各自獨立（最快開測）** | 家裡 `.env` 的 `DATABASE_URL` 整行**註解掉**（或不填）→ 自動退回本機 SQLite | 馬上能測，但資料兩台不同步，之後做方案 A 再搬 |

> 方案 B 不影響 step-01 驗收（收料觀察只看家裡那台自己的收件匣）。

---

## 家裡開機步驟（一次做完）

```powershell
# 1. 拉最新程式（含 Phase 12 探勘橋）
git pull

# 2. 裝依賴 + 建/升級資料庫（setup.bat 已含 alembic upgrade head）
setup.bat

# 3. 確認 .env 填好（見下方清單）後啟動
start_backend.bat     # 後端 http://127.0.0.1:8000/docs
start_frontend.bat    # 前端 http://localhost:5173
```

啟動驗證：開 `http://127.0.0.1:8000/`，看到「Albee Stock 後端運行中 + paper_trading: true」即成功。

---

## `.env` 最小必填清單（開機測試用）

從 `.env.example` 複製成 `.env`，只需動這幾行：

```ini
# --- 必填：Alpaca Paper 金鑰（https://app.alpaca.markets 後台抓）---
ALPACA_API_KEY=PK開頭約20碼
ALPACA_SECRET_KEY=約40碼
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# --- 資料庫：方案 A 填雲端連線字串；方案 B 整行註解掉（退回 SQLite）---
# DATABASE_URL=postgresql://使用者:密碼@主機:5432/資料庫名
#（密碼含 @ : / ? # 等符號要 URL 編碼，例 @ → %40）

# --- Phase 12 step-01：collector 通電（本次測試主角）---
# 來源與 robots 檢查見 collector-feeds-guide.md
COLLECTOR_RSS_FEEDS=https://quantocracy.com/feed/,https://alphaarchitect.com/feed/
COLLECTOR_INTERVAL_MIN=60
```

**其餘全部不用動**（預設安全）：

| 群組 | 預設 | 說明 |
|------|------|------|
| `ALLOW_LIVE_TRADING` | false | 實盤安全閥，**不要碰** |
| `DISCOVERY_ENABLED` | false | 探勘橋（step-02）。等 collector 觀察幾天、確認素材品質後再開；開之前先 `ollama serve` + `ollama pull llama3.1` |
| `AUTO_DEPLOY_ENABLED` / `POLITICAL_ENABLED` | false | 自動部署 / 政治員，維持關 |
| LLM 三行 | 本機 Ollama | 沒裝 Ollama 也能開機（助手功能優雅回 400，不影響其他） |
| `LINE_*` / `DISCORD_WEBHOOK_URL` / `FRED_API_KEY` | 空 | 通知與總經選用，留空照常運作 |

---

## 開機後驗收（step-01 runbook 摘要）

1. 等一輪排程（60 分）或手動跑：
   ```powershell
   venv\Scripts\python.exe -c "from backend.services.collector import run_collector_scan; run_collector_scan()"
   ```
2. 前端「市場蒐集員」頁看到 status=new 素材 → 入庫成功。
3. 同指令再跑一次：素材數不變 → 去重正常。
4. 之後 3~7 天每天看一眼收件匣（素材量 / 垃圾率 / 後端 log 有無例外）。
   詳細判讀標準見 [`collector-feeds-guide.md`](collector-feeds-guide.md)。

---

## 目前還缺什麼（誠實盤點，2026-06-11）

1. **真雲端 PG**：上面方案 A 還沒做——兩台共用資料的前提。
2. **collector 真 feed 觀察 3~7 天**：step-01 DoD 的人工部分，本檔就是要開始它。
3. **探勘橋實戰**：程式已完成（step-02），但 `DISCOVERY_ENABLED` 還沒開過真素材。
4. **Phase 12 step-03~05 未開工**：自動批次驗證 / 漏斗報表 / 端到端兩週檢討。
5. **Telegram 通知半成品**：躺在 `worktree-notify-telegram-line` 分支（未 commit 的
   `_send_telegram`），要用需補完合併；外面那台 `.env` 已預留 `TELEGRAM_*` 鍵。
