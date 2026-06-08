"""
公司戰情聚合 API（Phase 10 step-01）
====================================
把現有各服務的「現況」聚合成一包，給前端「公司戰情頁」一次畫出整間 AI 公司。

定位是**唯讀、純呈現層**：這裡只「轉述」既有服務的結果（帳戶 / Bot / 自動化規則 /
熔斷 / 最近決策），**不自己算交易、不算 EV、不下任何動作**。所有 alpha 與交易邏輯
仍在各既有模組，本端點只負責「組裝成一頁看得到的公司」。

設計要點：
- 帳戶區塊 best-effort——沒設 Alpaca 金鑰 / 離線時回 None，不讓整頁崩（其餘區塊純讀 DB）。
- 不新增任何 schema；只讀既有表與服務。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Bot, DecisionLog
from backend.services.alpaca_client import alpaca_client
from backend.services.automation_config import get_config
from backend.services.circuit_breaker import check_breaker

router = APIRouter(prefix="/company", tags=["Company"])


def _account_best_effort() -> dict | None:
    """取帳戶摘要；沒金鑰 / 連不上 Alpaca 時回 None（不丟錯，讓整頁照畫）。"""
    try:
        acc = alpaca_client.get_account()
        return {
            "status": str(acc.status),
            "cash": acc.cash,
            "buying_power": acc.buying_power,
            "portfolio_value": acc.portfolio_value,
        }
    except Exception:
        return None


@router.get("/overview")
def company_overview(decisions_limit: int = 10, db: Session = Depends(get_db)):
    """
    一次回傳整間公司的現況，給戰情頁的「部門卡」用。

    各區塊都只轉述既有服務：帳戶（best-effort）、Bot 艦隊、自動化規則、風控熔斷、
    最近決策審計。**不在這裡做任何交易 / 部署動作。**
    """
    # --- Bot 艦隊（純讀 DB）---
    bots = db.query(Bot).all()
    bot_list = [
        {
            "id": b.id,
            "name": b.name,
            "symbol": b.symbol,
            "strategy": b.strategy,
            "is_active": b.is_active,
        }
        for b in bots
    ]
    active_count = sum(1 for b in bots if b.is_active)

    # --- 自動化規則（模式 B 總開關 + 雙重門檻 + 名額）---
    cfg = get_config(db)
    automation = {
        "enabled": cfg.enabled,
        "ev_threshold": cfg.ev_threshold,
        "winrate_threshold": cfg.winrate_threshold,
        "max_bots": cfg.max_bots,
        "cash_per_bot": cfg.cash_per_bot,
        "scan_hour": cfg.scan_hour,
    }

    # --- 風控熔斷（best-effort，內部離線會回 None 不丟錯）---
    breaker = check_breaker(db)

    # --- 最近決策審計（跨所有 Bot，倒序）---
    rows = (
        db.query(DecisionLog)
        .order_by(DecisionLog.created_at.desc(), DecisionLog.id.desc())
        .limit(max(1, min(decisions_limit, 100)))  # 夾在 1~100，防一次撈爆
        .all()
    )
    decisions = [
        {
            "id": r.id,
            "bot_id": r.bot_id,
            "symbol": r.symbol,
            "signal": r.signal,
            "reason": r.reason,
            "price": r.price,
            "action": r.action,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]

    return {
        "account": _account_best_effort(),
        "bots": {"total": len(bots), "active": active_count, "list": bot_list},
        "automation": automation,
        "circuit_breaker": breaker,
        "decisions": decisions,
    }
