"""
AI 每日交易事後檢討 API（review.py）
======================================
提供手動觸發「每日 AI 交易分析」的端點，方便在前端或 /docs 直接補跑分析。
自動排程版本由 APScheduler 在美股收盤後（UTC 20:00）每日觸發。
"""

from datetime import date as _date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.trade_review import run_daily_review

router = APIRouter(prefix="/review", tags=["Review"])


@router.post("/daily")
def manual_daily_review(date: str | None = None, db: Session = Depends(get_db)):
    """
    手動觸發 AI 每日交易檢討。

    - date：格式 YYYY-MM-DD，省略時分析昨天。
    - 會讀 DecisionLog + TradeLog → LLM 分析 → 寫 explorations/review-YYYY-MM-DD.md → 推播摘要。
    - LLM 不可用時仍回傳統計彙整（llm_used: false），不報錯。
    """
    target = date or (_date.today() - timedelta(days=1)).isoformat()
    return run_daily_review(target, db)


@router.get("/daily")
def get_daily_review_status(date: str | None = None):
    """
    確認指定日期的 review 檔案是否存在（不重新跑分析）。
    date 省略 = 昨天。
    """
    from pathlib import Path
    from backend.config import settings

    target = date or (_date.today() - timedelta(days=1)).isoformat()
    expl_dir = Path(settings.EXPLORATIONS_DIR) if settings.EXPLORATIONS_DIR else (
        Path(__file__).parents[2] / "explorations"
    )
    filename = f"review-{target}.md"
    exists = (expl_dir / filename).exists()
    return {
        "date": target,
        "file": filename,
        "exists": exists,
        "path": str(expl_dir / filename) if exists else None,
    }
