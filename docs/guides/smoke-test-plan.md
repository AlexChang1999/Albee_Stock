# Smoke Test 計畫書（煙霧測試）

> **定位**：上線前 / 部署後 / 換機後 / A1 全上雲後，用來「一鍵驗系統健康」的最後一道關卡。
> 不是驗每個零件的細部邏輯（那是 490+ 單元測試的事），而是驗**整台機器開得起來、
> 核心端點真的回得了話**。

---

## 1. 為什麼需要它（補的三個缺口）

| 缺口 | 原狀況 | 本計畫補法 |
|------|--------|------------|
| 沒有整合煙霧測試 | `tests/test_api.py` 寫了範例但沒掛進 pytest（沒被收集），等於沒人在跑 | `tests/test_smoke.py`（`pytest -m smoke`） |
| CI 不跑前端 | `ci.yml` 只跑 backend，31 個 Vitest + `npm run build` 從沒驗 | CI 新增 `frontend` job |
| 部署健檢太淺 | `deploy.sh` 只 `curl GET /` 看服務活著，不驗功能端點 | `scripts/smoke_test.sh` 掛進 deploy 健檢 |

系統正處**混合雲過渡期**（部分服務已上 Oracle Micro VM，其餘等 A1 釋出才全上雲），
更需要一份不論本機或雲端都能跑的健康檢查。

---

## 2. 煙霧測試 vs 單元測試

| | 單元測試（`tests/test_*.py`） | 煙霧測試（本計畫） |
|---|---|---|
| 問題 | 「這個函式邏輯對不對？」 | 「整個系統起得來、核心路徑通不通？」 |
| 範圍 | 單一函式 / 模組，大量 mock | 端到端：起 app → 打真端點 |
| 數量 | 490+ 細測 | 約 20 條關鍵路徑 |
| 失敗代表 | 某個零件邏輯錯 | **啟動級故障**（DB 連不上、router 掛了、設定爆了） |

---

## 3. 涵蓋範圍（4 層）

| 層 | 驗什麼 | 工具 | 在哪跑 |
|----|--------|------|--------|
| **L1 後端啟動 + API** | FastAPI 起得來、lifespan 不爆（init_db + scheduler leader 選舉）、核心 GET 端點回 200 | `pytest -m smoke` / `smoke_test.sh` | 本機 + 雲端 + CI |
| **L2 前端 build + 載入** | `npm run test`（Vitest）綠、`npm run build` 建得起來 | CI `frontend` job | 本機 + CI |
| **L3 部署 / 上雲健檢** | deploy.sh 健檢 + 線上 smoke、失敗自動 rollback、systemd 服務活著 | `deploy.sh` + `smoke_test.sh` | 雲端 VM |
| **L4 外部整合連通性** | 缺金鑰時優雅降級不爆 500；有金鑰時 Alpaca/Neon 連得上 | `pytest -m smoke`（+ `RUN_INTEGRATION_SMOKE=1`） | 本機 + 雲端 |

---

## 4. 測試清單

### L1 後端啟動 + API（`tests/test_smoke.py`）

| 測試 | 端點 | 預期 | 失敗代表 |
|------|------|------|----------|
| `test_root_health` | `GET /` | 200 + `paper_trading` 欄位 | 服務根本沒起來 / lifespan 炸 |
| `test_status` | `GET /status` | 200 + `is_paper`/`allow_live`/`live_armed` | 設定讀不到 |
| `test_read_endpoints_respond` | 18 個無金鑰讀端點（見下） | 全 200 | 某 router 掛了 / DB 連不上 |

無金鑰讀端點清單：`/bots` `/trades` `/presets` `/backtest-runs` `/strategies`
`/positions` `/reminders` `/automation` `/factors` `/company/overview` `/explorations`
`/knowledge` `/opportunities` `/promotions` `/political/events` `/political/risk`
`/macro/series-list` `/collector/finds`

> **刻意不放**：`/account`、`/quotes/{symbol}`、`/bars/{symbol}`（需真金鑰、失敗回 400 → 放整合層）；
> `/ai-recommendations`（會真跑一輪海選回測，重、慢，不適合煙霧）。

### L4 外部整合

| 測試 | 預期 | 備註 |
|------|------|------|
| `test_positions_degrades_without_key` | `/positions` 無金鑰回 `[]` 而非 500 | 預設跑 |
| `test_account_reachable` | `/account` 回 200 含 `cash` | 需 `RUN_INTEGRATION_SMOKE=1` |
| `test_quote_reachable` | `/quotes/AAPL` 回 200 | 需 `RUN_INTEGRATION_SMOKE=1` |

### L2 前端（CI `frontend` job）

| 步驟 | 指令 | 失敗代表 |
|------|------|----------|
| 單元測試 | `npm run test` | 元件 / hook / util 邏輯壞 |
| production build | `npm run build` | import 錯 / 語法錯 / bundle 建不起來 |

### L3 部署健檢（`scripts/smoke_test.sh`，deploy.sh 自動跑）

打 `/` `/status` `/bots` `/strategies` `/positions` `/reminders`，任一異常 → `exit 1` → 觸發 rollback。

---

## 5. 三種跑法

### 本機開發
```powershell
# 後端煙霧（無金鑰也應全綠，驗降級）
venv\Scripts\python.exe -m pytest -m smoke -q

# 線上煙霧：先起後端（視窗 A），再另開 Git Bash 跑腳本（視窗 B）
venv\Scripts\uvicorn.exe backend.main:app          # 視窗 A
```
```bash
bash scripts/smoke_test.sh                          # 視窗 B → 期望「🎉 線上 smoke 全過」

# 前端
cd frontend && npm run test && npm run build
```

### CI（自動）
`.github/workflows/ci.yml`：
- `test` job：lint → **`pytest -m smoke`** → 全套 pytest → alembic upgrade → import 煙霧 → 漂移檢查
- `frontend` job：`npm ci` → `npm run test` → `npm run build`
- `deploy` job：`needs: [test, frontend]`，兩者全綠才部署

### 雲端 VM
```bash
# deploy.sh 已自動在健檢通過後跑 smoke_test.sh；也可手動：
bash scripts/smoke_test.sh http://127.0.0.1:8000
```

### 整合層（換機 / 上雲後手動驗一次，需真金鑰）
```bash
RUN_INTEGRATION_SMOKE=1 pytest -m smoke -q          # 含 /account /quotes 真連線
```

---

## 6. 混合雲現況對照

| 服務 | 現況 | 怎麼 smoke |
|------|------|-----------|
| 後端 API（FastAPI） | 已上 Oracle Micro VM（`158.101.127.219`，systemd `albee-backend`） | VM 上 `bash scripts/smoke_test.sh`；deploy 時自動跑 |
| 排程 / Bot 引擎 | 隨後端在 VM（leader 選舉，單實例執行排程） | `/status` + 觀察 deploy 健檢 |
| 前端 | 本機 / 待全上雲 | CI `frontend` job + 本機 `npm run build` |
| DB（Neon PG） | 已上雲（多機共用） | `RUN_INTEGRATION_SMOKE=1` 驗真連線；CI 用臨時 SQLite |
| 其餘待 A1 | A1 釋出後遷移 | 遷移後在新機重跑本計畫全部三種跑法 |

> 雲端／地端劃分紅線見 [`cloud-local-division.md`](cloud-local-division.md)；上雲步驟見 [`cicd-vm-setup.md`](cicd-vm-setup.md)。

---

## 7. 故障排除（常見紅燈）

| 症狀 | 可能原因 | 查法 |
|------|----------|------|
| smoke 全部「連不上」 | 後端沒起來 / 埠不對 | `journalctl -u albee-backend -n 50`（VM）；本機看 uvicorn log |
| `pytest -m smoke` collection 崩潰 | 誤收 `backend/test_connection.py` | 已用 `pyproject.toml` `testpaths=["tests"]` 鎖定 |
| `/positions` 回 500 而非 `[]` | alpaca_client 降級被改壞 | 看 `backend/services/alpaca_client.py` 的 except 是否還吞例外 |
| 整合層測試紅 | 缺金鑰 / Neon 連不上 | 確認 `.env` 的 `ALPACA_*` / `DATABASE_URL`；無金鑰本就該跳過 |
| 前端 build 紅 | import / 語法錯 | 本機 `cd frontend && npm run build` 看錯誤行 |
| deploy 一直 rollback | 健檢或 smoke 過不了 | VM 上手動 `bash scripts/smoke_test.sh` 看哪個端點掛 |

---

## 8. 相關檔案

- `tests/test_smoke.py` — 後端煙霧測試（L1 + L4）
- `scripts/smoke_test.sh` — 線上端點煙霧（L3）
- `scripts/deploy.sh` — 健檢通過後跑 smoke_test.sh
- `.github/workflows/ci.yml` — CI smoke 步驟 + frontend job
- `pyproject.toml` — 註冊 `smoke` marker + `testpaths`
- `tests/conftest.py` — `_disable_boot_side_effects`（煙霧測試不真打網路）
