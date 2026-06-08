"""
全自動護欄 API — 模式 B（改版 Phase 4；規則改吃 DB）
========================================
GET  /automation       看目前的自動化規則與名額狀態（總開關、門檻、已用名額…）。
PUT  /automation       編輯自動化規則（只改有帶的欄位；改 scan_hour 會即時重掛排程）。
POST /automation/run   手動觸發一輪自動部署（測試用）。
                       ?dry_run=true 只預覽會部署誰、不真的建；
                       ?force=true   略過「總開關未開」限制（方便沒開 enabled 也能試跑）。

排程器會在盤前自動呼叫 run_auto_deploy（force=False，受總開關控制）；這支 API 讓你不用
等到盤前也能手動驗證整條流程。

規則來源：automation_config 單列表（不再唯讀吃 .env）。.env 的 AUTO_DEPLOY_* 只當第一次
建表時的種子預設值。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Bot
from backend.services.automation import run_auto_deploy
from backend.services.automation_config import get_config, update_config
from backend.bots.bot_manager import bot_manager

router = APIRouter(tags=["Automation"])


class AutomationRulesUpdate(BaseModel):
    """自動化規則的可編輯欄位（全 Optional：只改有帶的）。"""
    enabled: Optional[bool] = None
    ev_threshold: Optional[float] = None
    winrate_threshold: Optional[float] = None
    max_bots: Optional[int] = None
    cash_per_bot: Optional[float] = None
    scan_hour: Optional[int] = None


def _serialize(cfg, active_count: int) -> dict:
    """把規則列 + 名額狀態組成給前端的回傳（鍵名與舊版維持一致，保前端契約）。"""
    return {
        "enabled": cfg.enabled,
        "ev_threshold": cfg.ev_threshold,
        "winrate_threshold": cfg.winrate_threshold,
        "max_bots": cfg.max_bots,
        "cash_per_bot": cfg.cash_per_bot,
        "scan_hour": cfg.scan_hour,
        "active_bots": active_count,
        "slots_left": max(0, cfg.max_bots - active_count),
    }


@router.get("/automation")
def get_automation(db: Session = Depends(get_db)):
    """回傳目前的自動化規則與名額狀態（給前端/使用者檢視）。"""
    cfg = get_config(db)
    active_count = db.query(Bot).filter(Bot.is_active.is_(True)).count()
    return _serialize(cfg, active_count)


@router.put("/automation")
def put_automation(body: AutomationRulesUpdate, db: Session = Depends(get_db)):
    """
    編輯自動化規則。只改「有帶」的欄位（None=不動）。

    改 scan_hour 時即時重掛盤前掃描的 cron job（不必重啟後端）。
    驗證失敗（如 scan_hour 超出 0~23）回 400。
    """
    try:
        cfg, hour_changed = update_config(db, **body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"規則不合法：{e}")

    # scan_hour 有變 → 立即用新時刻重掛 cron（add_job 已 replace_existing=True）
    if hour_changed:
        bot_manager.schedule_auto_deploy(cfg.scan_hour)

    active_count = db.query(Bot).filter(Bot.is_active.is_(True)).count()
    return _serialize(cfg, active_count)


@router.post("/automation/run")
def run_automation(force: bool = False, dry_run: bool = False, db: Session = Depends(get_db)):
    """手動觸發一輪自動部署。預設受總開關控制；force=true 可略過、dry_run=true 只預覽。"""
    try:
        return run_auto_deploy(db, force=force, dry_run=dry_run)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"自動部署失敗：{e}")
