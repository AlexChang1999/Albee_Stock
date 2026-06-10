# 步驟 1 — 總經資料接入 + 本機快取 + point-in-time

> 整個 Phase 11 的地基：先把「環境資料的大腦」接上來。**狀態：已落地 ✅**。回到 [Phase 11 索引](README.md)。

## 目標

讓系統拿得到 FRED（聖路易聯準會，免費）的總經數據（非農 `PAYEMS`、失業率 `UNRATE`、聯邦基金利率
`FEDFUNDS`、CPI `CPIAUCSL`、公債殖利率 `DGS10`/`DGS2`、VIX `VIXCLS`），落成**本機快取**，
並從第一天就守住 **point-in-time**——回測在某日只能看到那日「已公布」的值，杜絕偷看尚未公布的未來。

## 概念名稱

**Point-in-Time Data（時間點正確資料）** / 發布落差（Publication Lag）。
經濟數據公布有遞延：某月的非農約在**次月第一個週五**才公布。所以同一筆要分兩個日期存：
- `period_date`：資料「所屬期間」（例：`2024-05-01` = 2024 年 5 月那筆）。
- `released_at`：市場「實際知道」這筆的日期 = `period_date + 發布落差`。

> 對齊一律用 `released_at`，**嚴禁用 `period_date` 偷看未公布的未來**。這是「回測=實盤」鐵則的延伸。

## 已落地的檔（as-built）

| 檔 | 職責 |
|----|------|
| `backend/services/fred_client.py` | 薄 FRED client（`requests` 打 `/fred/series/observations`）。`has_key()` / `get_observations()`；沒 `FRED_API_KEY` 或連不上 → 回 `None`（仿 `services/llm.py` 優雅降級，不崩、不阻斷其他功能） |
| `backend/services/macro_data.py` | 統一介面（仿 `market_data`）：`refresh_series`/`refresh_all`（打 FRED upsert 進快取）、`get_macro_series(db, series_id, as_of)`（讀快取；`as_of` 不為 None 時只回 `released_at <= as_of`）。函式都吃 `db: Session`（好測、不綁全域 session）。落差表 `_PUBLICATION_LAG_DAYS` 集中此處 |
| `backend/models/macro_series.py` | `MacroObservation` → 表 `macro_observations`。欄位 `series_id`/`period_date`/`released_at`/`value`/`source`/`fetched_at`；唯一鍵 `uq_macro_obs_series_period`(series+period) |
| `backend/routers/macro.py` | `GET /macro/series-list`（追蹤清單 + key 是否已設）、`GET /macro/series?series_id=&as_of=`（point-in-time 唯讀）、`POST /macro/refresh`（向 FRED 更新；沒 key 回友善 400） |
| `tests/test_macro.py` | 6 個純單元測試（記憶體 SQLite + `monkeypatch`，不連網） |

發布落差（保守取整，寧可晚看到不可早看到）：`PAYEMS`/`UNRATE`/`FEDFUNDS` = 35d、`CPIAUCSL` = 45d、
`DGS10`/`DGS2`/`VIXCLS` = 1d（日頻）；未知序列用 `settings.MACRO_DEFAULT_LAG_DAYS`（預設 35）。

## 改動構想（接線）

- `backend/config.py`：`FRED_API_KEY`（留空＝關閉）、`MACRO_SERIES`（預設
  `PAYEMS,UNRATE,FEDFUNDS,CPIAUCSL,DGS10,DGS2,VIXCLS`）、`MACRO_DEFAULT_LAG_DAYS`。
  **不另設 `MACRO_ENABLED`**——沒 key 即關，避免冗餘旗標（反 slop）。
- `backend/models/__init__.py`：註冊 `MacroObservation`（讓 `Base` 與 Alembic 認得）。
- `backend/main.py`：掛 `macro` router。
- `.env.example`：補上述欄位 + FRED 免費 key 申請註解。
- Alembic：`revision --autogenerate -m "macro_observations cache table"` → 人工檢查 → `upgrade head`。

## 重用現有

- `services/llm.py` 的「沒金鑰 → 優雅降級回 None」模式（`fred_client` 照抄精神）。
- `services/market_data.py` 的 dispatcher 風格（`macro_data` 當對外唯一介面）。
- `routers/factors.py` 的唯讀端點風格；`database.get_db` 的 `Depends` 注入。
- `database.Base` + `models/__init__.py` 模型註冊慣例；Alembic `render_as_batch`（SQLite 安全）。

## 洩漏風險（本步最關鍵）

- **唯一致命點＝偷看未來**：任何讀取若用 `period_date` 對齊就破功。守門集中在
  `get_macro_series` 的 `released_at <= as_of` 過濾——上層只要帶對 `as_of`（= 回測當日）即安全。
- **v1 用設定式發布落差近似 vintage**：落差只把資料往後推、永不提前 → 保守、誠實、可測。
  v2（記錄、本步不做）換 FRED/ALFRED 真實 vintage（`realtime_end`）拿歷史公布值，介面不變。

## 驗收（DoD — 已達成 ✅）

```powershell
venv\Scripts\python.exe -m pytest tests\test_macro.py -q   # → 6 passed
```

6 測試涵蓋：
1. `test_refresh_sets_released_at_with_publication_lag`：`released_at == period + 落差`（PAYEMS 35d）。
2. `test_point_in_time_hides_unreleased` ★：`as_of` 在公布前看不到、公布當日(含)後看得到。
3. `test_no_as_of_returns_all`：不帶 `as_of` 回全部（研究/報表視角）。
4. `test_refresh_is_idempotent_upsert`：重抓同期間更新值、不重複堆積（唯一鍵）。
5. `test_graceful_when_no_key`：沒 key（`get_observations` 回 None）→ `refresh` 回 0、不崩。
6. `test_publication_lag_fallback_for_unknown_series`：未知序列吃預設落差。

另：啟後端 → `GET /macro/series-list` 回 `fred_key_set` 與序列清單；沒填 key 時 `POST /macro/refresh`
回友善 400（不影響其他功能）。Alembic 遷移已 `upgrade head`，`macro_observations` 表在正式 DB。
