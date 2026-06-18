"""
開機補跑 + 每日 job 同日防重複（維運安全軌）
=============================================
家用電腦不是 24/7：排程器（APScheduler）活在後端行程裡，
早上 7/8 點電腦沒開機，discovery / auto_validate 等每日管線那天就整段跳過。

本檔提供兩件事：

1. **同日防重複**（make_daily_idempotent）：
   每個每日 job 跑成功就在 job_run_log 落一筆「今天跑過了」。
   cron 正常觸發與開機補跑共用同一張表判斷 → 同 job 同一天最多實際執行一次。
   **只記成功**：失敗不落紀錄，當天稍後的 cron 或下次開機自然重試。

2. **開機補跑**（run_catchup）：
   後端啟動時依管線順序檢查每個每日 job——「開關有開 + 排定時刻已過 + 今天還沒跑」
   就立刻補跑。電腦不管幾點開、開多久，當天管線照走。
   一步失敗不中斷後續（discovery 掛掉不影響 auto_validate 驗舊候選）。

不放大任何權限：補跑的每個 job 都受它自己原本的 enable 閘控制
（DISCOVERY_ENABLED / AUTO_VALIDATE_ENABLED…），這裡只解決「時間到沒開機」。
"""

from datetime import datetime

from backend.config import settings
from backend.database import SessionLocal
from backend.models import JobRunLog


def _today(now: datetime | None = None) -> str:
    """本機日期字串（"YYYY-MM-DD"），job_run_log 的比對鍵。"""
    return (now or datetime.now()).strftime("%Y-%m-%d")


def has_run_today(db, job_name: str, now: datetime | None = None) -> bool:
    """某 job 今天是否已成功跑過（只看成功紀錄——失敗不落表）。"""
    return (
        db.query(JobRunLog)
        .filter(JobRunLog.job_name == job_name, JobRunLog.run_date == _today(now))
        .first()
        is not None
    )


def record_run(db, job_name: str, detail: str | None = None, now: datetime | None = None) -> None:
    """記一筆成功跑次。"""
    db.add(JobRunLog(
        job_name=job_name,
        run_date=_today(now),
        ran_at=now or datetime.now(),
        detail=detail,
    ))
    db.commit()


def make_daily_idempotent(job_name: str, fn):
    """
    把一個每日 job 函式包成「同日只實際執行一次」的版本。

    - 今天已成功跑過 → 直接跳過（回 None）。
    - 沒跑過 → 執行；成功才落紀錄。fn 拋例外就讓它往上拋（不落紀錄 → 可重試），
      APScheduler 會把例外記進 log、job 本身不會被移除。
    """
    def _wrapped(*args, **kwargs):
        db = SessionLocal()
        try:
            if has_run_today(db, job_name):
                print(f"⏭️  [{job_name}] 今天已成功跑過，跳過（同日防重複）")
                return None
        finally:
            db.close()

        result = fn(*args, **kwargs)

        db = SessionLocal()
        try:
            # 摘要截短存 detail（如 discovery 回傳的統計 dict），方便事後查「那天跑出什麼」
            record_run(db, job_name, detail=None if result is None else str(result)[:300])
        finally:
            db.close()
        return result

    _wrapped.__name__ = f"daily_{job_name}"
    return _wrapped


def _daily_steps():
    """
    可補跑的每日 job 清單，**依管線順序**：
    探勘橋（產候選）→ 自動驗證（候選過 OOS 閘）→ 知識庫自動部署 Paper Bot（驗過的掛網跑）
    → 領導股回測（落每日紀錄）→ 心跳日報（排在驗證後，日報才含今天剛 validated 的待審數）
    → tracking 對帳。

    刻意排除：
    - auto_deploy（screener 版）：「盤前」自動部署，補跑到盤中語義就變了，不碰。
      （知識庫版 auto_deploy_knowledge 只建 paper bot、與盤前盤中無關，補跑安全 → 納入。）
    - opportunity_scan / deadman_ping / collector_scan：interval job，開機後自己會跑
      （collector 另在 run_catchup 開頭先收一輪料，讓 discovery 有新素材）。

    延遲 import：避免循環依賴（tracking 反過來用 bot_manager，bot_manager 用本檔）。
    """
    from backend.services.discovery import run_discovery_batch
    from backend.services.auto_validate import run_auto_validate
    from backend.services.auto_deploy_knowledge import run_auto_deploy_knowledge
    from backend.services.daily_watch import run_leader_backtest
    from backend.services.heartbeat import run_daily_heartbeat
    from backend.services.tracking import run_tracking_check

    return [
        # (job 名（沿用排程器 job id）, enable 閘, 每日排定時刻, 函式)
        ("discovery_bridge", settings.DISCOVERY_ENABLED, settings.DISCOVERY_HOUR, run_discovery_batch),
        ("auto_validate", settings.AUTO_VALIDATE_ENABLED, settings.AUTO_VALIDATE_HOUR, run_auto_validate),
        ("auto_deploy_knowledge", settings.AUTO_DEPLOY_KNOWLEDGE_ENABLED, settings.AUTO_DEPLOY_KNOWLEDGE_HOUR, run_auto_deploy_knowledge),
        ("leader_backtest", settings.LEADER_BACKTEST_ENABLED, settings.LEADER_BACKTEST_HOUR, run_leader_backtest),
        ("heartbeat_daily", True, settings.HEARTBEAT_HOUR, run_daily_heartbeat),
        ("tracking_check", True, settings.TRACKING_CHECK_HOUR, run_tracking_check),
    ]


def run_catchup(now: datetime | None = None) -> dict:
    """
    開機補跑主流程（後端啟動時由排程器以一次性 job 呼叫，不擋 FastAPI 啟動）。

    :param now: 測試注入用的「現在」；正式跑留 None。
    :return: 各 job 的處置摘要 {job_name: ran/already_ran/not_due/disabled/failed: ...}
    """
    if not settings.CATCHUP_ON_BOOT:
        return {"skipped": "CATCHUP_ON_BOOT=false"}
    now = now or datetime.now()
    summary: dict[str, str] = {}

    # 0) 先收一輪料：collector 是 interval job，開機後要等滿一個間隔才首跑；
    #    這裡先跑一次，讓接下來補跑的 discovery 吃得到今天的新素材。
    #    （collector 按 source_url 去重，重複跑安全。）
    if settings.COLLECTOR_INTERVAL_MIN > 0:
        from backend.services.collector import run_collector_scan
        try:
            run_collector_scan()
            summary["collector_scan"] = "ran"
        except Exception as e:  # 斷網等情況：不影響後續補跑
            summary["collector_scan"] = f"failed: {e}"
    else:
        summary["collector_scan"] = "disabled"

    # 1) 每日 job 依序補跑
    for job_name, enabled, hour, fn in _daily_steps():
        if not enabled:
            summary[job_name] = "disabled"
            continue
        if now.hour < hour:
            summary[job_name] = "not_due"  # 時刻未到：當天 cron 會正常觸發，不搶跑
            continue
        db = SessionLocal()
        try:
            already = has_run_today(db, job_name, now)
        finally:
            db.close()
        if already:
            summary[job_name] = "already_ran"
            continue
        try:
            make_daily_idempotent(job_name, fn)()
            summary[job_name] = "ran"
        except Exception as e:
            # 一步失敗不中斷後續；不落紀錄 → 當天稍後 cron / 下次開機自然重試
            summary[job_name] = f"failed: {e}"

    print(f"🩹 開機補跑完成：{summary}")
    return summary
