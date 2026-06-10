# PostgreSQL 雲端同步 — 設定 / 搬遷 / 換機 runbook

> 目的：讓「公司電腦做過的資料」（總經數據、回測歷史、策略 preset、bots、決策 log）
> 不必回家重做。做法＝把資料庫從本機 SQLite 換成**雲端共用 PostgreSQL**，兩台電腦連同一個 DB。
>
> 原理：程式碼/筆記走 git；**跑出來的資料**在資料庫。SQLite 檔（`albee_stock.db`）被 gitignore、
> 不跟 git 走，所以改用雲端 PG＝兩台即時共享同一份資料。`config.py` 已支援 `DATABASE_URL` 覆寫，程式零改。

---

## 連線設定（`.env`）

`.env`（git 早就 ignore，密碼不外洩）加一行，把雲端 PG 連線字串填進去：

```
DATABASE_URL=postgresql://<使用者>:<密碼>@<主機>:5432/<資料庫名>
```

- `<使用者>` `<密碼>` `<主機>` `<資料庫名>` **全部要換成 PG 供應商給的真實值**（Supabase/Neon/Railway 後台都查得到）。
- ⚠️ 密碼若含 `@ : / ? #` 等符號要 URL 編碼（例 `@`→`%40`、`#`→`%23`），否則連線字串會解析錯。
- 沒填 `DATABASE_URL`（或整行註解掉 `#`）＝**自動退回本機 SQLite**，App 照常能跑。
  → 還沒拿到真實連線字串前，先把這行註解掉，免得 App 連不上一個假主機而起不來。

確認有吃到：
```powershell
venv\Scripts\python.exe -c "from backend.config import settings; print(settings.DATABASE_URL)"
```
印出 `postgresql://...` 才往下。

---

## 一次性搬遷：SQLite → PostgreSQL

> ⚠️ 在**有現成資料的那台**（目前是公司電腦）跑，把本機 SQLite 資料推進雲端 PG。**只跑一次**（PG 空的時候）。
> 開始前先備份保險：複製一份 `albee_stock.db` 到別處。

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
with src.connect() as s, dst.begin() as d:
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

## 回家那台（搬遷做完後，超簡單）

1. `git pull`（develop）→ 拿到合併後的程式 + 這份 runbook + `psycopg2-binary`。
2. `venv\Scripts\python.exe -m pip install -r requirements.txt`。
3. `.env` 設**同一個** `DATABASE_URL`（跟公司那台一模一樣）。
4. 啟動 → 讀同一個雲端 PG，公司做的全在，**零搬遷**。

> 家裡那台**不要**再跑 `migrate_once.py`（資料已在 PG，重搬會撞列）。

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
