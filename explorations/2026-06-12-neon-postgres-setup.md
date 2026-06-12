# 2026-06-12 — Neon 雲端 PostgreSQL 設置過程（SQLite → Neon 搬遷實錄）

## 背景與動機

專案原本用本機 SQLite（`albee_stock.db`，被 gitignore），跑出來的資料（回測歷史、
bots、決策 log、總經數據）綁死在單一電腦上。為了「換電腦就有、多台共享同一份資料」，
依 `docs/guides/setup-postgres-sync.md` 規劃把資料庫換成雲端 PostgreSQL，供應商選 **Neon**。

`backend/config.py` 早已支援 `DATABASE_URL` 由 `.env` 覆寫：填了就連 PG、
留空自動退回 SQLite——所以整個切換**程式碼零修改**，只動設定與資料。

## 選型決策

- **供應商：Neon**（免費方案、不用信用卡；Supabase/Railway 為備選，連線字串格式通用）。
- **Region：AWS Asia Pacific (Singapore) `ap-southeast-1`**——離台灣最近、延遲最低；
  Neon 專案建立後 region 不可改。
- **Postgres 版本：預設（17）**——SQLAlchemy + psycopg2 全相容，專案無版本特定功能。
- **Neon Auth：不需要**——那是給 web app 做使用者登入註冊的服務（類似 Firebase Auth）；
  本專案只用資料庫本身，連線字串帳密即認證。

## 實際執行步驟（公司電腦，2026-06-12）

1. **前置確認**：`psycopg2-binary 2.9.12` 已在 venv（`requirements.txt` 已含）；
   `albee_stock.db` 存在；`.env` 的 `DATABASE_URL` 原指向 `localhost` 假雲端
   （名叫 Cloud-Postgres 但不在雲端，家裡連不到——這是切換的根本原因）。
2. **備份**：複製 `albee_stock.db` 到專案外（保險，PG 穩定後可丟）。
3. **Neon 開戶**：neon.tech 註冊 → Create project（Singapore、PG 17）→
   Dashboard「Connect」複製連線字串（含 `?sslmode=require`）→ 貼進 `.env`。
4. **連線驗證**：SQLAlchemy `create_engine` + `SELECT version()` →
   `PostgreSQL 17.10 on aarch64-unknown-linux-gnu`，通。
5. **建 schema**：`alembic upgrade head` → 20 個遷移全跑過，15 張表，
   head `2639cd3d3e17`。
6. **搬資料**：跑一次性 `migrate_once.py`（SQLite 反射全表 → 依 FK 順序插入 PG →
   `setval` 校正自增序列）。
7. **驗證**：查 PG 表數/列數/alembic 版本 + 起 uvicorn 煙霧測試
   （`GET /` 回 `{"message":"Albee Stock 後端運行中","paper_trading":true}`）。

## 踩坑與修正（最有價值的部分）

### 坑 1：Alembic 遷移種子列撞 PK

第一次跑搬遷腳本就炸：

```
psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint
"automation_config_pkey"  DETAIL: Key (id)=(1) already exists.
```

**原因**：`alembic upgrade head` 建表時，部分遷移會**種預設列**（如
`automation_config` 的單列設定表）。搬遷腳本假設 PG 全空，直接插入 SQLite 的
id=1 → 撞主鍵。

**修正**：搬遷腳本插入前先清空 PG 目標表（此時 PG 只有種子列，SQLite 是真相來源，
刪掉無損）。刪除走**反 FK 順序**（`reversed(meta.sorted_tables)`，子表先刪），
插入走正 FK 順序（父表先插）。整段在單一交易內，第一次失敗時已自動回滾、無半套資料。
修正版已回寫進 runbook 的腳本範本。

### 坑 2（觀察）：本機 SQLite 其實近乎全空

搬遷結果只有 `automation_config` 1 列，其餘表全 0 列——這台沒累積過資料。
教訓：搬遷前先看清楚來源有什麼，別假設「一定有一堆資料要搬」。雲端因此是乾淨起點。

### 坑 3（環境）：PowerShell 內嵌 python -c 的引號逃逸

驗證指令在 PowerShell 用 `\"` 逃逸雙引號會炸 parser——複雜驗證一律寫成小 .py 檔再跑，
別硬塞 one-liner。

## 後續文件落地（commit `280bea1`，develop）

- `docs/guides/setup-postgres-sync.md`：改為 Neon 實際流程 + 踩坑修正 +
  「換電腦 / 新電腦」完整設置節（git pull 後照做、勿重跑搬遷）。
- `CLAUDE.md` / `.env.example`：補 `DATABASE_URL` 欄位與 runbook 指引，
  新電腦的人或 AI pull 下來即知去哪設置。
- `docs/guides/home-boot-checklist.md`：「資料庫非真雲端」缺口標記已解決。
- `CHANGELOG.md`：未發布區記錄。

## 營運注意

- Neon 免費版閒置 auto-suspend，第一個請求冷啟動多 1~2 秒，正常。
- 之後 schema 變更照舊走 Alembic：任一台 `upgrade head` 即改雲端，另一台
  pull 到遷移檔後也跑一次（兩台 schema 同步）。
- `.env` 的 `DATABASE_URL` 別註解掉——會默默退回 SQLite，資料分岔。
- 連線字串（含密碼）只進 `.env`，絕不進 git / 對話 / 文件。
