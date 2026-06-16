# 開發踩坑紀錄（dev-pitfalls-log）

> **這份是什麼**：把這個專案**實際踩過、用 commit 修掉**的坑收斂成一頁。每條含
> **症狀 / 根因 / 修法 / 出處 commit**，方便換電腦、新 AI 接手、自己回顧時一眼找到，
> 不必再翻 172 個 commit 的 `git log`。
>
> **與 CLAUDE.md 的分工**：[`CLAUDE.md`](../../CLAUDE.md)「已知注意事項」留**精簡鐵則**
> （開工前必記的少數規則）；本檔留**完整史料 + commit 溯源**（每個坑當初怎麼炸、怎麼修）。
> 兩處內容會交叉，但定位不同——CLAUDE.md 給「現在該怎麼做」，本檔給「為什麼這樣做、誰踩過」。
>
> 史料來源：各 fix commit body、`CHANGELOG.md`「修正」區塊、`CLAUDE.md` 已載入的坑。

---

## 快速索引

| 主題 | 坑（一句話） | 出處 commit |
|------|--------------|-------------|
| A. Windows 編碼 | 主控台 cp950 印中文/emoji 崩潰 | （`config.py` 既有） |
| A. Windows 編碼 | `.bat` 無 BOM 配 `chcp 65001` → command 無法辨識 | `8f91074` |
| A. Windows 編碼 | 本機 `.env` 被以錯誤編碼存檔，中文註解變亂碼 | （CHANGELOG） |
| B. DB / Alembic | schema 漂移：`no such column: bots.promotion_status` | `8f91074` |
| B. DB / Alembic | SQLite 沒開 `render_as_batch` → 改/刪欄位遷移失敗 | （CLAUDE.md） |
| B. DB / Alembic | `database.py` 寫死 `check_same_thread` → 換 PG 連線崩 | `893b022` |
| B. DB / Alembic | PostgreSQL boolean 遷移與 SQLite 0/1 不同調 | `7a6bb27` |
| B. DB / Alembic | SQLite→PG 搬遷種子列撞 PK | （CHANGELOG Neon） |
| C. 依賴 / 啟動 | `requirements.txt` psycopg2 重複釘版 → pip ResolutionImpossible | `93b3f65` |
| C. 依賴 / 啟動 | alpaca-py 模組載入即建 client，無金鑰 CI 光 import 就崩 | `c2173cd` |
| D. 測試確定性 | TestClient 寫進真 dev DB → 跨測試污染 | `6b461b5`、`13ef4bb` |
| E. 回測=實盤 | 樣本內挑冠軍 / 偷看未來 / 資料路徑分岔（過擬合） | `837160c` |
| E. 回測=實盤 | macro overlay 真資料 OOS 無加分 → 誠實砍層 | `893b022` |
| E. 回測=實盤 | kelly folds=0 同段估又複利（資料洩漏） | `f2fde4c` |
| F. 前端 | 寫死淺色 hex 貼深藍主題上隱形 | `631dac0` |
| G. 即時系統 | 政治員讀回自己通知 → 無限自我回饋（15 秒一筆） | `1df9d1b`、`0e5d45a` |
| H. Git 衛生 | worktree 殘留整包 repo 誤入 commit | `efc600d` |
| I. 前瞻偏誤 | 缺口判斷用日曆日非交易日 → 假日無限重抓 | （CHANGELOG Phase 11） |
| I. 前瞻偏誤 | macro `period_date` 偷看未公布未來 | （CHANGELOG） |
| J. Linux 部署 | APScheduler 吃伺服器本地時間 → 必設 `Asia/Taipei` | （CHANGELOG free-vm） |

---

## A. Windows 編碼

### A1. 主控台 cp950 印中文/emoji 崩潰
- **症狀**：後端啟動或腳本印 emoji/中文時 `UnicodeEncodeError`，整個程序崩。
- **根因**：Windows 主控台預設 cp950，無法編 emoji 與部分中文。
- **修法**：`backend/config.py` 開頭 `sys.stdout.reconfigure(encoding="utf-8")`。**獨立腳本**
  （如 `backend/test_connection.py`）不經 config，需自己加同一行。
- **出處**：`config.py` 既有修正（CLAUDE.md 已載）。

### A2. `.bat` 存成 UTF-8 無 BOM 配 `chcp 65001`
- **症狀**：`setup.bat` / `start_backend.bat` / `start_frontend.bat` 雙擊報 command 無法辨識。
- **根因**：`.bat` 含中文、存成 UTF-8 **無 BOM**，配 `chcp 65001` 觸發 cmd.exe 讀取位移 bug。
- **修法**：改存 **UTF-8 with BOM**（內容、CRLF 不動）。
- **出處**：commit `8f91074`。

### A3. 本機 `.env` 被以錯誤編碼存檔
- **症狀**：`.env` 中文註解全變亂碼。
- **根因**：編輯器以錯誤編碼存檔。
- **修法**：以 UTF-8 重存。**`.env` 不進 git，僅記錄為坑**（提醒編輯時鎖 UTF-8）。
- **出處**：CHANGELOG。

---

## B. 資料庫 / Alembic

### B1. schema 漂移 `no such column: bots.promotion_status`
- **症狀**：後端啟動報 `no such column: bots.promotion_status`。
- **根因**：DB schema 漂移——後續遷移的 `ALTER add_column` 從沒在這台機器跑過（活的 SQLite，非版控）。
- **修法**：對帳補上 `promotion_status` / `promotion_proposed_at` / `promotion_reason` 三欄。
  **正解是一律走 Alembic、絕不手動 `ALTER TABLE`**；新機 `alembic upgrade head` 一行建好。
- **出處**：commit `8f91074`。

### B2. SQLite 沒開 `render_as_batch`
- **症狀**：未來改/刪欄位的遷移在 SQLite 上失敗。
- **根因**：SQLite 的 `ALTER` 很弱（不能改/刪欄位），需 batch 模式重建表。
- **修法**：`alembic/env.py` 設 `render_as_batch=True`（已設）。
- **出處**：CLAUDE.md。

### B3. `database.py` 寫死 `check_same_thread` → 換 PostgreSQL 崩
- **症狀**：切 Neon PostgreSQL 後連線崩。
- **根因**：`connect_args={"check_same_thread": False}` 是 **SQLite 限定**參數，PG 不認。
- **修法**：`connect_args` 依方言（dialect）判斷，只在 SQLite 帶該參數。
- **出處**：commit `893b022`、CHANGELOG。

### B4. PostgreSQL boolean 遷移
- **症狀**：遷移在 PG 上 boolean 欄位行為與 SQLite 不一致。
- **根因**：SQLite 用 0/1 存 bool，PG 是原生 `boolean`，遷移需顯式處理。
- **修法**：支援 postgres boolean migration。
- **出處**：commit `7a6bb27`。

### B5. SQLite→PG 搬遷種子列撞 PK
- **症狀**：把本機 SQLite 資料搬進 Neon PG 時，遷移建立的種子列與插入資料撞主鍵。
- **根因**：遷移本身會種列，搬遷腳本又插同一批。
- **修法**：搬遷腳本**先清表再插入**。
- **出處**：CHANGELOG（Neon 搬遷，20 遷移／15 表）。

---

## C. 依賴 / 啟動

### C1. `requirements.txt` psycopg2-binary 重複釘版
- **症狀**：`pip install -r requirements.txt` 直接 `ResolutionImpossible`。
- **根因**：同檔出現 `psycopg2-binary==2.9.12` 與 `==2.9.10` 兩行（後者為 `29de1e5` 誤加孤行）。
- **修法**：刪孤行，保留有註解的 `2.9.12`。
- **出處**：commit `93b3f65`（孤行源自 `29de1e5`）。

### C2. alpaca-py 模組載入即建 client
- **症狀**：沒有 `.env` 的 CI 環境，光 `import` 服務層（test_backtest → backtest_engine → alpaca_client）就崩，CI 紅燈。
- **根因**：Alpaca SDK 建 client 當下就驗金鑰，金鑰為空丟 `ValueError`；模組頂層寫 `alpaca_client = AlpacaClient()` 在 import 時就建。
- **修法**：trading/data client 改用 `property` **延遲初始化**，第一次真正呼叫 API 才碰金鑰。
- **出處**：commit `c2173cd`。

---

## D. 測試確定性

### D1. TestClient 寫進真 dev DB → 跨測試污染
- **症狀**：`test_automation::test_run_dry_run` 間歇失敗（planned 被清空）。
- **根因**：`test_automation_config` 的 PUT roundtrip 用 TestClient 打到**真 dev DB**，把
  `ev_threshold` 寫成 321 持久化；後跑的測試靠預設門檻 150，被污染。另一例：`run_auto_deploy`
  查 Bot 表去重，dev DB 有同名 AAPL Bot → 候選被剔 → planned 空。
- **修法**：API 測試用 `app.dependency_overrides` 覆寫 `get_db` 成**臨時 SQLite**隔離；
  關鍵測試 stub 掉 `get_config` / `get_account` 回固定值，結果完全確定性。
- **出處**：commit `6b461b5`、`13ef4bb`。

---

## E. 回測=實盤誠實性（最易被破壞的鐵則）

> 核心信條：**回測看到的 EV 必須是實盤拿得到 EV 的誠實估計**。下面三件事不可分岔。

### E1. 樣本內挑冠軍 / 偷看未來 / 資料路徑分岔
- **症狀**：回測 EV 漂亮，實盤拿不到。
- **根因**：①整段歷史挑樣本內最佳（過擬合）；②用當根收盤、零成本成交（偷看未來）；
  ③實盤端寫死 `alpaca_client.get_bars(days=60)`、與回測資料源/回看長度分岔。
- **修法**：①挑冠軍/設門檻一律看 **OOS**（`optimizer` 以 `oos_expected_value` 排名）；
  ②走 `_simulate_from_signals`：手續費/滑價 + 訊號於**次根開盤成交**、最後一根不成交；
  ③實盤與回測都走 `market_data.get_bars(..., source=settings.DATA_SOURCE)` +
  `strategies/lookback.required_lookback_days(...)`。
- **出處**：commit `837160c`、CLAUDE.md。

### E2. macro overlay 真資料 OOS 無加分 → 誠實砍層
- **症狀**：macro 煞車層上線的衝動 vs 真資料驗證結果不符。
- **根因**：真 FRED 資料（7 series、41,604 obs）walk-forward 驗證，macro overlay 層
  `worth=False`、Δ=-101.68（baseline 91.17 → candidate -10.51）。
- **修法**：依紀律**誠實砍除被否決的 overlay 層**（刪 `MacroOverlayStrategy` 等），
  **保留 FRED 資料地基**（client/快取/特徵/路由）。保留有加分的層（adaptive +17.72、meta +38.88）。
- **教訓**：機制做出來≠該上線；**砍弱層、不美化數據**。
- **出處**：commit `893b022`。

### E3. kelly folds=0 資料洩漏
- **症狀**：kelly 層 folds=0、湊不到門檻全 skip，且估比例時有洩漏。
- **根因**：同一段資料估 W/R 又拿來複利（in-sample leakage）。
- **修法**：分離訓練/測試、用**擴張窗**估比例（嚴格 OOS），測試段套比例複利。修後 folds 0→2
  仍 < `MIN_FOLDS=3`（資料太薄）→ 無法認證，維持預設關但設計改善保留。
- **出處**：commit `f2fde4c`。

---

## F. 前端

### F1. 寫死淺色 hex 貼深藍主題上隱形
- **症狀**：元件文字在深藍面板上看不到（如寫死 `#1a2238` 深色字貼深底）。
- **根因**：全站走 `theme.js` 深藍主題，元件卻寫死淺色 hex。`Stat.jsx` 踩過。
- **修法**：用 `color="text.primary"` / `"text.secondary"` 或 `theme` / `NEON` 變數取色，
  **不寫死 hex**。新元件比照既有深底元件。
- **出處**：commit `631dac0`、CLAUDE.md。

---

## G. 即時系統迴圈

### G1. 政治員讀回自己通知 → 無限自我回饋
- **症狀**：實測 **15 秒一筆**風險警報洗版。
- **根因**：`DISCORD_WEBHOOK_URL`（系統通知）與 watcher 監看頻道為同頻道，自己發的警報被自己
  讀回判讀 → 再警報 → 無限迴圈。換新 webhook 後，舊 webhook 留在頻道歷史的訊息 id 已不同，
  webhook id 防護認不出，回補又被撿回。
- **修法**：**雙層保險絲**——①即時監聽與啟動回補都依 webhook id 跳過自己通知 webhook 發的訊息
  （`Webhook.from_url` 自帶 token，免 Manage Webhooks 權限）；②訊息開頭是固定指紋
  （🏛️ 政治風險訊號 / 💓 心跳）直接不收；on_message 與回補共用同一套 `_should_backfill_message`。
  on_ready 偵測同頻道時印設定錯誤警告。**正解仍是通知用獨立頻道專屬 webhook**，防護只是保險絲。
- **出處**：commit `1df9d1b`、`0e5d45a`。

---

## H. Git 衛生

### H1. worktree 殘留整包 repo 誤入 commit
- **症狀**：一個 commit 莫名多出整包 repo 副本（含 4327 行 `package-lock.json`）。
- **根因**：`.claude/worktrees/` 的 leftover worktree 是完整 repo 副本，被誤 add 進 commit。
- **修法**：移除誤入目錄，`.gitignore` 加 `.claude/worktrees/` 防再犯。
- **出處**：commit `efc600d`。

---

## I. 資料時間 / 前瞻偏誤

### I1. 缺口判斷用日曆日非交易日
- **症狀**：週末/假日/停牌時被誤判成資料缺口，**無限重抓**。
- **根因**：最後一根 K 線日期恆早於 `today`（日曆日），被當成缺口。
- **修法**：缺口判斷用**交易日**而非日曆日。
- **出處**：CHANGELOG（Phase 11）。

### I2. macro `period_date` 偷看未公布未來
- **症狀**：總經特徵潛在前瞻偏誤。
- **根因**：用 `period_date`（資料所屬期）會偷看當時尚未公布的未來值。
- **修法**：守門以實際公布時點為準，防前瞻（延續 step-01 守門）。沒 `FRED_API_KEY` 或連不上
  → 回 `None` 靜默跳過，不崩、不阻斷其他功能。
- **出處**：CHANGELOG。

---

## J. Linux 常駐部署

### J1. APScheduler 吃伺服器本地時間
- **症狀**：排程在雲端 VM（UTC）上於錯誤時間觸發。
- **根因**：APScheduler 預設吃**伺服器本地時間**，免費 VM 多為 UTC。
- **修法**：必設時區 `Asia/Taipei`。（另一 Linux 坑：systemd 服務設定。）
- **出處**：CHANGELOG（free-vm 部署）。

---

## 怎麼維護這份

- **每修掉一個有代表性的坑**，就在上面對應主題加一條（**症狀 / 根因 / 修法 / 出處 commit**）
  並補進「快速索引」表一列，附 commit hash。
- 同步精簡版鐵則進 [`CLAUDE.md`](../../CLAUDE.md)「已知注意事項」（只放開工必記的，細節留本檔）。
- commit hash 用短碼即可；要回查細節 `git show <hash>`。
