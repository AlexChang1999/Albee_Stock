"""
Agent Gateway — 外部 AI agent 受限存取（採納自 QuantDinger 的 Agent Gateway）
=========================================================================
讓 Claude / Cursor 等外部 AI 透過 bearer token 驅動我們的回測 / 策略 / 知識庫查詢，
並可下「預設 paper」的單。配套的 stdio MCP server 在 mcp_server/。

安全三層（沿用「回測=實盤」與實盤雙閘的精神）：
1. **token 閘**：每個端點都要 `Authorization: Bearer <AGENT_API_TOKEN>`。
   未設 AGENT_API_TOKEN → 整組 Gateway 回 503（預設關，沒設就用不了）。token 不符 → 401。
2. **唯讀為主**：絕大多數端點只查資料（回測 / 策略 / 帳戶 / 機會 / 知識），不改狀態。
3. **下單預設 paper**：唯一的寫入端點 POST /orders 預設只能下 paper 單；要碰真錢須
   AGENT_LIVE_TRADING_ENABLED=true（第三道閘），且仍由 alpaca_client 的實盤雙閘把關。

每筆呼叫落 agent_audits 審計表（append-only，best-effort 不阻斷主流程）。
"""

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import AgentAudit, BacktestRun, Bot
from backend.services.alpaca_client import alpaca_client
from backend.services.backtest_engine import run_backtest
from backend.strategies import list_strategies, STRATEGY_PARAM_SPECS
# 復用既有 router 的序列化器，避免兩處手寫漂移
from backend.routers.opportunities import _serialize as _serialize_opportunity
from backend.routers.knowledge import _dict as _serialize_knowledge
from backend.models import Opportunity, StrategyKnowledge

router = APIRouter(prefix="/api/agent/v1", tags=["Agent Gateway"])


# ---------- 審計 ----------
def _audit(db: Session, endpoint: str, params: dict | None, status: str, detail: str = "") -> None:
    """寫一筆 agent 呼叫審計（best-effort：寫失敗只吞掉，不影響 agent 的查詢/下單結果）。"""
    try:
        db.add(AgentAudit(
            endpoint=endpoint,
            token_label="default",  # 目前單 token；未來多 token 才有區別
            params=params,
            status=status,
            detail=detail[:500] if detail else None,
        ))
        db.commit()
    except Exception:
        db.rollback()


# ---------- token 閘（FastAPI dependency）----------
def require_agent_token(authorization: str = Header(default="")) -> str:
    """
    驗 bearer token。未設 AGENT_API_TOKEN → 503（Gateway 整組關）；token 不符 → 401。
    用 secrets.compare_digest 做常數時間比對，避免時序側信道。
    """
    if not settings.AGENT_API_TOKEN:
        raise HTTPException(status_code=503, detail="Agent Gateway 未啟用（.env 未設 AGENT_API_TOKEN）")
    prefix = "Bearer "
    token = authorization[len(prefix):] if authorization.startswith(prefix) else ""
    if not token or not secrets.compare_digest(token, settings.AGENT_API_TOKEN):
        raise HTTPException(status_code=401, detail="agent token 無效或缺漏")
    return token


# 整個 router 都掛 token 閘
_guard = Depends(require_agent_token)


# ---------- 唯讀端點 ----------
@router.get("/strategies", dependencies=[_guard])
def agent_list_strategies(db: Session = Depends(get_db)):
    """列出可用策略（代號 + 中文名）與各自合法參數 schema，給 agent 知道能跑什麼、怎麼填參數。"""
    _audit(db, "/api/agent/v1/strategies", None, "ok")
    return {"strategies": list_strategies(), "param_specs": STRATEGY_PARAM_SPECS}


class AgentBacktestRequest(BaseModel):
    """agent 跑回測要傳的資料（與 /backtest 一致，預設值方便最小呼叫）。"""
    strategy: str = "rsi"
    symbol: str
    params: dict = {}
    days: int = 365
    initial_cash: float = 10000.0
    source: str = settings.DATA_SOURCE
    allow_short: bool = False  # 做空開關：僅回測評估用，實盤 Bot 只做多


@router.post("/backtest", dependencies=[_guard])
def agent_backtest(payload: AgentBacktestRequest, db: Session = Depends(get_db)):
    """跑一次回測（走與前端 /backtest 完全相同的 run_backtest，含成本 + 隔日成交 + OOS）。"""
    snapshot = payload.model_dump()
    try:
        result = run_backtest(
            strategy_name=payload.strategy,
            symbol=payload.symbol.upper(),
            params=payload.params,
            days=payload.days,
            initial_cash=payload.initial_cash,
            source=payload.source,
            allow_short=payload.allow_short,
        )
        _audit(db, "/api/agent/v1/backtest", snapshot, "ok",
               f"EV={result.get('expected_value')}")
        return result
    except Exception as e:
        _audit(db, "/api/agent/v1/backtest", snapshot, "error", str(e))
        raise HTTPException(status_code=400, detail=f"回測失敗：{e}")


@router.get("/backtest/history", dependencies=[_guard])
def agent_backtest_history(limit: int = 20, db: Session = Depends(get_db)):
    """
    列出最近的回測歷史，依 EV 由高到低，給 agent 參考過去跑過什麼、表現如何。

    EV 等績效存在 metrics JSON 裡（不是扁平欄位），故在 Python 端排序：先抓較多筆、
    用 metrics.expected_value 排序後截斷（量不大，足夠用）。
    """
    rows = (
        db.query(BacktestRun)
        .order_by(BacktestRun.created_at.desc())
        .limit(200)
        .all()
    )

    def _ev(r: BacktestRun) -> float:
        v = (r.metrics or {}).get("expected_value")
        return v if isinstance(v, (int, float)) else float("-inf")

    rows = sorted(rows, key=_ev, reverse=True)[: max(1, min(limit, 100))]
    _audit(db, "/api/agent/v1/backtest/history", {"limit": limit}, "ok")
    return [
        {
            "id": r.id,
            "strategy": r.strategy_key,
            "symbol": r.symbol,
            "params": r.params,
            "period_days": r.period_days,
            "expected_value": (r.metrics or {}).get("expected_value"),
            "win_rate_pct": (r.metrics or {}).get("win_rate_pct"),
            "total_return_pct": (r.metrics or {}).get("total_return_pct"),
            "is_good": bool(r.is_good),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/account", dependencies=[_guard])
def agent_account(db: Session = Depends(get_db)):
    """查 Alpaca 帳戶（現金 / 購買力 / 組合淨值）。無金鑰 / 連線失敗回 400。"""
    try:
        acc = alpaca_client.get_account()
        _audit(db, "/api/agent/v1/account", None, "ok")
        return {
            "status": str(acc.status),
            "cash": acc.cash,
            "buying_power": acc.buying_power,
            "portfolio_value": acc.portfolio_value,
            "is_paper": settings.IS_PAPER,
        }
    except Exception as e:
        _audit(db, "/api/agent/v1/account", None, "error", str(e))
        raise HTTPException(status_code=400, detail=f"連線 Alpaca 失敗：{e}")


@router.get("/bots", dependencies=[_guard])
def agent_list_bots(db: Session = Depends(get_db)):
    """列出所有 Bot（唯讀：代號 / 策略 / 標的 / 啟用狀態 / paper 還是真錢）。"""
    bots = db.query(Bot).order_by(Bot.id).all()
    _audit(db, "/api/agent/v1/bots", None, "ok")
    return [
        {
            "id": b.id,
            "name": b.name,
            "strategy": b.strategy,
            "symbol": b.symbol,
            "is_active": bool(b.is_active),
            "promotion_status": getattr(b, "promotion_status", None),
        }
        for b in bots
    ]


@router.get("/opportunities", dependencies=[_guard])
def agent_opportunities(limit: int = 50, db: Session = Depends(get_db)):
    """列出常駐探勘機會清單（依 OOS EV 由高到低）。復用 opportunities router 的序列化器。"""
    rows = (
        db.query(Opportunity)
        .order_by(Opportunity.oos_expected_value.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    _audit(db, "/api/agent/v1/opportunities", {"limit": limit}, "ok")
    return [_serialize_opportunity(o) for o in rows]


@router.get("/knowledge", dependencies=[_guard])
def agent_knowledge(limit: int = 50, db: Session = Depends(get_db)):
    """列出策略知識庫（復用 knowledge router 的序列化器）。給 agent 讀已驗證 / 策展過的策略。"""
    rows = db.query(StrategyKnowledge).order_by(StrategyKnowledge.id.desc()).limit(max(1, min(limit, 200))).all()
    _audit(db, "/api/agent/v1/knowledge", {"limit": limit}, "ok")
    return [_serialize_knowledge(k) for k in rows]


# ---------- 唯一寫入端點：下單（預設 paper）----------
class AgentOrderRequest(BaseModel):
    """agent 下單要傳的資料。預設 paper，要碰真錢須伺服端三道閘齊開。"""
    symbol: str
    qty: float
    side: str  # "buy" / "sell"


@router.post("/orders", dependencies=[_guard])
def agent_submit_order(payload: AgentOrderRequest, db: Session = Depends(get_db)):
    """
    送市價單。安全三道閘：
    1. 若連到實盤(真錢) 但 AGENT_LIVE_TRADING_ENABLED=false → 直接拒絕（agent 專屬閘，回 403）。
    2. 即使本閘開了，仍由 alpaca_client.submit_market_order 的實盤雙閘
       （IS_PAPER / ALLOW_LIVE_TRADING）做最終把關——本閘只是「再多一層拒絕」，不繞過雙閘。
    3. 模擬環境（paper）一律放行。
    """
    snapshot = payload.model_dump()
    side = payload.side.lower()
    if side not in ("buy", "sell"):
        _audit(db, "/api/agent/v1/orders", snapshot, "error", "side 只能是 buy / sell")
        raise HTTPException(status_code=400, detail="side 只能是 buy / sell")

    # 第三道閘：真錢環境下，agent 沒被明確授權碰真錢 → 拒絕
    if not settings.IS_PAPER and not settings.AGENT_LIVE_TRADING_ENABLED:
        _audit(db, "/api/agent/v1/orders", snapshot, "rejected", "agent 未獲授權下真錢單")
        raise HTTPException(
            status_code=403,
            detail="目前為實盤環境，但 AGENT_LIVE_TRADING_ENABLED=false：agent 不得下真錢單。",
        )

    try:
        order = alpaca_client.submit_market_order(payload.symbol.upper(), payload.qty, side)
        _audit(db, "/api/agent/v1/orders", snapshot, "ok",
               f"order_id={getattr(order, 'id', None)}")
        return {
            "order_id": str(getattr(order, "id", "")),
            "symbol": payload.symbol.upper(),
            "qty": payload.qty,
            "side": side,
            "is_paper": settings.IS_PAPER,
        }
    except Exception as e:
        _audit(db, "/api/agent/v1/orders", snapshot, "error", str(e))
        raise HTTPException(status_code=400, detail=f"下單失敗：{e}")
