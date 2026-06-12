# PostgreSQL 雲端同步（Neon）— 設定 / 搬遷 / 換機 runbook

> 目的：讓「公司電腦做過的資料」（總經數據、回測歷史、策略 preset、bots、決策 log）
> 不必回家重做。做法＝把資料庫從本機 SQLite 換成**雲端共用 PostgreSQL**，兩台電腦連同一個 DB。
>
> 原理：程式碼/筆記走 git；**跑出來的資料**在資料庫。SQLite 檔（`albee_stock.db`）被 gitignore、
> 不跟 git 走，所以改用雲端 PG＝兩台即時共享同一份資料。`config.py` 已支援 `DATABASE_URL` 覆寫，程式零改。

> ✅ **現況（2026-06-12）**：已正式切換 **Neon** 免費 PostgreSQL（17.x，新加坡區
> `ap-southeast-1`）。一次性搬遷已完成、Alembic schema 已建好（head `2639cd3d3e17` 當時）、
> 後端驗證通過。**新電腦只要做「[換電腦 / 新電腦](#換電腦--新電腦搬遷已完成超簡單)」那節**
> （填同一個 `DATABASE_URL` 即可，零搬遷）；「一次性搬遷」章節僅留作歷史紀錄與未來換供應商參考，**不要再跑**。

---

## Neon 開戶（已完成；留作換供應商 / 重建參考）

1. 開 https://neon.tech → 用 GitHub 或 Google 登入（免費方案，不用信用卡）。
2. **Create project**：名稱隨意（如 `albee-stock`），Region 選 **AWS Asia Pacific (Singapore)**
   （`ap-southeast-1`，離台灣最近；建立後不可改 region），Postgres 版本用預設即可。
3. **Neon Auth 不需要**——那是給 web app 做使用者登入註冊的服務；本專案只用資料庫本身，
   連線字串裡的帳密就是認證。
4. Dashboard 點 **Connect** → 複製連線字串，長相：
   ```
   postgresql://neondb_owner:npg_xxxx@ep-xxxx.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
   ```
   貼進 `.env` 的 `DATABASE_URL`（密碼別貼進任何會 commit 的檔或對話）。

> 💡 Neon 免費版閒置會 auto-suspend，第一個請求冷啟動多 1~2 秒，正常現象。

---

## 連線設定（`.env`）

`.env`（git 早就 ignore，密碼不外洩）加一行，把雲端 PG 連線字串填進去：

```
DATABASE_URL=postgresql://neondb_owner:<密碼>@ep-xxxx.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
```

- 整串直接從 Neon Dashboard 的 **Connect** 複製即可（含 `?sslmode=require`，雲端 PG 必加）。
- 換別家供應商（Supabase/Railway）格式同 `postgresql://<使用者>:<密碼>@<主機>:5432/<資料庫名>`，真實值後台都查得到。
- ⚠️ 密碼若含 `@ : / ? #` 等符號要 URL 編碼（例 `@`→`%40`、`#`→`%23`），否則連線字串會解析錯。
- 沒填 `DATABASE_URL`（或整行註解掉 `#`）＝**自動退回本機 SQLite**，App 照常能跑。
  → 還沒拿到真實連線字串前，先把這行註解掉，免得 App 連不上一個假主機而起不來。

確認有吃到：
```powershell
venv\Scripts\python.exe -c "from backend.config import settings; print(settings.DATABASE_URL)"
```
印出 `postgresql://...` 才往下。

---

## 一次性搬遷：SQLite → PostgreSQL（✅ 2026-06-12 已完成，勿重跑）

> ⚠️ 在**有現成資料的那台**跑，把本機 SQLite 資料推進雲端 PG。**只跑一次**（PG 空的時候）。
> 開始前先備份保險：複製一份 `albee_stock.db` 到別處。
> 本節**已執行完畢**，留作未來換供應商時的範本；其他電腦直接跳到「換電腦 / 新電腦」。

### Step 1 — 裝 PG 驅動（已完成 ✅）
```powershell
venv\Scripts\python.exe -m pip install psycopg2-binary
```
（已寫進 `requirements.txt`，家裡那台 `pip install -r` 會自動裝。）

### Step 2 — `.env` 填真實 `DATABASE_URL`
見上面「連線設定」。把假主機換成真值。

### Step 3 — 在 PG 建空表
```powershell
venv\Scripts\alembic.exe upgrade head
```
alembic 讀 `DATABASE_URL` → 在雲端 PG 建好所有表（此時空）。

### Step 4 — 把資料搬進去
存成專案根目錄 `migrate_once.py`（跑完即可刪，不必進 git）：

```python
# migrate_once.py — SQLite → PostgreSQL 一次性搬遷（跑完即可刪）
from sqlalchemy import create_engine, MetaData, insert, text

from backend.config import settings, BASE_DIR
import backend.models  # noqa: F401 — 載入全部 model，讓 metadata 認得所有表

SQLITE_URL = f"sqlite:///{BASE_DIR / 'albee_stock.db'}"
PG_URL = settings.DATABASE_URL
assert PG_URL.startswith("postgresql"), "DATABASE_URL 還沒指到 PostgreSQL，先做 Step 2"

src = create_engine(SQLITE_URL)
dst = create_engine(PG_URL)

meta = MetaData()
meta.reflect(bind=src)  # 反射 SQLite 既有所有表

# 1) 依 FK 相依順序逐表複製（父表先於子表）
#    插入前先清掉 PG 既有列——Alembic 遷移會種預設列（如 automation_config），
#    不先刪會撞 PK（實測踩到 duplicate key "automation_config_pkey"）。
#    SQLite 是真相來源，PG 此時只有種子資料，刪掉無損。反 FK 順序刪（子表先刪）。
with src.connect() as s, dst.begin() as d:
    for table in reversed(meta.sorted_tables):
        if table.name == "alembic_version":
            continue
        d.execute(table.delete())
    for table in meta.sorted_tables:
        if table.name == "alembic_version":
            continue  # 版本表 Step 3 已建好，別覆蓋
        rows = [dict(r._mapping) for r in s.execute(table.select())]
        if not rows:
            print(f"{table.name}: 0 列，跳過")
            continue
        d.execute(insert(table), rows)
        print(f"{table.name}: 搬 {len(rows)} 列")

# 2) 校正 PG 自增序列（手動帶 id 插入後，序列不會自動前進，否則下次新增撞 PK）
with dst.begin() as d:
    for table in meta.sorted_tables:
        if "id" not in table.columns:
            continue
        seq = d.execute(
            text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": table.name}
        ).scalar()
        if seq:
            d.execute(
                text(f"SELECT setval(:s, COALESCE((SELECT MAX(id) FROM {table.name}), 1))"),
                {"s": seq},
            )
print("✅ 搬遷完成")
```
執行：
```powershell
venv\Scripts\python.exe migrate_once.py
```
看到每張表「搬 N 列」+ `✅ 搬遷完成` 即成功。**只跑一次**；重跑會 PK 撞列。

### Step 5 — 驗證
```powershell
venv\Scripts\uvicorn.exe backend.main:app --reload
```
開 http://127.0.0.1:8000/docs，打 `GET /macro/series` 或看回測歷史頁，資料都在 → 成功。
之後 `.env` 維持指向 PG，**別再寫回 SQLite**（SQLite 之後新增的不會進 PG）。

---

## 換電腦 / 新電腦（搬遷已完成，超簡單）

> 給「另一台電腦上的人或 AI」看的完整設置流程——git pull 下來後照做即可。

1. `git pull`（develop）→ 拿到程式 + 這份 runbook（`requirements.txt` 已含 `psycopg2-binary`）。
2. `venv\Scripts\python.exe -m pip install -r requirements.txt`（或直接雙擊 `setup.bat`）。
3. 複製 `.env.example` 成 `.env`，`DATABASE_URL` 填**同一個 Neon 連線字串**
   （跟原電腦一模一樣；從 Neon Dashboard → Connect 重新複製也行）。其餘金鑰照常填。
4. 啟動後端 → 讀同一個雲端 PG，另一台做的資料全在，**零搬遷**。

驗證有連上 Neon：
```powershell
venv\Scripts\python.exe -c "from backend.config import settings; print(settings.DATABASE_URL)"
```
印出 `postgresql://...neon.tech...` 即正確；印出 `sqlite:///...` 表示 `.env` 沒填到。

> ⚠️ 新電腦**不要**跑 `migrate_once.py`（資料已在 PG，重搬會清掉雲端資料再用本機空 SQLite 蓋掉）。
> 也不用跑 `alembic upgrade head`——雲端 schema 已是最新；只有之後 git pull 拿到**新的遷移檔**時才需要跑。

---

## 之後 schema 有變（改 model 欄位時）

PG 通用同一套 Alembic 流程：
```powershell
venv\Scripts\alembic.exe revision --autogenerate -m "說明改了什麼"
# 檢查 alembic\versions\ 新檔無誤後：
venv\Scripts\alembic.exe upgrade head
```
在任一台跑 `upgrade head` 即改雲端 PG，另一台 `git pull` 拿到遷移檔後也 `upgrade head`（兩台 schema 同步）。

---

## 注意

- `migrate_once.py` 是一次性工具，跑完刪掉，不必進 git。
- 雲端 PG 帳密只放 `.env`（git ignore）；**絕不寫進任何會 commit 的檔**（含本檔、`backup.bat`）。
- `backup.bat`（複製 SQLite）退役，但留著當「PG 連不上時的本機保險」也無妨。
