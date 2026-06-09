"""
資料模型（Models）
==================
這裡匯入所有資料表模型，讓 SQLAlchemy 能一次認得它們。
其他地方可以直接 from backend.models import Bot, TradeLog, StrategyPreset, BacktestRun, ...
"""

from backend.models.bot import Bot
from backend.models.trade import TradeLog
from backend.models.strategy_preset import StrategyPreset
from backend.models.backtest_run import BacktestRun
from backend.models.decision_log import DecisionLog
from backend.models.portfolio_state import PortfolioState
from backend.models.strategy_knowledge import StrategyKnowledge
from backend.models.automation_config import AutomationConfig
from backend.models.opportunity import Opportunity
from backend.models.factor_snapshot import FactorSnapshot
from backend.models.raw_strategy_find import RawStrategyFind

__all__ = [
    "Bot",
    "TradeLog",
    "StrategyPreset",
    "BacktestRun",
    "DecisionLog",
    "PortfolioState",
    "StrategyKnowledge",
    "AutomationConfig",
    "Opportunity",
    "FactorSnapshot",
    "RawStrategyFind",
]
