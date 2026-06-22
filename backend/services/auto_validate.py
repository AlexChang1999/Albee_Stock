"""
候選自動批次驗證 — OOS 閘排程化（Phase 12 step-03）
====================================================
把「人逐筆按 POST /knowledge/{id}/validate」自動化：每日定時取知識庫 status=candidate
的策略至多 AUTO_VALIDATE_BATCH_SIZE 筆，逐筆呼叫**既有** evolution.validate_candidate
（含成本回測 + walk-forward OOS + is_layer_worth_it verdict），結果自然流轉
validated / rejected。本檔是薄薄一層批次器，**判準零修改**。

明確界線（防 slop / 防漂移）：
- 通過門檻全在 evolution / validation 既有程式，本檔只做排程取批與失敗隔離。
- 不自動晉升 curated（人在迴路鐵則：validated → curated 只能由人按）。
- 驗證資料走 validate_candidate 內的 market_data.get_bars（鐵則：回測=實盤同資料源）。
- 驗證標的統一用籃子 settings.auto_validate_symbols（跨產業池化；candidate 無自帶 symbol，
  同一基準各候選才可比）。籃子留空時退回單檔 AUTO_VALIDATE_SYMBOL（向後相容）。

失敗隔離（單筆炸不擋整批、不放行也不誤殺）：
- 單筆例外（資料抓不到 / 回測例外）→ 失敗計數 +1、維持 candidate、繼續下一筆，下批重試。
- 連續 _MAX_FAILURES 次失敗才標 rejected（操作性放棄，非策略不好）。
- 失敗計數記在 oos_metrics["auto_validate"]（免遷移）；validate_candidate 成功時會
  整顆覆蓋 oos_metrics → 計數自然歸零。
- 兩種 rejected 可稽核區分：evolution 判的含 "verdict"/"walk_forward" 鍵；
  本檔 3 次放棄的只含 "auto_validate"（內含 rejected_by/rejected_at）。

設計：record_validation_failure 是純函式（好測）；run_auto_validate 才碰 DB（仿 discovery.py）。
"""

import logging
from datetime import datetime

from backend.config import settings
from backend.database import SessionLocal
from backend.models.strategy_knowledge import StrategyKnowledge
from backend.services import evolution

logger = logging.getLogger(__name__)

# 連續失敗達此數才標 rejected（之前都維持 candidate 下批重試，不誤殺）
_MAX_FAILURES = 3


def record_validation_failure(row, error_msg: str) -> bool:
    """
    把一次驗證失敗記進 row.oos_metrics["auto_validate"]（純函式，不碰 DB）。

    ★ JSON 欄位陷阱：Column(JSON) 沒掛 MutableDict，就地 mutate 不會被 SQLAlchemy
    偵測到、不會持久化——這裡一律**重建 dict 後重新賦值**。

    :return: True = 本次達 _MAX_FAILURES、已把 row 標 rejected（操作性放棄）。
    """
    prev = ((row.oos_metrics or {}).get("auto_validate") or {})
    failures = int(prev.get("failures", 0)) + 1
    info = {"failures": failures, "last_error": str(error_msg)[:300]}
    if failures >= _MAX_FAILURES:
        # 操作性放棄：與 evolution 的 verdict-reject 區分（這裡沒有 "verdict" 鍵），
        # step-05 算 OOS 通過率時分母要排除 rejected_by=auto_validate 的列
        row.status = "rejected"
        info["rejected_by"] = "auto_validate"
        info["rejected_at"] = datetime.now().isoformat(timespec="seconds")
    row.oos_metrics = {"auto_validate": info}
    return failures >= _MAX_FAILURES


def run_auto_validate(db=None, force: bool = False) -> dict:
    """
    跑一輪自動驗證：取 status=candidate 的知識至多 AUTO_VALIDATE_BATCH_SIZE 筆，
    逐筆送既有 OOS 閘（evolution.validate_candidate，判準零修改）。

    - AUTO_VALIDATE_ENABLED=false 且 force=False → 直接 return（排程掛載處也有閘，雙保險）。
      手動「跑一次」端點傳 force=True 略過此旗標；判準（38 籃子 walk-forward）一字不改。
    - 單筆例外 → 記失敗計數、維持 candidate、繼續下一筆（連續 3 次才 rejected）。
    - 冪等：只取 status=candidate，已 validated/rejected 的永不重驗。

    :param db: 測試可注入 session；None = 自建（排程入口用）。
    :param force: True = 略過 AUTO_VALIDATE_ENABLED 旗標（人工手動觸發用），判準不變。
    :return: {"processed", "validated", "rejected", "failed"} 統計。
    """
    stats = {"processed": 0, "validated": 0, "rejected": 0, "failed": 0}
    if not settings.AUTO_VALIDATE_ENABLED and not force:
        return stats

    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        rows = (
            db.query(StrategyKnowledge)
            .filter(StrategyKnowledge.status == "candidate")
            .order_by(StrategyKnowledge.id)
            .limit(max(1, settings.AUTO_VALIDATE_BATCH_SIZE))
            .all()
        )
        for row in rows:
            stats["processed"] += 1
            try:
                result = evolution.validate_candidate(
                    row, settings.auto_validate_symbols, days=settings.AUTO_VALIDATE_DAYS
                )
            except Exception as e:
                # 失敗隔離：這筆炸（資料抓不到 / 回測例外）不擋整批
                stats["failed"] += 1
                if record_validation_failure(row, str(e)):
                    stats["rejected"] += 1
                    logger.warning(
                        "自動驗證：knowledge %s 連續失敗 %s 次，標 rejected（操作性放棄）：%s",
                        row.id, _MAX_FAILURES, e,
                    )
                else:
                    logger.warning("自動驗證：knowledge %s 本次失敗（維持 candidate 下批重試）：%s", row.id, e)
                continue

            if result.get("status") == "validated":
                stats["validated"] += 1
            else:
                stats["rejected"] += 1

        db.commit()
    finally:
        if own_session:
            db.close()

    logger.info(
        "自動驗證完成：processed=%s validated=%s rejected=%s failed=%s",
        stats["processed"], stats["validated"], stats["rejected"], stats["failed"],
    )
    return stats
