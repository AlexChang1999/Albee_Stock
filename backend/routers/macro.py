"""
總經 / 環境資料 API（Phase 11 step-01）
======================================
讓前端 / 查驗能讀本機快取的總經序列，並手動觸發向 FRED 更新。
定位：唯讀為主 + 一個更新觸發。總經數據是「環境因子」，給回測與報表看，這裡不下單、不建 Bot。
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services import macro_data, fred_client

router = APIRouter(prefix="/macro", tags=["Macro"])


@router.get("/series-list")
def list_configured_series():
    """目前設定要追蹤的 FRED 序列代號清單（含是否已設 FRED key）。"""
    return {
        "fred_key_set": fred_client.has_key(),
        "series": macro_data.configured_series(),
    }


@router.get("/series")
def get_series(
    series_id: str,
    as_of: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """
    讀某序列的本機快取觀測值（依期間升冪）。
    帶 as_of（YYYY-MM-DD）= point-in-time：只回那天已公布的值（回測誠實視角）。
    """
    df = macro_data.get_macro_series(db, series_id, as_of=as_of)
    return {
        "series_id": series_id.upper(),
        "as_of": as_of.isoformat() if as_of else None,
        "count": len(df),
        "observations": [
            {
                "period_date": r["period_date"].isoformat(),
                "released_at": r["released_at"].isoformat(),
                "value": r["value"],
            }
            for _, r in df.iterrows()
        ],
    }


@router.post("/refresh")
def refresh(db: Session = Depends(get_db)):
    """
    向 FRED 抓設定清單裡的所有序列、更新本機快取。回傳每序列更新筆數。
    沒設 FRED_API_KEY → 回 400 友善提示（其餘功能不受影響）。
    """
    if not fred_client.has_key():
        raise HTTPException(
            status_code=400,
            detail=(
                "尚未設定 FRED_API_KEY。請到 "
                "https://fred.stlouisfed.org/docs/api/api_key.html 免費申請後填入 .env，"
                "即可抓非農 / 失業率 / 利率 / CPI 等總經數據。"
            ),
        )
    counts = macro_data.refresh_all(db)
    return {"refreshed": counts, "total": sum(counts.values())}
