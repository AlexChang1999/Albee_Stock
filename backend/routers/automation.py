"""
全局自動化規則 API（模式 B 自動駕駛）── Phase 4
=================================================
讓前端能：
  - GET  /automation/rules     讀目前模式 B 的規則設定與「是否正在跑」
  - POST /automation/scan-now  立刻手動觸發一輪海選＋自動部署（force=True）
  - POST /automation/toggle    執行階段開/關週期掃描（不改 .env，重啟後仍以 .env 為準）

設計說明：
  規則「來源真相」是 .env（config.settings），預設全關、保守。這裡的 toggle 只動
  「記憶體裡的排程器」——方便當下試開試關，不會偷改設定檔；後端重啟後是否啟動，
  仍由 AUTO_PILOT_ENABLED 決定。這樣保留「預設安全、要明確開啟」的精神。
"""

from fastapi import APIRouter, HTTPException

from backend.config import settings
from backend.bots.bot_manager import bot_manager
from backend.services import autopilot

router = APIRouter(prefix="/automation", tags=["Automation"])


@router.get("/rules")
def get_rules():
    """讀模式 B 規則設定，附帶「目前週期掃描是否在跑」。"""
    rules = autopilot.get_rules()
    rules["running"] = bot_manager.is_autopilot_running()
    return rules


@router.post("/scan-now")
def scan_now():
    """
    立刻手動跑一輪自動駕駛（force=True：就算總開關沒開也乾跑一次）。

    注意：force=True 仍會「實際部署」達標的 Bot（這就是手動觸發的用途）。
    真正下單仍受實盤雙閘安全閥保護，沒開實盤就只在 Paper 模擬。
    """
    try:
        return autopilot.run_autopilot_scan(force=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"自動掃描失敗：{e}")


@router.post("/toggle")
def toggle(enable: bool):
    """
    執行階段開/關週期掃描（不改 .env）。

    :param enable: True=啟動週期掃描；False=停止。
    開啟時用 .env 設定的 AUTO_PILOT_INTERVAL_SEC 當頻率。
    """
    if enable:
        bot_manager.start_autopilot(settings.AUTO_PILOT_INTERVAL_SEC)
    else:
        bot_manager.stop_autopilot()
    return {
        "running": bot_manager.is_autopilot_running(),
        "interval_sec": settings.AUTO_PILOT_INTERVAL_SEC,
    }
