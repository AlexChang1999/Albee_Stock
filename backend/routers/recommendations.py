"""
AI 策略探勘 API（改版 Phase 2）
================================
GET /ai-recommendations
  → 跑漏斗式篩選（量能 → 情緒 → EV 海選），回傳值得部署的策略推薦清單。

為什麼要快取？
  這支會對一籃股票抓資料、跑回測、（可能）呼叫本機 LLM，屬於「重」運算，
  按一次可能要好幾秒。用一個極簡的記憶體快取，短時間內重複呼叫直接回上次結果，
  避免使用者連點把本機跑爆。要強制重算就帶 ?refresh=true。

職責分離：這裡只「回推薦」，不建 Bot。前端按「一鍵 Deploy」時才走既有 POST /bots。
"""

import time

from fastapi import APIRouter, HTTPException

from backend.services.screener import screen_watchlist

router = APIRouter(tags=["Recommendations"])

# 極簡記憶體快取：{ key: (存入時間, 結果) }
_CACHE: dict = {}
_CACHE_TTL_SEC = 300  # 5 分鐘內視為新鮮


@router.get("/ai-recommendations")
def ai_recommendations(
    days: int = 365,
    initial_cash: float = 10000.0,
    source: str = "alpaca",
    min_ev: float = 0.0,
    refresh: bool = False,
):
    """
    回傳 AI 海選的推薦清單（依 EV 由高到低）。

    :param days: 回測往前抓幾天
    :param initial_cash: 每檔回測/建議配資的初始資金
    :param source: 資料源 alpaca（預設）/ yfinance
    :param min_ev: 只回 EV 大於此值的推薦（預設 0）
    :param refresh: True = 忽略快取強制重算
    """
    key = (days, initial_cash, source, min_ev)
    now = time.time()

    # 命中且未過期 → 直接回（標 cached=True 讓前端知道）
    if not refresh and key in _CACHE:
        ts, cached = _CACHE[key]
        if now - ts < _CACHE_TTL_SEC:
            return {**cached, "cached": True}

    try:
        result = screen_watchlist(
            days=days, initial_cash=initial_cash, source=source, min_ev=min_ev
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"AI 海選失敗：{e}")

    _CACHE[key] = (now, result)
    return {**result, "cached": False}
