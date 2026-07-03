"""
向量化引擎對拍測試
==================
核心保證：向量化引擎 run_vectorized 與事件式引擎 _run_on_df 在「同一份資料、同一組參數」
下，算出來的績效必須一致（這是用向量化加速卻不改變結果的底線）。

對每個有向量化版本的策略，各跑一組代表性參數，比對：總報酬、最大回撤、勝率、EV、
交易筆數、最終淨值，以及整條資金曲線。任一不合就 fail。

執行：
    venv\\Scripts\\python.exe -m pytest tests/test_vectorized_engine.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import pytest

from backend.strategies import get_strategy
from backend.services.backtest_engine import _run_on_df
from backend.services.vectorized_engine import run_vectorized, SIGNAL_BUILDERS


def _sample_ohlc(n=150, seed=42):
    """造一段有漲有跌、帶日內高低的 OHLCV，讓各種策略都會觸發訊號。"""
    rs = np.random.RandomState(seed)
    # 隨機漫步 + 一段明顯趨勢，製造交叉/突破/超買超賣等情境
    steps = rs.normal(0.001, 0.02, n)
    steps[n // 3: n // 2] += 0.02   # 中段一波上漲
    steps[2 * n // 3:] -= 0.015     # 後段一波下跌
    close = 100 * np.cumprod(1 + steps)
    high = close * (1 + np.abs(rs.normal(0, 0.005, n)))
    low = close * (1 - np.abs(rs.normal(0, 0.005, n)))
    return pd.DataFrame({
        "timestamp": pd.bdate_range("2023-01-02", periods=n).astype(str),
        "open": close,
        "high": high,
        "low": low,
        "close": close,
        "volume": rs.randint(1_000_000, 5_000_000, n),
    })


# 每個策略一組代表性參數
PARAMS = {
    "ma_crossover": {"short_window": 5, "long_window": 20},
    "rsi": {"period": 14, "oversold": 30, "overbought": 70},
    "macd": {"fast": 12, "slow": 26, "signal": 9},
    "bollinger": {"period": 20, "num_std": 2},
    "donchian": {"period": 20},
    "stochastic": {"k_period": 14, "d_period": 3},
    "momentum": {"period": 10, "threshold": 5},
    "williams_r": {"period": 14},
    "adx_trend": {"period": 14, "adx_threshold": 25},
}

# 要逐一比對的數值欄位
NUMERIC_KEYS = [
    "total_return_pct", "max_drawdown_pct", "win_rate_pct",
    "expected_value", "expectancy_pct", "num_round_trips",
    "num_trades", "final_equity", "num_wins", "num_losses",
]


@pytest.mark.parametrize("strategy_key", list(SIGNAL_BUILDERS.keys()))
def test_vectorized_matches_event(strategy_key):
    df = _sample_ohlc()
    params = PARAMS[strategy_key]

    event = _run_on_df(get_strategy(strategy_key, params), df, 10000.0)
    vec = run_vectorized(strategy_key, params, df, 10000.0)

    for key in NUMERIC_KEYS:
        assert vec[key] == event[key], (
            f"[{strategy_key}] {key} 不一致：向量化 {vec[key]} vs 事件式 {event[key]}"
        )
    # 整條資金曲線也要一致
    assert vec["equity_curve"] == event["equity_curve"], f"[{strategy_key}] 資金曲線不一致"


def test_all_registered_strategies_vectorized():
    """提醒：若有策略沒列進 SIGNAL_BUILDERS，這裡會列出來（optimizer 會退回事件式，不算錯）。"""
    from backend.strategies import STRATEGY_REGISTRY, ScriptStrategy
    # composite（Phase 8 step-03）是「聚合多個子策略」的組合器，本質上無法收成單一向量化 builder，
    # 刻意只走事件式路徑（_run_on_df 內逐根聚合子策略訊號），故豁免此不變式。
    # ScriptStrategy 子類（事件驅動、有狀態 on_bar）整個家族天生走事件式重播，同樣豁免——
    # 用 issubclass 判斷而非手列名單，之後新增 Script 策略不會再漏接這個測試。
    # snr_3_0：多階段序列掃描（swing→爆發→Fresh 計數→拒絕→確認→結構突破），
    # 狀態跨多根、無法收成單一向量化 builder，刻意只走事件式（同 composite 豁免；
    # 且 v1 不進 optimizer PARAM_GRIDS，向量化快路徑本來就用不到）。
    EVENT_ONLY = {"composite", "snr_3_0"} | {
        key for key, cls in STRATEGY_REGISTRY.items() if issubclass(cls, ScriptStrategy)
    }
    missing = set(STRATEGY_REGISTRY) - set(SIGNAL_BUILDERS) - EVENT_ONLY
    # 其餘策略期望全部都有向量化版本
    assert not missing, f"這些策略還沒向量化（會走慢路徑）：{missing}"
