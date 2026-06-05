"""
組合回撤熔斷（Phase 6 step-09）
================================
給整個帳戶一個「自動剎車」：當總權益從峰值回落超過門檻，暫停所有新增曝險
（新買進 + 自動部署），但既有持倉的風控出場照常運作。這是跑真錢的最後一道安全網。

設計：
- portfolio_circuit_breaker(...)：純函式，只判斷「是否該熔斷」，好寫單元測試。
- check_breaker(db)：best-effort 編排——查帳戶權益、更新持久化峰值、回是否熔斷；
  查不到帳戶（離線 / 無金鑰）一律「不熔斷」放行，不阻斷其他流程。
- 觸發時 notify 一次（去抖，避免每輪洗版）。
"""

import time

from backend.config import settings
from backend.database import SessionLocal
from backend.models import PortfolioState
from backend.services.alpaca_client import alpaca_client
from backend.services.notifier import notify


# ============================================================
# 純函式：是否該熔斷
# ============================================================
def portfolio_circuit_breaker(equity_now: float, equity_peak: float, max_dd_pct: float) -> bool:
    """
    依「當前權益 / 歷史峰值 / 最大回撤門檻」判斷是否該熔斷。

    回撤% =（峰值 − 現值）÷ 峰值 × 100；>= 門檻即熔斷。
    峰值無效（None / <=0）→ 不熔斷（還沒有有效水位可比）。
    現值 > 峰值（創新高）→ 回撤為負 → 不熔斷。
    """
    if not equity_peak or equity_peak <= 0:
        return False
    drawdown_pct = (equity_peak - equity_now) / equity_peak * 100
    return drawdown_pct >= max_dd_pct


# ============================================================
# 持久化峰值讀寫
# ============================================================
def _get_or_create_state(db) -> PortfolioState:
    """取出單列 portfolio_state（id=1），沒有就建一筆空的。"""
    st = db.query(PortfolioState).filter(PortfolioState.id == 1).first()
    if st is None:
        st = PortfolioState(id=1, equity_peak=None)
        db.add(st)
        db.commit()
        db.refresh(st)
    return st


# ============================================================
# 通知去抖（避免熔斷期間每輪都發）
# ============================================================
_last_notify_ts: float = 0.0
NOTIFY_COOLDOWN_SEC = 3600  # 同一波熔斷最多每小時通知一次


def _notify_tripped_once(equity_now: float, equity_peak: float) -> None:
    global _last_notify_ts
    now = time.monotonic()
    if now - _last_notify_ts < NOTIFY_COOLDOWN_SEC:
        return
    _last_notify_ts = now
    notify(
        f"🛑 組合回撤熔斷觸發：總權益 ${equity_now:,.2f} / 峰值 ${equity_peak:,.2f}"
        f"（回撤 ≥ {settings.PORTFOLIO_MAX_DRAWDOWN_PCT}%）。"
        "暫停所有新增曝險（新買進 / 自動部署），既有持倉的風控出場照常運作。"
    )


# ============================================================
# 編排：查權益 → 更新峰值 → 回是否熔斷（best-effort）
# ============================================================
def check_breaker(db=None) -> dict:
    """
    best-effort 跑一輪熔斷檢查。

    :return: dict {tripped, equity_now, equity_peak}。
        查不到帳戶權益（離線 / 無金鑰 / 出錯）→ tripped=False（放行，不阻斷流程）。
    """
    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        try:
            acct = alpaca_client.get_account()
            equity_now = float(acct.portfolio_value)
        except Exception:
            # best-effort：取不到權益就不熔斷（離線不阻斷既有流程）
            return {"tripped": False, "equity_now": None, "equity_peak": None}

        st = _get_or_create_state(db)
        peak = st.equity_peak
        if peak is None or equity_now > peak:
            peak = equity_now
            st.equity_peak = peak
            db.commit()

        tripped = portfolio_circuit_breaker(
            equity_now, peak, settings.PORTFOLIO_MAX_DRAWDOWN_PCT
        )
        if tripped:
            _notify_tripped_once(equity_now, peak)
        return {"tripped": tripped, "equity_now": equity_now, "equity_peak": peak}
    finally:
        if own_session:
            db.close()
