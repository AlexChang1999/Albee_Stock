"""
知識庫策略 → Paper Bot 自動部署排程
=====================================
把「驗證過的好策略」自動部署成 Paper Bot 掛網跑（補 curated 知識庫接不到 Bot 的斷層，
取代手動逐筆 deploy）。每日定時取目標狀態（預設 curated）且還沒部署過的知識，逐筆用**既有**
共用函式 deploy_curated_to_bots 建 Paper Bot。本檔是薄薄一層批次器。

明確界線（防 slop / 防漂移）：
- ★ 只建 **paper** bot（promotion_status="paper"），完全不碰真錢雙閘（ALPACA_BASE_URL 實盤 +
  ALLOW_LIVE_TRADING）。上真錢仍走既有 promotion 流程（人核准 + 雙閘）。
- 預設從 curated 觸發（保留「validated→人晉升 curated」人工閘）；可改 validated（全自動）。
- 冪等：只取 deployed_at IS NULL，建完戳 deployed_at → 同一筆知識永不重複建 Bot。
- 失敗隔離：單筆例外不擋整批、不誤殺（維持原狀、不戳 deployed_at，下批重試）。

設計：run_auto_deploy_knowledge 才碰 DB（仿 auto_validate.run_auto_validate）。
"""

import logging

from backend.config import settings
from backend.database import SessionLocal
from backend.models.strategy_knowledge import StrategyKnowledge
from backend.services.knowledge_deploy import deploy_curated_to_bots

logger = logging.getLogger(__name__)


def run_auto_deploy_knowledge(db=None) -> dict:
    """
    跑一輪自動部署：取 status=AUTO_DEPLOY_FROM_STATUS 且 deployed_at 為空的知識至多
    AUTO_DEPLOY_KNOWLEDGE_MAX_PER_RUN 筆，逐筆部署成 Paper Bot（掛網跑 paper）。

    - AUTO_DEPLOY_KNOWLEDGE_ENABLED=false → 直接 return（排程掛載處也有閘，雙保險）。
    - 冪等：只取 deployed_at IS NULL；建完戳 deployed_at（deploy_curated_to_bots 內處理）。
    - 單筆例外 → 隔離，維持原狀、繼續下一筆。

    :param db: 測試可注入 session；None = 自建（排程入口用）。
    :return: {"processed", "deployed_knowledge", "bots_created", "failed"} 統計。
    """
    stats = {"processed": 0, "deployed_knowledge": 0, "bots_created": 0, "failed": 0}
    if not settings.AUTO_DEPLOY_KNOWLEDGE_ENABLED:
        return stats

    symbols = settings.auto_deploy_knowledge_symbols
    if not symbols:
        logger.warning("自動部署：AUTO_DEPLOY_KNOWLEDGE_SYMBOLS 為空，跳過整輪")
        return stats

    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        rows = (
            db.query(StrategyKnowledge)
            .filter(
                StrategyKnowledge.status == settings.AUTO_DEPLOY_FROM_STATUS,
                StrategyKnowledge.deployed_at.is_(None),
            )
            .order_by(StrategyKnowledge.id)
            .limit(max(1, settings.AUTO_DEPLOY_KNOWLEDGE_MAX_PER_RUN))
            .all()
        )
        for row in rows:
            stats["processed"] += 1
            try:
                created = deploy_curated_to_bots(
                    db, row, symbols,
                    trade_amount=settings.AUTO_DEPLOY_KNOWLEDGE_TRADE_AMOUNT,
                    check_interval_sec=settings.AUTO_DEPLOY_KNOWLEDGE_CHECK_INTERVAL,  # 艦隊降載
                    activate=True,   # 自動部署：建好即啟用，掛網跑 paper
                )
                db.commit()          # 逐筆 commit，防中途斷
                stats["deployed_knowledge"] += 1
                stats["bots_created"] += len(created)
            except Exception as e:
                # 失敗隔離：rollback 該筆（含未戳的 deployed_at），維持原狀下批重試
                db.rollback()
                stats["failed"] += 1
                logger.warning("自動部署：knowledge %s 失敗（維持原狀下批重試）：%s", row.id, e)
                continue
    finally:
        if own_session:
            db.close()

    logger.info(
        "自動部署完成：processed=%s deployed_knowledge=%s bots_created=%s failed=%s",
        stats["processed"], stats["deployed_knowledge"], stats["bots_created"], stats["failed"],
    )
    return stats
