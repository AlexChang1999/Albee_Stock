"""
探勘管線手動觸發 API（Phase 14）
=================================
給「公司戰情頁」每個 AI 角色一顆「跑一次」鈕，把原本只有排程（且預設關）的探勘流水線
變成人可以**逐關手動推進**（擬人操作）：

- POST /discovery/run            ：探勘橋跑一次（raw new → candidate）。
- POST /discovery/triage/{id}    ：對單筆收件匣素材即時試轉策略（CollectorPage 逐篇鈕）。
- POST /discovery/validate-batch ：自動驗證跑一次（candidate → validated/rejected，38 籃子）。
- POST /discovery/auto-deploy    ：自動部署跑一次（curated 門檻及以上 → 各標的 paper bot）。

定位：薄薄一層觸發器。真正邏輯全在 services（discovery / auto_validate / auto_deploy_knowledge），
這裡只用 force=True 略過 *_ENABLED 旗標，**其餘安全閘一律保留**：
- LLM 外送閘（llm.cloud_blocked）——素材 / 場景不外送雲端。
- 驗證判準零修改（evolution 的 38 籃子 walk-forward OOS）。
- 部署只建 paper bot，不碰真錢雙閘。
排程旗標（DISCOVERY_ENABLED 等）維持預設關；本路由不改任何設定。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import RawStrategyFind
from backend.services import discovery, llm
from backend.services.auto_deploy_knowledge import run_auto_deploy_knowledge
from backend.services.auto_validate import run_auto_validate

router = APIRouter(prefix="/discovery", tags=["Discovery"])

_NO_LLM_DETAIL = "未設定 LLM（LLM_BASE_URL / LLM_MODEL）。請檢查後端 .env。"
_CLOUD_BLOCKED_DETAIL = (
    "LLM_BASE_URL 指向外部服務，會把收件匣素材送到第三方。預設只允許本機（localhost）。"
    "確定要用雲端供應商，請在後端 .env 設 LLM_ALLOW_CLOUD=true，或改回本機 Ollama。"
)


def _llm_client_or_400():
    """建 LLM client，沿用 llm 模組的外送安全閥；缺設定 / 被擋 → 400（同 knowledge 體例）。"""
    if llm.cloud_blocked():
        raise HTTPException(status_code=400, detail=_CLOUD_BLOCKED_DETAIL)
    client = llm.get_client()
    if client is None:
        raise HTTPException(status_code=400, detail=_NO_LLM_DETAIL)
    return client


@router.post("/run")
def run_discovery(db: Session = Depends(get_db)):
    """
    探勘橋跑一次：取收件匣 status=new 的素材，LLM 判讀成既有策略候選（force 略過排程旗標）。

    回 {"processed", "built", "discarded", "skipped"}。LLM 沒設定 / 指向雲端未開閘時，
    服務內部整批跳過（skipped），不誤殺素材。
    """
    return discovery.run_discovery_batch(db, force=True)


@router.post("/triage/{find_id}")
def triage_one_find(find_id: int, db: Session = Depends(get_db)):
    """
    對單筆收件匣素材即時「試轉策略」（給 CollectorPage 逐篇鈕用）。

    走與批次同一支 discovery.triage_one（防幻覺約束一致：只准既有策略 + 參數鎖 schema）。
    成功 → 建 candidate、find 標 built；失敗 → find 標 discarded（理由落 triage_note）。
    回 {"status", "knowledge_id", "note", "proposal"}。
    """
    find = db.query(RawStrategyFind).filter(RawStrategyFind.id == find_id).first()
    if find is None:
        raise HTTPException(status_code=404, detail="找不到這筆素材")
    if find.status not in ("new", "triaged"):
        raise HTTPException(
            status_code=400,
            detail=f"只有 new/triaged 的素材可試轉（目前 status={find.status}）",
        )
    client = _llm_client_or_400()
    result = discovery.triage_one(db, find, client)
    db.commit()
    return result


@router.post("/validate-batch")
def run_validate_batch(db: Session = Depends(get_db)):
    """
    自動驗證跑一次：取知識庫 status=candidate，逐筆送既有 OOS 閘（38 籃子 walk-forward）。
    判準零修改，只是 force 略過排程旗標。回 {"processed", "validated", "rejected", "failed"}。
    """
    return run_auto_validate(db, force=True)


@router.post("/auto-deploy")
def run_auto_deploy(db: Session = Depends(get_db)):
    """
    自動部署跑一次：把 curated（門檻及以上）且未部署過的知識，部署成各標的 paper bot。
    ★只建 paper bot，不碰真錢雙閘。回 {"processed", "deployed_knowledge", "bots_created", "failed"}。
    """
    return run_auto_deploy_knowledge(db, force=True)
