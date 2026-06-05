"""
策略清單 API（Phase 6 step-10）
================================
GET /strategies
  → 回傳全部可用策略的 [{value, label}] 清單（直接來自策略註冊表）。

為什麼要有這支？
  以前新增策略要同時改後端註冊表與前端清單（constants.js），靠人記得同步、容易漂移。
  把「策略清單」收成單一來源、對外曝露成 API 後，前端可改由此載入（或至少靠測試
  斷言前後端一致），新增策略時就不會再忘了某一處。
"""

from fastapi import APIRouter

from backend.strategies import list_strategies

router = APIRouter(tags=["Strategies"])


@router.get("/strategies")
def get_strategies():
    """回傳可用策略清單 [{value, label}]（value=代號、label=中文顯示名）。"""
    return list_strategies()
