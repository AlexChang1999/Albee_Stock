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
from backend.strategies.composite import CompositeStrategy

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
    # Phase 8 step-03：策略組合（子策略訊號投票 / 加權 / 狀態切換）
    "composite": CompositeStrategy,
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
    "composite": "策略組合",
}

# 策略「合法參數 schema」：代號 -> {參數名: {default, min, max}}。
# Phase 12 修品質漏洞用——這是「哪些參數名合法 + 合理範圍」的單一真相來源：
#   1) 探勘橋 / 策略生成器把它塞進 LLM prompt，叫模型「只准用這些參數名、值落範圍內」；
#   2) triage_find 收到提案後，用它驗「參數名是否合法」，擋掉亂猜的名字（如 short_ma）。
# 為何重要：策略 generate_signal 用 params.get("名", 預設) 讀參數，遇到不認識的鍵會「靜默
# 回退預設值」不報錯——LLM 若猜錯名（short_ma vs short_window），回測其實跑的是預設參數，
# OOS 測到的根本不是提案策略。集中宣告在此（與 STRATEGY_LABELS 同處），杜絕多處手寫漂移。
# default 必須與各策略檔 generate_signal 裡的 params.get(..., 預設) 一致；min/max 是建議範圍。
# composite 不列（沒有可草擬的扁平參數 schema，探勘橋本就排除它）。
STRATEGY_PARAM_SPECS: dict[str, dict[str, dict]] = {
    "ma_crossover": {
        "short_window": {"default": 5, "min": 2, "max": 100},
        "long_window": {"default": 20, "min": 5, "max": 300},
    },
    "rsi": {
        "period": {"default": 14, "min": 2, "max": 100},
        "overbought": {"default": 70, "min": 50, "max": 95},
        "oversold": {"default": 30, "min": 5, "max": 50},
    },
    "macd": {
        "fast": {"default": 12, "min": 2, "max": 50},
        "slow": {"default": 26, "min": 5, "max": 100},
        "signal": {"default": 9, "min": 2, "max": 50},
    },
    "bollinger": {
        "period": {"default": 20, "min": 5, "max": 100},
        "num_std": {"default": 2, "min": 1, "max": 4},
    },
    "donchian": {
        "period": {"default": 20, "min": 5, "max": 200},
    },
    "stochastic": {
        "k_period": {"default": 14, "min": 2, "max": 50},
        "d_period": {"default": 3, "min": 1, "max": 20},
    },
    "momentum": {
        "period": {"default": 10, "min": 2, "max": 100},
        "threshold": {"default": 5, "min": 0.5, "max": 30},  # 百分比門檻
    },
    "williams_r": {
        "period": {"default": 14, "min": 2, "max": 100},
        "overbought": {"default": -20, "min": -50, "max": -1},
        "oversold": {"default": -80, "min": -99, "max": -50},
    },
    "adx_trend": {
        "period": {"default": 14, "min": 2, "max": 50},
        "adx_threshold": {"default": 25, "min": 10, "max": 50},
    },
}


def param_spec(name: str) -> dict[str, dict]:
    """回傳某策略的合法參數 schema（{參數名: {default,min,max}}）。

    沒登記 schema 的策略（如 composite）回空 dict——呼叫端據此判定「不接受任何提案參數」。
    """
    return STRATEGY_PARAM_SPECS.get(name, {})


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
    "STRATEGY_PARAM_SPECS",
    "param_spec",
    "get_strategy",
    "list_strategies",
]
