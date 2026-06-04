"""
AI 策略探勘 API ── Phase 2
============================
把 services/screener.py 的「漏斗式海選」開成一個 HTTP 端點，給前端
「AI 策略探勘中心」分頁呼叫，渲染成高期望值（EV>0）的推薦卡片。

只有一個端點：
- GET /ai-recommendations ：跑一輪海選，回推薦清單（依 EV 由高到低）

設計重點：
- 純讀取、不改任何資料（不建 Bot、不下單），純粹「給建議」。
- 預設 source="yfinance"，免 Alpaca 金鑰也能跑出結果。
- 海選可能花幾秒到幾十秒（取決於池子大小與本機算力），屬正常。
"""

from fastapi import APIRouter, HTTPException, Query

from backend.services import screener

router = APIRouter(tags=["AI"])


@router.get("/ai-recommendations")
def get_ai_recommendations(
    days: int = Query(180, ge=30, le=730, description="每檔往前抓幾天 K 線"),
    volume_multiplier: float = Query(
        2.5, ge=0.0, description="第一層量比門檻（最新量/20日均量 ≥ 此值才過關）"
    ),
    min_ev: float = Query(0.0, description="第二層期望值門檻（EV ≥ 此值才進推薦）"),
    top: int = Query(10, ge=1, le=50, description="最多回傳幾筆推薦"),
    source: str = Query("yfinance", description="資料源：yfinance（免費）或 alpaca"),
    symbols: str | None = Query(
        None, description="自訂海選池，逗號分隔（如 AAPL,MSFT）；留空用預設池"
    ),
):
    """
    跑一輪 AI 漏斗式海選，回推薦清單。

    流程（細節見 services/screener.py）：
      第一層 量能篩選 → 第二層 多策略回測取 EV 最高 → 依 EV 排序回前 top 筆。
    """
    # 把 "AAPL,MSFT" 這種字串轉成清單；留空就用預設池
    symbol_list = None
    if symbols:
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]

    try:
        return screener.screen(
            symbols=symbol_list,
            days=days,
            volume_multiplier=volume_multiplier,
            min_ev=min_ev,
            top=top,
            source=source,
        )
    except ValueError as e:
        # 例如不支援的 source
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"海選失敗：{e}")
