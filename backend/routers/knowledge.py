"""
策略知識庫 API ── Phase 8（step-01 CRUD / 02 提案 / 04 驗證 / 05 排行+使用時機 / 06 人在迴路）
================================================================================================
策略知識庫（StrategyKnowledge）是「蒐集 → 整合 → 驗證 → 策展 → 進化」閉環的單一資料來源。

端點分組（依 Phase 8 各 step）：
- step-01 基本 CRUD            ：GET/POST/PUT/DELETE /knowledge
- step-02 LLM 草擬候選參數     ：POST /knowledge/propose（只進候選區，不回測、不部署）
- step-04 自動驗證管線         ：POST /knowledge/{id}/validate（OOS + walk-forward 才判 validated）
- step-05 排行 + 使用時機說明  ：GET /knowledge/ranking、POST /knowledge/{id}/usage-note
- step-06 人在迴路審核         ：POST /knowledge/{id}/promote、POST /knowledge/{id}/reject

鐵則：晉升（validated → curated）只能由人觸發（step-06）；驗證一律看樣本外（step-04）。
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import StrategyKnowledge
from backend.services import explorations, llm, strategy_generator
from backend.services.evolution import validate_candidate
from backend.services.strategy_selector import build_regime_strategy_map

router = APIRouter(tags=["Knowledge"])

# 驗證狀態機允許的狀態值（step-01）
_STATUSES = {"candidate", "validated", "curated", "rejected"}

_NO_LLM_DETAIL = "未設定 LLM（LLM_BASE_URL / LLM_MODEL）。請檢查後端 .env。"
_CLOUD_BLOCKED_DETAIL = (
    "LLM_BASE_URL 指向外部服務，會把策略場景描述送到第三方。預設只允許本機（localhost）。"
    "確定要用雲端供應商，請在後端 .env 設 LLM_ALLOW_CLOUD=true，或改回本機 Ollama。"
)


# ---------- 請求資料格式 ----------
class KnowledgeIn(BaseModel):
    """建立 / 編輯一筆知識的資料。"""
    name: str
    strategy_key: str = "ma_crossover"
    theory: str | None = None
    scenario: str | None = None
    usage_note: str | None = None
    params: dict = {}
    composite_of: list | None = None
    status: str = "candidate"


class ProposeIn(BaseModel):
    """請 LLM 依場景草擬候選參數。"""
    strategy_key: str
    scenario: str
    n: int = 3
    name_prefix: str | None = None  # 候選命名前綴（預設用策略鍵）


class ValidateIn(BaseModel):
    """對某筆候選跑驗證管線時要驗哪檔、回看幾天。"""
    symbol: str = "AAPL"
    days: int = 365


class UsageNoteIn(BaseModel):
    """產生使用時機說明：在哪檔上算狀態親和性。"""
    symbol: str = "AAPL"


class RejectIn(BaseModel):
    """退回某筆候選，附理由（寫進 explorations 記憶）。"""
    reason: str = ""


# ---------- 內部小工具 ----------
def _get_or_404(db: Session, kid: int) -> StrategyKnowledge:
    k = db.query(StrategyKnowledge).filter(StrategyKnowledge.id == kid).first()
    if not k:
        raise HTTPException(status_code=404, detail="找不到這筆策略知識")
    return k


def _dict(k: StrategyKnowledge) -> dict:
    return {
        "id": k.id,
        "name": k.name,
        "strategy_key": k.strategy_key,
        "theory": k.theory,
        "scenario": k.scenario,
        "usage_note": k.usage_note,
        "params": k.params,
        "composite_of": k.composite_of,
        "status": k.status,
        "oos_metrics": k.oos_metrics,
        "regime_affinity": k.regime_affinity,
        "created_at": k.created_at.isoformat() if k.created_at else None,
        "updated_at": k.updated_at.isoformat() if k.updated_at else None,
    }


def _ev_of(k: StrategyKnowledge) -> float:
    """取某筆知識的 OOS EV（排序用）；缺值當 -inf 排最後。"""
    ev = (k.oos_metrics or {}).get("expected_value")
    return ev if isinstance(ev, (int, float)) else float("-inf")


def _llm_client_or_400():
    """建 LLM client，沿用 llm 模組的外送安全閥；缺設定 / 被擋 → 400。"""
    if llm.cloud_blocked():
        raise HTTPException(status_code=400, detail=_CLOUD_BLOCKED_DETAIL)
    client = llm.get_client()
    if client is None:
        raise HTTPException(status_code=400, detail=_NO_LLM_DETAIL)
    return client


# ========== step-01：基本 CRUD ==========
@router.get("/knowledge")
def list_knowledge(status: str | None = None, db: Session = Depends(get_db)):
    """列出知識（可選 status 篩選），新到舊。"""
    q = db.query(StrategyKnowledge)
    if status:
        q = q.filter(StrategyKnowledge.status == status)
    rows = q.order_by(StrategyKnowledge.created_at.desc()).all()
    return [_dict(k) for k in rows]


@router.get("/knowledge/ranking")
def rank_knowledge(status: str = "validated", db: Session = Depends(get_db)):
    """
    策略庫排行（step-05）：依 OOS EV（oos_metrics.expected_value）由高到低排序。
    預設只看已通過驗證（validated）的；可改篩 curated 等。
    （SQLite 對 JSON 欄位排序不便，與 presets 一致改在 Python 端排，資料量小無虞。）
    """
    rows = db.query(StrategyKnowledge).filter(StrategyKnowledge.status == status).all()
    rows.sort(key=_ev_of, reverse=True)
    return [_dict(k) for k in rows]


@router.get("/knowledge/{kid}")
def get_knowledge(kid: int, db: Session = Depends(get_db)):
    """看單筆知識完整內容。"""
    return _dict(_get_or_404(db, kid))


@router.post("/knowledge")
def create_knowledge(payload: KnowledgeIn, db: Session = Depends(get_db)):
    """新增一筆知識（手動建立）。"""
    if payload.status not in _STATUSES:
        raise HTTPException(status_code=400, detail=f"status 必須是 {_STATUSES}")
    k = StrategyKnowledge(
        name=payload.name,
        strategy_key=payload.strategy_key,
        theory=payload.theory,
        scenario=payload.scenario,
        usage_note=payload.usage_note,
        params=payload.params,
        composite_of=payload.composite_of,
        status=payload.status,
    )
    db.add(k)
    db.commit()
    db.refresh(k)
    return _dict(k)


@router.put("/knowledge/{kid}")
def update_knowledge(kid: int, payload: KnowledgeIn, db: Session = Depends(get_db)):
    """編輯一筆知識。"""
    if payload.status not in _STATUSES:
        raise HTTPException(status_code=400, detail=f"status 必須是 {_STATUSES}")
    k = _get_or_404(db, kid)
    k.name = payload.name
    k.strategy_key = payload.strategy_key
    k.theory = payload.theory
    k.scenario = payload.scenario
    k.usage_note = payload.usage_note
    k.params = payload.params
    k.composite_of = payload.composite_of
    k.status = payload.status
    db.commit()
    db.refresh(k)
    return _dict(k)


@router.delete("/knowledge/{kid}")
def delete_knowledge(kid: int, db: Session = Depends(get_db)):
    """刪除一筆知識。"""
    k = _get_or_404(db, kid)
    name = k.name
    db.delete(k)
    db.commit()
    return {"message": f"已刪除策略知識：{name}"}


# ========== step-02：LLM 草擬候選參數 ==========
@router.post("/knowledge/propose")
def propose_knowledge(payload: ProposeIn, db: Session = Depends(get_db)):
    """
    請 LLM 依場景草擬幾組候選參數，每組寫成一筆 status=candidate 的知識。
    **只草擬、不回測、不部署**；非法策略鍵被擋（400）。
    """
    client = _llm_client_or_400()
    try:
        param_sets = strategy_generator.propose_params(
            client, payload.strategy_key, payload.scenario, payload.n
        )
    except ValueError as e:  # 非法策略鍵
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # LLM 連不上等 → 優雅 400
        raise HTTPException(status_code=400, detail=llm.friendly_err(e))

    prefix = payload.name_prefix or payload.strategy_key
    created = []
    for i, params in enumerate(param_sets, start=1):
        k = StrategyKnowledge(
            name=f"{prefix} 候選 #{i}",
            strategy_key=payload.strategy_key,
            scenario=payload.scenario,
            params=params,
            status="candidate",
        )
        db.add(k)
        created.append(k)
    db.commit()
    for k in created:
        db.refresh(k)
    return {"created": [_dict(k) for k in created]}


# ========== step-04：自動驗證管線 ==========
@router.post("/knowledge/{kid}/validate")
def validate_knowledge(kid: int, payload: ValidateIn, db: Session = Depends(get_db)):
    """
    對某筆候選跑驗證管線（含成本回測 + OOS 切分 + walk-forward），
    只有「樣本外真加分」判 validated，否則 rejected。判定鍵讀 OOS / walk-forward，非 in-sample。
    """
    k = _get_or_404(db, kid)
    try:
        summary = validate_candidate(k, payload.symbol, payload.days)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    db.refresh(k)
    return summary


# ========== step-05：使用時機說明（狀態親和性 + LLM） ==========
@router.post("/knowledge/{kid}/usage-note")
def make_usage_note(kid: int, payload: UsageNoteIn, db: Session = Depends(get_db)):
    """
    產生使用時機說明（step-05）：用 Phase 7 的狀態親和性（這策略在哪種市場狀態 OOS 最好）
    ＋ LLM 寫一句白話「何時用」，寫回 usage_note / regime_affinity。
    """
    client = _llm_client_or_400()
    k = _get_or_404(db, kid)

    # 狀態親和性：從 Phase 7「狀態→策略對照表」的完整明細抽出本策略在各狀態的 OOS 表現
    try:
        regime_map = build_regime_strategy_map(payload.symbol)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    affinity = {
        regime: per_strat[k.strategy_key]
        for regime, per_strat in (regime_map.get("stats") or {}).items()
        if k.strategy_key in per_strat
    }
    best_regime = max(affinity, key=lambda r: affinity[r]["ev"]) if affinity else None

    # LLM 寫一句白話使用時機（不長篇大論，一兩句、可執行）
    sys_text = "你是策略策展助手。用繁體中文寫『使用時機』，**只回一到兩句白話**，不要長篇。"
    user_text = (
        f"策略：{k.strategy_key}（{k.name}）\n"
        f"場景描述：{k.scenario or '（無）'}\n"
        f"各市場狀態的樣本外表現（EV/勝率/筆數）：{affinity or '（資料不足）'}\n"
        f"OOS 最佳狀態：{best_regime or '（不明）'}\n\n"
        "請寫一兩句『何時該用這個策略』。"
    )
    try:
        note = llm.complete(
            client,
            [{"role": "system", "content": sys_text},
             {"role": "user", "content": user_text}],
            max_tokens=200,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=llm.friendly_err(e))

    k.usage_note = note
    k.regime_affinity = {"best_regime": best_regime, "by_regime": affinity}
    db.commit()
    db.refresh(k)
    return _dict(k)


# ========== step-06：人在迴路審核 ==========
@router.post("/knowledge/{kid}/promote")
def promote_knowledge(kid: int, db: Session = Depends(get_db)):
    """
    晉升 validated → curated（**只能由人觸發**；系統自動流程到 validated 為止）。
    非 validated 的不准晉升（防跳過驗證直接策展）。理由留檔到 explorations 記憶。
    """
    k = _get_or_404(db, kid)
    if k.status != "validated":
        raise HTTPException(
            status_code=400,
            detail=f"只有 validated 的策略可晉升為 curated（目前 status={k.status}）",
        )
    k.status = "curated"
    db.commit()
    db.refresh(k)
    # 採用理由留檔（可追溯軌跡）
    reason = f"人工晉升為策展庫（curated）。OOS EV={_ev_of(k)}。"
    explorations.write_knowledge_note(k.id, k.strategy_key, "promote", reason)
    return _dict(k)


@router.post("/knowledge/{kid}/reject")
def reject_knowledge(kid: int, payload: RejectIn, db: Session = Depends(get_db)):
    """退回某筆（→ rejected，附理由）；理由寫進 explorations 記憶。"""
    k = _get_or_404(db, kid)
    k.status = "rejected"
    db.commit()
    db.refresh(k)
    reason = payload.reason or "（未填理由）"
    explorations.write_knowledge_note(k.id, k.strategy_key, "reject", reason)
    return _dict(k)
