"""
環境特徵（Macro Features）── Phase 11 step-03
==============================================
把 step-01 的總經序列（FRED）以 **point-in-time** 對齊到價格 df 的每一根 K 棒，
輸出成「每根一列」的特徵欄，給 step-04 的回測引擎當輸入。

設計鐵則（對齊 Phase 11 README + step-03 DoD）：
- **as-of 一律用 `released_at`**：對每根 bar 的日期 d，各序列只取 `released_at <= d` 的
  最後一筆（forward-fill）。**嚴禁用 period_date** ——否則會把「下個月才公布的數據」
  貼到本月，洩漏未來、回測虛高。這是「回測 = 實盤」鐵則的延伸（守門延續 step-01）。
- **無未來函數**：第 i 根的特徵只看 `released_at <= bar_date_i` 的觀測，與其他 bar 無關 →
  對 df.iloc[:i+1] 與完整 df 在第 i 根算出同值。
- **特徵不是越多越好**：先給 6 個有直覺、可解釋的，別一次塞 30 個（每多一欄 = 多一個過擬合自由度）。
- **優雅降級**：沒 FRED 資料（沒 key / 沒 refresh）→ 各欄為 NaN，不崩、不阻斷回測。

風格仿 `services/regime_features.compute_features`（每根一列、可解釋、不黑箱）。
as-of 取值直接重用 step-01 的 `macro_data.get_macro_series`（每序列載一次全量、依 period 升冪）。
"""

from datetime import date
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from backend.services import macro_data

# 要用到的 FRED 序列（與 config.MACRO_SERIES 的代號一致）
_SERIES_IDS = ["FEDFUNDS", "UNRATE", "CPIAUCSL", "DGS10", "DGS2", "VIXCLS"]

# 本檔輸出的特徵欄（缺資料時為 NaN）
_FEATURE_COLS = [
    "fed_funds_level",
    "fed_funds_3m_chg",
    "unemployment_trend",
    "cpi_yoy",
    "yield_curve",
    "vix_level",
]


def _as_of_value(
    series_df: pd.DataFrame, on_date: date, periods_back: int = 0
) -> Optional[float]:
    """
    某序列在 on_date「當下看得到」的值（point-in-time）：
    取 `released_at <= on_date` 的可見子集，回第 (-1 - periods_back) 筆的 value。

    - periods_back=0 → 最新可見值（as-of 當期）。
    - periods_back=N → 可見序列往回數 N 期（算變化 / 年增率用）。
    可見筆數不足 → None（→ 上層該欄填 NaN，代表「公布前」沒有當期值，不偷看未來）。
    """
    if series_df is None or series_df.empty:
        return None
    visible = series_df[series_df["released_at"] <= on_date]
    if len(visible) <= periods_back:
        return None
    return float(visible["value"].iloc[-1 - periods_back])


def attach_macro_features(price_df: pd.DataFrame, db: Session) -> pd.DataFrame:
    """
    吃一段 K 線 DataFrame（需有 timestamp 欄），回傳「複製一份並加上 6 個環境特徵欄」。

    新增欄（全部 as-of `released_at` 對齊，公布前為前值 / NaN，非當期值）：
    - fed_funds_level    ：聯邦基金利率水位（FEDFUNDS as-of）
    - fed_funds_3m_chg   ：FEDFUNDS 近 3 期變化（升 / 降息趨勢；月頻 ≈ 3 個月）
    - unemployment_trend ：UNRATE 近 3 期變化（上升 = 衰退傾向）
    - cpi_yoy            ：CPI 年增率 %（CPIAUCSL 近 12 期；通膨溫度）
    - yield_curve        ：DGS10 − DGS2（殖利率曲線，倒掛 = 衰退預警）
    - vix_level          ：VIX 收盤（恐慌指數，高 = risk-off）

    不改傳入的 df（回傳新物件）。空 df / 無 timestamp → 原樣回傳。
    """
    if price_df is None or price_df.empty or "timestamp" not in price_df:
        return price_df.copy() if price_df is not None else pd.DataFrame()

    df = price_df.copy()

    # 各序列只載一次全量（依 period 升冪、含 released_at），之後對每根 bar 做 as-of 切片
    series = {sid: macro_data.get_macro_series(db, sid) for sid in _SERIES_IDS}
    fed, unr, cpi = series["FEDFUNDS"], series["UNRATE"], series["CPIAUCSL"]
    dgs10, dgs2, vix = series["DGS10"], series["DGS2"], series["VIXCLS"]

    bar_dates = pd.to_datetime(df["timestamp"]).dt.date

    rows = []
    for d in bar_dates:
        fed_now = _as_of_value(fed, d, 0)
        fed_3m = _as_of_value(fed, d, 3)
        unr_now = _as_of_value(unr, d, 0)
        unr_3m = _as_of_value(unr, d, 3)
        cpi_now = _as_of_value(cpi, d, 0)
        cpi_yr = _as_of_value(cpi, d, 12)
        dgs10_now = _as_of_value(dgs10, d, 0)
        dgs2_now = _as_of_value(dgs2, d, 0)

        rows.append(
            {
                "fed_funds_level": fed_now,
                "fed_funds_3m_chg": (
                    fed_now - fed_3m if fed_now is not None and fed_3m is not None else None
                ),
                "unemployment_trend": (
                    unr_now - unr_3m if unr_now is not None and unr_3m is not None else None
                ),
                "cpi_yoy": (
                    (cpi_now / cpi_yr - 1.0) * 100.0
                    if cpi_now is not None and cpi_yr not in (None, 0)
                    else None
                ),
                "yield_curve": (
                    dgs10_now - dgs2_now
                    if dgs10_now is not None and dgs2_now is not None
                    else None
                ),
                "vix_level": _as_of_value(vix, d, 0),
            }
        )

    feat = pd.DataFrame(rows, columns=_FEATURE_COLS, index=df.index)
    # None → NaN（float 欄，下游可一致處理）
    for col in _FEATURE_COLS:
        df[col] = pd.to_numeric(feat[col], errors="coerce")
    return df
