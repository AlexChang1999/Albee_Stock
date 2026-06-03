"""
全自動護欄 API — 模式 B（改版 Phase 4）
========================================
GET  /automation       看目前的自動化規則與名額狀態（總開關、門檻、已用名額…）。
POST /automation/run   手動觸發一輪自動部署（測試用）。
                       ?dry_run=true 只預覽會部署誰、不真的建；
                       ?force=true   略過「總開關未開」限制（方便沒開 enabled 也能試跑）。

排程器會在盤前自動呼叫 run_auto_deploy（force=False，受總開關控制）；這支 API 讓你不用
等到盤前也能手動驗證整條流程。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import Bot
from backend.services.automation import run_auto_deploy

router = APIRouter(tags=["Automation"])


@router.get("/automation")
def get_automation(db: Session = Depends(get_db)):
    """回傳目前的自動化規則與名額狀態（給前端/使用者檢視）。"""
    active_count = db.query(Bot).filter(Bot.is_active.is_(True)).count()
    return {
        "enabled": settings.AUTO_DEPLOY_ENABLED,
        "ev_threshold": settings.AUTO_DEPLOY_EV_THRESHOLD,
        "winrate_threshold": settings.AUTO_DEPLOY_WINRATE_THRESHOLD,
        "max_bots": settings.AUTO_DEPLOY_MAX_BOTS,
        "cash_per_bot": settings.AUTO_DEPLOY_CASH_PER_BOT,
        "scan_hour": settings.AUTO_DEPLOY_HOUR,
        "active_bots": active_count,
        "slots_left": max(0, settings.AUTO_DEPLOY_MAX_BOTS - active_count),
    }


@router.post("/automation/run")
def run_automation(force: bool = False, dry_run: bool = False, db: Session = Depends(get_db)):
    """手動觸發一輪自動部署。預設受總開關控制；force=true 可略過、dry_run=true 只預覽。"""
    try:
        return run_auto_deploy(db, force=force, dry_run=dry_run)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"自動部署失敗：{e}")
