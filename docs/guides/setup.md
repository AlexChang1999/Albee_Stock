# 換電腦開發環境設置指南

這份文件記錄在**新電腦** `git clone` 之後，需要完成哪些設置才能跑起來。

> 為什麼需要這份文件？因為有些東西（金鑰、虛擬環境、套件）基於安全或體積考量
> 被 `.gitignore` 排除了，**不會跟著 git 走**，必須在新電腦上重建。

---

## ⚠️ 出發前（在舊電腦）務必先做

確認今天的程式碼都已經 commit 並 push 到 GitHub，否則新電腦 clone 不到：

```powershell
git add .
git commit -m "你的訊息"
git push
```

另外，**`.env` 不會被 push**（裡面有 API 金鑰，故意排除）。請先把金鑰另外記下來，
方法二選一：
- 用隨身碟 / 密碼管理器，把 `.env` 內容複製到新電腦
- 或回家後重新到 [Alpaca](https://app.alpaca.markets) 後台複製 Paper 金鑰

---

## 新電腦設置步驟

### 0. 先安裝必備軟體

| 軟體 | 版本 | 下載 |
|------|------|------|
| Python | 3.13 | <https://www.python.org/downloads/> |
| Node.js | v24（或 LTS） | <https://nodejs.org/> |
| Git | 最新 | <https://git-scm.com/> |

安裝後確認版本：

```powershell
python --version
node --version
git --version
```

### 1. 取得程式碼

```powershell
git clone https://github.com/AlexChang1999/Albee_Stock.git
cd Albee_Stock
```

### 2. 後端：建立虛擬環境 + 安裝套件

```powershell
# 建立虛擬環境（資料夾名稱用 venv，跟 .gitignore 一致）
python -m venv venv

# 安裝後端依賴
venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. 設定 .env（最容易忘記的一步！）

```powershell
# 用範本複製一份
copy .env.example .env
```

然後用編輯器打開 `.env`，填入 Alpaca 金鑰（不要加引號、不要有多餘空格）：

```
ALPACA_API_KEY=你的_PK開頭金鑰
ALPACA_SECRET_KEY=你的_Secret金鑰
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

> （選用）`DATA_SOURCE` 控制抓 K 線的資料源，回測與實盤共用同一設定：
> `alpaca`（預設）或 `yfinance`（免費、無金鑰）。不填就用 `alpaca`。

### 4. 前端：安裝套件

```powershell
cd frontend
npm install
cd ..
```

---

## 驗證設置成功

```powershell
# 1) 測試後端能連上 Alpaca（會顯示帳戶餘額）
venv\Scripts\python.exe backend\test_connection.py

# 2) 跑後端完整單元測試（不需連線，全過代表程式碼完整）
venv\Scripts\python.exe -m pytest tests/ -q

# 3) 跑前端單元測試（在 frontend 資料夾）
cd frontend
npm run test
cd ..
```

三個都成功，就代表新電腦環境 OK 了。

---

## 啟動專案（開兩個終端機）

```powershell
# 終端機 1：後端
venv\Scripts\uvicorn.exe backend.main:app --reload

# 終端機 2：前端
cd frontend
npm run dev
```

- 後端 API 文件：<http://127.0.0.1:8000/docs>
- 前端畫面：<http://localhost:5173>

---

## 「不會跟著 git 走」的東西清單

clone 後這些**不存在**，要靠上面步驟重建：

| 項目 | 為什麼被排除 | 怎麼重建 |
|------|------------|---------|
| `.env` | 含 API 金鑰，外洩有風險 | 步驟 3：從範本複製並填入金鑰 |
| `venv/` | 虛擬環境體積大、跟系統綁定 | 步驟 2：重新建立 |
| `frontend/node_modules/` | 套件體積巨大 | 步驟 4：`npm install` |
| `albee_stock.db` | 本機資料庫，各電腦獨立 | 後端首次啟動會**自動建立**空的 |

> 注意：資料庫不會同步，所以新電腦一開始**沒有任何 Bot 和交易紀錄**，這是正常的。

---

## Claude Code 技能（plugin）自動安裝

本專案把要用的 Claude Code plugin 設定寫在 `.claude/settings.json`（**有進 git**），
所以在新電腦用 Claude Code 開啟本專案時，會**自動提示安裝**這些 plugin，按同意即可：

| plugin | 用途 | 來源 marketplace |
|--------|------|------------------|
| `caveman` | 壓縮溝通模式（caveman/cavecrew/commit/review 全家） | GitHub `JuliusBrussee/caveman` |
| `frontend-design` | 前端設計 skill（做 React UI 時用） | 官方 `claude-plugins-official` |

另外 `.claude/skills/strategy-builder/`（把交易策略一條龍變成程式）是**專案內建 skill**，
直接跟著 repo 走、不必安裝。

> 機器專屬的個人設定（bgIsolation、個人 permissions）請放 `.claude/settings.local.json`
> （**不進 git**），不要塞進共享的 `settings.json`。

---

## 之後每次「換電腦繼續開發」的日常流程

```powershell
# 開工前：把另一台電腦的最新進度拉下來
git pull

# pull 後若有人改過資料庫 schema（新增 alembic/versions/ 遷移檔），升級本機 DB：
venv\Scripts\alembic.exe upgrade head

# 若 requirements.txt / package.json 有更新，補裝依賴：
venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend && npm install && cd ..

# 收工前：把這台的進度推上去
git add .
git commit -m "今天做了什麼"
git push
```

> 養成「開工 pull、收工 push」的習慣，兩台電腦就不會打架。
> `git pull` 看到 `alembic/versions/` 有新檔，記得 `alembic upgrade head`，否則新欄位 / 新表會對不上。
