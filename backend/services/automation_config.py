"""
自動部署規則的存取服務（load-or-seed + 驗證更新）
==================================================
集中「讀/寫 automation_config 單列表」的邏輯，讓 router 與 automation 服務都走這裡，
不各自拼 query。規則改吃 DB 後，這裡是唯一的存取入口。

- get_config(db)：拿規則列；查不到就用 .env 的 AUTO_DEPLOY_* 預設「種」一筆（防呆）。
- update_config(db, **fields)：只改有帶的欄位、做基本驗證，回傳更新後的列 +「scan_hour 有沒有變」
  （router 用來決定要不要即時重掛排程 cron）。
"""

from backend.config import settings
from backend.models import AutomationConfig

# 可被更新的欄位白名單（防止外部塞奇怪的 key 進來）
EDITABLE_FIELDS = (
    "enabled",
    "ev_threshold",
    "winrate_threshold",
    "max_bots",
    "cash_per_bot",
    "scan_hour",
    "scan_interval_min",
)


def get_config(db) -> AutomationConfig:
    """
    取得自動部署規則（固定 id=1 那一列）。

    正常情況下 Alembic 遷移已經種好一筆；查不到（例如舊 DB / 測試用的空 DB）時，
    用 .env 的 AUTO_DEPLOY_* 預設值現場建一筆並 commit，確保呼叫端永遠拿得到規則。
    """
    cfg = db.query(AutomationConfig).filter(AutomationConfig.id == 1).first()
    if cfg is None:
        cfg = AutomationConfig(
            id=1,
            enabled=settings.AUTO_DEPLOY_ENABLED,
            ev_threshold=settings.AUTO_DEPLOY_EV_THRESHOLD,
            winrate_threshold=settings.AUTO_DEPLOY_WINRATE_THRESHOLD,
            max_bots=settings.AUTO_DEPLOY_MAX_BOTS,
            cash_per_bot=settings.AUTO_DEPLOY_CASH_PER_BOT,
            scan_hour=settings.AUTO_DEPLOY_HOUR,
            scan_interval_min=settings.SCAN_INTERVAL_MIN,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def _validate(field: str, value):
    """單一欄位的型別與範圍驗證；不合法丟 ValueError（router 轉 400）。"""
    if field == "enabled":
        return bool(value)
    if field == "scan_hour":
        v = int(value)
        if not (0 <= v <= 23):
            raise ValueError("scan_hour 必須介於 0~23（24 小時制的「時」）")
        return v
    if field == "max_bots":
        v = int(value)
        if v < 1:
            raise ValueError("max_bots 至少為 1")
        return v
    if field == "scan_interval_min":
        v = int(value)
        if v < 0:
            raise ValueError("scan_interval_min 不能為負數（0 = 關掉常駐掃描）")
        return v
    if field == "winrate_threshold":
        v = float(value)
        if not (0 <= v <= 100):
            raise ValueError("winrate_threshold 必須介於 0~100（百分比）")
        return v
    if field in ("ev_threshold", "cash_per_bot"):
        v = float(value)
        if v < 0:
            raise ValueError(f"{field} 不能為負數")
        return v
    raise ValueError(f"未知的欄位：{field}")


def update_config(db, **fields) -> tuple[AutomationConfig, bool]:
    """
    更新規則：只改「有帶」且在白名單內的欄位（None 視為沒帶、不動）。

    :return: (更新後的 AutomationConfig, scan_hour 是否有變)
             scan_hour 有變時，呼叫端應即時重掛排程 cron（不必重啟後端）。
    """
    cfg = get_config(db)
    hour_changed = False
    for field, value in fields.items():
        if field not in EDITABLE_FIELDS or value is None:
            continue
        clean = _validate(field, value)
        if field == "scan_hour" and clean != cfg.scan_hour:
            hour_changed = True
        setattr(cfg, field, clean)
    db.commit()
    db.refresh(cfg)
    return cfg, hour_changed
