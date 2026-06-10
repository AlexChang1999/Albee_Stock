# 步驟 2 — 多年 OHLCV 本機快取

> 讓「整個歷史」回測跑得起來、又不每次重抓外部 API。**狀態：已落地 ✅**。回到 [Phase 11 索引](README.md)。

## 已落地的檔（as-built）

| 檔 | 職責 |
|----|------|
| `backend/services/bar_cache.py` | `get_bars_cached(symbol, days, source, today=None)`：包在 `market_data.get_bars` 外層。缺口才補抓、寫進 parquet；命中快取 0 次 API。`today` 可注入（測試確定性）。內部 `_read/_write_cache`（parquet + `meta.json`）、`_merge`（去重保最新、升冪）、`_slice`（嚴格 ⊆ 請求區間） |
| `backend/config.py` | `BAR_CACHE_DIR`（預設 `data/cache/bars/`，按 `{source}/{symbol}` 分開存不混存） |
| `.gitignore` / `requirements.txt` | 加 `data/cache/`（快取不進版控）；加 `pyarrow`（parquet 引擎） |
| `tests/test_bar_cache.py` | 5 個純單元測試（合成 K 線 + monkeypatch `get_bars`，不連網） |

> **設計取捨（最關鍵）**：freshness 看 sidecar `meta.json` 的「已涵蓋的請求區間」，**不看最後一根 bar 日期**——
> 否則週末/假日/停牌時最後一根恆早於 today，會被誤判成缺口而無限重抓（DoD「第二次同請求 0 次 API」會破）。
> 接線回測/optimizer/screener 改吃快取 = **step-04** 的事，本步只交付可用模組 + 測試。

## 目標

支援多年（如 10 年 / `days=3650`）日 K 線回測，但**不要每次回測都向 Alpaca / yfinance 重抓**。
缺的區間才補抓、抓回來寫進本機快取；已有的區間命中快取、不重打。

## 概念名稱

**本機資料快取（Local Data Cache）** + 缺口補抓（Gap Filling）。
存成 **parquet**（欄式、壓縮、pandas 原生），放 `data/cache/bars/`（gitignore，不進版控）。

## 改動構想

- 新增 `backend/services/bar_cache.py`，**包在 `market_data.get_bars` 外層**，不改其簽章：
  - 既有：`market_data.get_bars(symbol, days=60, source="alpaca") -> DataFrame[open/high/low/close/volume/timestamp]`。
  - 新增：`get_bars_cached(symbol, days, source) -> DataFrame`——
    1. 讀 `data/cache/bars/{source}/{symbol}.parquet`（若有）。
    2. 算出快取覆蓋區間與請求區間的**缺口**（頭/尾）。
    3. 只對缺口呼叫 `market_data.get_bars` 補抓，`append` 後去重排序、寫回 parquet。
    4. 回傳請求區間的切片。
- `backend/config.py`：`BAR_CACHE_DIR`（預設 `data/cache/bars`）。
- `.gitignore`：加 `data/cache/`。
- 回測 / optimizer / screener 想跑多年時改呼叫 `bar_cache.get_bars_cached`（step-04 接線）。

## 重用現有

- `market_data.get_bars(symbol, days, source)` 當唯一底層抓取來源——cache **只包外層**，
  不改它、不繞過它（維持單一抓取路徑、好除錯）。
- pandas `to_parquet`/`read_parquet`（pandas 已是專案依賴）。

## 風險

- **快取一致性**：同 symbol 不同 source（alpaca vs yfinance）值可能不同 → 快取路徑按
  `{source}/{symbol}` 分開，**不可混存**（呼應「回測=實盤」：近端 OOS 驗證仍用實盤源對齊）。
- **不可成為偷看未來的後門**：cache 只是「少打幾次 API」，回傳區間仍嚴格等於請求區間，
  不得回傳請求結束日之後的列。
- **缺口判定要保守**：交易日空缺（假日 / 停牌）不可誤判成缺口而無限重抓——以「請求端點 vs 快取端點」
  比對，不以「逐日是否連續」比對。

## 驗收（DoD）

- 第一次抓某 symbol 多年 → 打外部 API 一次、寫出 parquet。
- 第二次同區間 → **命中快取、不打 API**（monkeypatch `market_data.get_bars`，斷言呼叫次數 0）。
- 請求比快取更早 / 更晚的區間 → 只補抓缺口那段（斷言補抓區間正確、結果無重複列、依時間升冪）。
- 回傳區間嚴格落在請求區間內（不洩漏請求結束日之後的資料）。
- 純單元測試（合成 K 線 + monkeypatch，不連網）。
