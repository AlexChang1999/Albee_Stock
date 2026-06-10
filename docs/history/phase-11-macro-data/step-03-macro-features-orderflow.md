# 步驟 3 — 環境特徵 + 買賣壓代理

> 把總經序列與「買賣壓」對齊成回測吃得到的特徵欄。**狀態：已落地 ✅**。回到 [Phase 11 索引](README.md)。

## 已落地的檔（as-built）

| 檔 | 職責 |
|----|------|
| `backend/services/macro_features.py` | `attach_macro_features(price_df, db)`：對每根 bar 取各序列 `released_at <= bar_date` 的最後一筆 forward-fill，加 6 欄（`fed_funds_level`/`fed_funds_3m_chg`/`unemployment_trend`/`cpi_yoy`/`yield_curve`/`vix_level`）。內部 `_as_of_value(series_df, on_date, periods_back)` 是 point-in-time 取值核心。重用 `macro_data.get_macro_series` |
| `backend/services/orderflow_proxy.py` | `compute_orderflow(price_df)`：tick 規則加 4 欄（`buy_vol_proxy`/`sell_vol_proxy`/`net_pressure`/`pressure_ratio`）。平盤/首根對半、零量 ratio 給中性 0.5；守恆等式 `buy+sell==volume` |
| `tests/test_orderflow.py`（6 測）/ `tests/test_macro_features.py`（6 測） | 純函式 + 記憶體 SQLite，驗對齊不洩漏 / 恆等式 / 方向 / 無未來函數 |

> **誠實標註**：買賣壓是 **tick 代理**（漲跌方向 × 總量），**不是**真實逐筆 order flow（真值需付費源
> Polygon/Databento，列範圍外）。兩模組皆**純函式、無未來函數**；接線回測引擎吃 `features` = **step-04**。

## 目標

兩件事，都輸出成「每根 K 棒一列」的特徵，給 step-04 的回測引擎當輸入：
1. **環境特徵**：把 step-01 的總經序列 as-of 對齊到價格 `df` 的日期。
2. **買賣壓代理**：免費資料源拿不到真實 order flow（只有總成交量），用 **tick 規則**近似買/賣量。

## 候選特徵

### 環境特徵（`macro_features.py`，全部用 `released_at` 對齊）

| 特徵 | 來源序列 | 直覺 |
|------|----------|------|
| `fed_funds_level` | `FEDFUNDS` | 利率水位（高利率 = 緊縮環境） |
| `fed_funds_3m_chg` | `FEDFUNDS` | 近 3 月變化（升息 / 降息趨勢） |
| `unemployment_trend` | `UNRATE` | 失業率趨勢（上升 = 衰退傾向） |
| `cpi_yoy` | `CPIAUCSL` | CPI 年增率（通膨溫度） |
| `yield_curve` | `DGS10 - DGS2` | 殖利率曲線（倒掛 = 衰退預警） |
| `vix_level` | `VIXCLS` | 恐慌指數（高 = risk-off） |

### 買賣壓代理（`orderflow_proxy.py`，tick 規則）

| 輸出 | 規則 |
|------|------|
| `buy_vol_proxy` | `close > prev_close` → 當根 `volume` 計買壓；否則 0 |
| `sell_vol_proxy` | `close < prev_close` → 當根 `volume` 計賣壓；否則 0（平盤歸前一方向或對半，需在測試定義清楚） |
| `net_pressure` | `buy_vol_proxy - sell_vol_proxy` |
| `pressure_ratio` | `buy_vol_proxy / (buy_vol_proxy + sell_vol_proxy)` |

> **誠實標註**：這是 **tick 代理**（用漲跌方向把總量歸給買 / 賣方），**不是**真實逐筆 order flow。
> 真值要付費資料源（Polygon / Databento），列在 Phase 11 範圍外。不可包裝成真 order flow 行銷。

## 改動構想

- 新增 `backend/services/macro_features.py`：`attach_macro_features(price_df, db) -> df`——
  對每個 bar 日期，取各序列中 `released_at <= bar_date` 的**最後一筆** forward-fill 成欄位。
- 新增 `backend/services/orderflow_proxy.py`：`compute_orderflow(price_df) -> df`（加上四個代理欄）。
- 兩者皆**純函式、無未來函數**（第 i 根只看 `df.iloc[:i+1]`，與回測 walk-forward 同紀律）。

## 重用現有

- `strategies/indicators.py` 的 OBV / MFI 類量價慣例（買賣壓代理同精神）。
- `services/regime_features.py` 的特徵對齊風格（每根一列、可解釋、不黑箱）。
- step-01 的 `macro_data.get_macro_series(db, series_id, as_of=bar_date)` 直接當 as-of 取值來源。

## 洩漏 / 過擬合風險

- **as-of 一律用 `released_at`**：對齊時若用 `period_date` 就把「下個月才公布的數據」貼到本月 →
  洩漏未來、回測虛高。守門延續 step-01 鐵則。
- **特徵不是越多越好**：先給上表 6 + 4 個有直覺的，別一次塞 30 個（每多一欄就多一個過擬合自由度）。
- **代理恆等式必須成立**：`buy_vol_proxy + sell_vol_proxy == volume`（平盤處理方式要明確且測到）。

## 驗收（DoD）

- `attach_macro_features`：某序列值只在其 `released_at` 之後的 bar 才出現（公布前該欄為前值 / NaN，**非**當期值）。
- 對 `df.iloc[:i+1]` 與完整 `df` 在第 i 根算出的特徵一致（無未來函數）。
- `compute_orderflow`：`buy_vol_proxy + sell_vol_proxy == volume`；上漲根買壓 > 0 且賣壓 == 0，下跌根反之。
- 純函式單元測試（合成序列驗對齊不洩漏 + 代理恆等式 + 方向）。
