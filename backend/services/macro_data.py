"""
總經 / 環境資料層（Phase 11 step-01）
====================================
對外統一介面，仿 services/market_data.py 的精神：上層只認識
get_macro_series / refresh_series，不直接碰 FRED 或 DB 細節。

做兩件事：
1. **本機快取**：先讀 macro_observations 表；要更新才打 FRED（fred_client），抓回來 upsert。
2. **point-in-time**：每筆存「資料期間 period_date」與「市場知道日 released_at = period + 發布落差」。
   讀取時可給 as_of，只回 released_at <= as_of 的值——這是「回測不能偷看尚未公布數據」的守門。

★ 函式都吃 db: Session（呼叫端／router 用 Depends(get_db) 帶進來），純粹好測、不綁全域 session。
"""

from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import MacroObservation
from backend.services import fred_client

# 各序列的「發布落差」天數：經濟數據公布遞延，回測當日只能看到已公布的。
# 保守取整（寧可晚看到、不可早看到）。未列的序列用 settings.MACRO_DEFAULT_LAG_DAYS。
_PUBLICATION_LAG_DAYS = {
    "PAYEMS": 35,    # 非農就業：次月第一個週五公布（period 是月初 → ~5 週）
    "UNRATE": 35,    # 失業率：與非農同步發布
    "CPIAUCSL": 45,  # CPI：次月中旬公布（period 是月初 → ~6 週）
    "FEDFUNDS": 35,  # 聯邦基金有效利率（月頻）：次月初公布
    "DGS10": 1,      # 10 年期公債殖利率（日頻）：隔日可得
    "DGS2": 1,       # 2 年期公債殖利率（日頻）
    "VIXCLS": 1,     # VIX 收盤（日頻）
}


def configured_series() -> list:
    """settings.MACRO_SERIES 解析成乾淨的序列代號清單。"""
    return [s.strip().upper() for s in settings.MACRO_SERIES.split(",") if s.strip()]


def publication_lag_days(series_id: str) -> int:
    """某序列的發布落差天數（未知序列用設定的預設）。"""
    return _PUBLICATION_LAG_DAYS.get(series_id.upper(), settings.MACRO_DEFAULT_LAG_DAYS)


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def refresh_series(db: Session, series_id: str) -> int:
    """
    向 FRED 抓某序列、upsert 進本機快取。回傳新增/更新的筆數。
    沒 FRED key 或抓取失敗 → 回 0（best-effort，不崩）。
    """
    series_id = series_id.upper()
    rows = fred_client.get_observations(series_id)
    if not rows:
        return 0

    lag = publication_lag_days(series_id)
    n = 0
    for r in rows:
        try:
            period = _parse_date(r["date"])
        except (KeyError, ValueError):
            continue
        released = period + timedelta(days=lag)
        # upsert：同序列同期間已存在就更新值，否則新增
        obs = (
            db.query(MacroObservation)
            .filter(
                MacroObservation.series_id == series_id,
                MacroObservation.period_date == period,
            )
            .one_or_none()
        )
        if obs is None:
            db.add(
                MacroObservation(
                    series_id=series_id,
                    period_date=period,
                    released_at=released,
                    value=r["value"],
                    source="fred",
                )
            )
        else:
            obs.value = r["value"]
            obs.released_at = released
            obs.fetched_at = datetime.now()
        n += 1
    db.commit()
    return n


def refresh_all(db: Session) -> dict:
    """把設定清單裡的每個序列都更新一次。回傳 {series_id: 筆數}。"""
    return {sid: refresh_series(db, sid) for sid in configured_series()}


def get_macro_series(
    db: Session, series_id: str, as_of: Optional[date] = None
) -> pd.DataFrame:
    """
    從本機快取讀某序列，回傳 DataFrame[period_date, released_at, value]（依期間升冪）。

    ★ as_of 不為 None 時，只回 released_at <= as_of 的列（point-in-time：回測在 as_of
      當日只看得到那天已公布的數據，杜絕偷看未來）。as_of=None＝研究/報表視角，回全部。
    """
    series_id = series_id.upper()
    q = db.query(MacroObservation).filter(MacroObservation.series_id == series_id)
    if as_of is not None:
        q = q.filter(MacroObservation.released_at <= as_of)
    obs = q.order_by(MacroObservation.period_date.asc()).all()
    return pd.DataFrame(
        [
            {"period_date": o.period_date, "released_at": o.released_at, "value": o.value}
            for o in obs
        ],
        columns=["period_date", "released_at", "value"],
    )
