"""
策略套件
========
每個策略一個檔案，都繼承 base.py 的 BaseStrategy。

STRATEGY_REGISTRY 是「策略註冊表」：
用字串代號對應到策略類別，這樣 Bot 只要存代號（例如 "ma_crossover"），
就能找到對應的策略。新增策略時，只要在這裡登記一行即可（鬆耦合）。
"""

from backend.strategies.base import BaseStrategy, Signal
from backend.strategies.ma_crossover import MACrossoverStrategy
from backend.strategies.rsi import RSIStrategy
from backend.strategies.macd import MACDStrategy
from backend.strategies.bollinger import BollingerStrategy
from backend.strategies.donchian import DonchianStrategy
from backend.strategies.stochastic import StochasticStrategy
from backend.strategies.momentum import MomentumStrategy
from backend.strategies.williams_r import WilliamsRStrategy

# 策略註冊表：代號 -> 類別
# 之後新增策略，就在這裡多加一行對應即可。
STRATEGY_REGISTRY = {
    "ma_crossover": MACrossoverStrategy,
    "rsi": RSIStrategy,
    "macd": MACDStrategy,
    "bollinger": BollingerStrategy,
    "donchian": DonchianStrategy,
    "stochastic": StochasticStrategy,
    "momentum": MomentumStrategy,
    "williams_r": WilliamsRStrategy,
}


def get_strategy(name: str, params: dict) -> BaseStrategy:
    """依代號建立對應的策略實例。"""
    if name not in STRATEGY_REGISTRY:
        raise ValueError(f"未知的策略：{name}，可用的有：{list(STRATEGY_REGISTRY.keys())}")
    return STRATEGY_REGISTRY[name](params)


__all__ = ["BaseStrategy", "Signal", "STRATEGY_REGISTRY", "get_strategy"]
