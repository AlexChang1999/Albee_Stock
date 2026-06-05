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
from backend.strategies.adx_trend import ADXTrendStrategy

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
    "adx_trend": ADXTrendStrategy,
}

# 策略顯示名（中文）：代號 -> 給人看的名稱。
# Phase 6 step-10：把「顯示名」收成單一來源，由 GET /strategies 對外曝露，
# 讓前端清單能改由後端載入（或靠測試斷言前後端一致），消除「多處手動同步」的漂移。
STRATEGY_LABELS = {
    "ma_crossover": "均線交叉",
    "rsi": "RSI",
    "macd": "MACD",
    "bollinger": "布林通道",
    "donchian": "唐奇安通道突破",
    "stochastic": "KD 隨機指標",
    "momentum": "動量",
    "williams_r": "威廉指標",
    "adx_trend": "ADX 趨勢",
}


def get_strategy(name: str, params: dict) -> BaseStrategy:
    """依代號建立對應的策略實例。"""
    if name not in STRATEGY_REGISTRY:
        raise ValueError(f"未知的策略：{name}，可用的有：{list(STRATEGY_REGISTRY.keys())}")
    return STRATEGY_REGISTRY[name](params)


def list_strategies() -> list[dict]:
    """回傳策略清單 [{value, label}, ...]（依註冊表順序）。

    value = 策略代號（後端唯一識別 / Bot.strategy 存的值）；
    label = 中文顯示名（沒登記 label 的就退回用代號，避免漏列）。
    """
    return [
        {"value": key, "label": STRATEGY_LABELS.get(key, key)}
        for key in STRATEGY_REGISTRY
    ]


__all__ = [
    "BaseStrategy",
    "Signal",
    "STRATEGY_REGISTRY",
    "STRATEGY_LABELS",
    "get_strategy",
    "list_strategies",
]
