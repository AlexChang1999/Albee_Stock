"""
資料模型（Models）
==================
這裡匯入所有資料表模型，讓 SQLAlchemy 能一次認得它們。
其他地方可以直接 from backend.models import Bot, TradeLog
"""

from backend.models.bot import Bot
from backend.models.trade import TradeLog

__all__ = ["Bot", "TradeLog"]
