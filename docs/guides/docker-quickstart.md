# Docker 一鍵起後端 + 前端

## 用法

```powershell
# 第一次：複製沙盒設定（預設值已經安全，不用改）
copy .env.docker.example .env.docker

# 起服務（--build 第一次跑或改了依賴時加）
docker compose up -d --build

# 驗證兩邊都活著
python scripts/smoketest.py

# 看 log / 關掉
docker compose logs -f backend
docker compose down
```

- 後端：http://localhost:8000/docs
- 前端：http://localhost:5173

## ⚠️ 為什麼是 `.env.docker`、不是 `.env`

正式 `.env` 指向 Neon 雲端 DB（多台電腦共用同一份正式資料）。docker 容器若讀到它，
開機會把自己當成第二個排程 leader，直接 resume 正式環境裡所有啟用中的 Bot——
已經實測炸過一次：190+ 個 Bot 同時掛起、Discord 推播連續打到 429。

`docker-compose.yml` 因此刻意只讀 `.env.docker`：強制走容器內獨立 SQLite
（`albee_backend_data` volume，空 DB，開機沒有任何 Bot 可 resume）+ 全部自動化
排程關閉（`CATCHUP_ON_BOOT`/`LEADER_BACKTEST_ENABLED`/`AUTO_DEPLOY_*`/... 皆
`false`）。想在沙盒裡測 Alpaca 連線，自行在 `.env.docker` 填 **Paper** 金鑰——
絕對不要把正式 `.env` 的金鑰或 `DATABASE_URL` 複製進 `.env.docker`。

## 檔案對照

| 檔案 | 用途 |
|------|------|
| `backend/Dockerfile` | Python 3.13-slim，開機先 `alembic upgrade head` 再起 `uvicorn` |
| `frontend/Dockerfile` | Node 22-slim，跑 Vite dev server（`--host 0.0.0.0`） |
| `docker-compose.yml` | 起後端(8000) + 前端(5173)，backend 有 healthcheck |
| `.env.docker.example` | 沙盒設定範本（進 git）；`.env.docker` 是實際使用的檔（gitignore） |
| `scripts/smoketest.py` | 免依賴（純標準庫），驗證後端/前端關鍵端點都正常回應 |

## 已知踩坑

- Docker Desktop 沒開會報 `failed to connect to the docker API at npipe://...`——
  先把 Docker Desktop 開起來（`docker info` 能跑出東西才算真的好了）。
- 容器內 SQLite 資料只活在 `albee_backend_data` volume：`docker compose down -v`
  會連資料一起清掉；只是 `down`（沒加 `-v`）資料還在，下次 `up` 會接回去。
