"""
基本面 / 財報 / 新聞 API
========================
用 yfinance 抓資料，提供四個查詢端點。實際邏輯都在 services/fundamentals.py。

- GET /fundamentals/{symbol}             公司基本資料
- GET /fundamentals/{symbol}/financials  財報三表（?period=annual|quarterly）
- GET /fundamentals/{symbol}/news        相關新聞
- GET /fundamentals/{symbol}/actions     配息 / 分割歷史
"""

from fastapi import APIRouter, HTTPException

from backend.services import fundamentals

router = APIRouter(prefix="/fundamentals", tags=["Fundamentals"])


@router.get("/{symbol}")
def profile(symbol: str):
    """公司基本資料（市值、PE、EPS、產業、簡介…）。"""
    try:
        return fundamentals.get_profile(symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"取得基本資料失敗：{e}")


@router.get("/{symbol}/financials")
def financials(symbol: str, period: str = "annual"):
    """財報三表。period 可填 annual（年度，預設）或 quarterly（季度）。"""
    if period not in ("annual", "quarterly"):
        raise HTTPException(status_code=400, detail="period 只能是 annual 或 quarterly")
    try:
        return fundamentals.get_financials(symbol.upper(), period=period)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"取得財報失敗：{e}")


@router.get("/{symbol}/news")
def news(symbol: str):
    """個股相關新聞。"""
    try:
        return fundamentals.get_news(symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"取得新聞失敗：{e}")


@router.get("/{symbol}/actions")
def actions(symbol: str):
    """配息與股票分割歷史。"""
    try:
        return fundamentals.get_actions(symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"取得配息/分割失敗：{e}")
