"""
策略單元測試
============
用「假資料」測試均線交叉策略的判斷邏輯對不對。
重點：這些測試完全不需要連線 Alpaca，純測演算法。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe tests\\test_strategies.py
或用 pytest：
    venv\\Scripts\\python.exe -m pytest tests/
"""

import sys
from pathlib import Path

# Windows 主控台 cp950 印 emoji 會崩潰，強制改 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 讓測試能 import 到 backend（把專案根目錄加進搜尋路徑）
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from backend.strategies.ma_crossover import MACrossoverStrategy
from backend.strategies.rsi import RSIStrategy
from backend.strategies.macd import MACDStrategy
from backend.strategies.bollinger import BollingerStrategy
from backend.strategies.donchian import DonchianStrategy
from backend.strategies.stochastic import StochasticStrategy
from backend.strategies.momentum import MomentumStrategy
from backend.strategies.base import Signal

# 用小參數 short=2, long=3，方便精確構造交叉情境
PARAMS = {"short_window": 2, "long_window": 3}


def test_golden_cross_should_buy():
    """短均線向上穿越長均線 → 應該回傳 buy。"""
    # 設計：最後一根大漲，使 2 日均線從長均線下方穿到上方
    df = pd.DataFrame({"close": [10, 10, 10, 9, 12]})
    strategy = MACrossoverStrategy(PARAMS)
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.BUY, f"預期 buy，實際 {signal}（{reason}）"
    print(f"✅ 黃金交叉測試通過：{reason}")


def test_death_cross_should_sell():
    """短均線向下穿越長均線 → 應該回傳 sell。"""
    df = pd.DataFrame({"close": [10, 10, 10, 13, 5]})
    strategy = MACrossoverStrategy(PARAMS)
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.SELL, f"預期 sell，實際 {signal}（{reason}）"
    print(f"✅ 死亡交叉測試通過：{reason}")


def test_not_enough_data_should_hold():
    """資料筆數不足 → 應該觀望(hold)。"""
    df = pd.DataFrame({"close": [10, 10]})
    strategy = MACrossoverStrategy(PARAMS)
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.HOLD, f"預期 hold，實際 {signal}（{reason}）"
    print(f"✅ 資料不足測試通過：{reason}")


def test_no_cross_should_hold():
    """價格平穩、沒有交叉 → 應該觀望(hold)。"""
    df = pd.DataFrame({"close": [10, 10, 10, 10, 10]})
    strategy = MACrossoverStrategy(PARAMS)
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.HOLD, f"預期 hold，實際 {signal}（{reason}）"
    print(f"✅ 無交叉測試通過：{reason}")


# ============================================================
# RSI 策略測試
# ============================================================
def test_rsi_oversold_should_buy():
    """連續下跌 → RSI 很低（超賣）→ 應該 buy。"""
    # 從 100 一路跌到 85，共 16 筆，RSI 會接近 0
    df = pd.DataFrame({"close": list(range(100, 84, -1))})
    strategy = RSIStrategy({"period": 14})
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.BUY, f"預期 buy，實際 {signal}（{reason}）"
    print(f"✅ RSI 超賣測試通過：{reason}")


def test_rsi_overbought_should_sell():
    """連續上漲 → RSI 很高（超買）→ 應該 sell。"""
    df = pd.DataFrame({"close": list(range(85, 101))})
    strategy = RSIStrategy({"period": 14})
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.SELL, f"預期 sell，實際 {signal}（{reason}）"
    print(f"✅ RSI 超買測試通過：{reason}")


# ============================================================
# MACD 策略測試
# ============================================================
def test_macd_golden_cross_should_buy():
    """前段持平、最後一根大漲 → MACD 上穿訊號線 → 應該 buy。"""
    df = pd.DataFrame({"close": [100] * 34 + [120]})
    strategy = MACDStrategy()  # 用預設 12/26/9
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.BUY, f"預期 buy，實際 {signal}（{reason}）"
    print(f"✅ MACD 黃金交叉測試通過：{reason}")


def test_macd_death_cross_should_sell():
    """前段持平、最後一根大跌 → MACD 下穿訊號線 → 應該 sell。"""
    df = pd.DataFrame({"close": [100] * 34 + [80]})
    strategy = MACDStrategy()
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.SELL, f"預期 sell，實際 {signal}（{reason}）"
    print(f"✅ MACD 死亡交叉測試通過：{reason}")


# ============================================================
# 布林通道策略測試
# ============================================================
def test_bollinger_below_lower_should_buy():
    """最後一根暴跌、跌破下軌 → 應該 buy。"""
    df = pd.DataFrame({"close": [100] * 19 + [50]})
    strategy = BollingerStrategy({"period": 20})
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.BUY, f"預期 buy，實際 {signal}（{reason}）"
    print(f"✅ 布林下軌測試通過：{reason}")


def test_bollinger_above_upper_should_sell():
    """最後一根暴漲、突破上軌 → 應該 sell。"""
    df = pd.DataFrame({"close": [100] * 19 + [150]})
    strategy = BollingerStrategy({"period": 20})
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.SELL, f"預期 sell，實際 {signal}（{reason}）"
    print(f"✅ 布林上軌測試通過：{reason}")


# ============================================================
# 唐奇安通道突破策略測試
# ============================================================
def test_donchian_breakout_should_buy():
    """突破前 20 日高點 → 應該 buy。"""
    df = pd.DataFrame({"close": [10] * 20 + [15]})
    strategy = DonchianStrategy({"period": 20})
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.BUY, f"預期 buy，實際 {signal}（{reason}）"
    print(f"✅ 唐奇安突破測試通過：{reason}")


def test_donchian_breakdown_should_sell():
    """跌破前 20 日低點 → 應該 sell。"""
    df = pd.DataFrame({"close": [10] * 20 + [5]})
    strategy = DonchianStrategy({"period": 20})
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.SELL, f"預期 sell，實際 {signal}（{reason}）"
    print(f"✅ 唐奇安跌破測試通過：{reason}")


# ============================================================
# KD 隨機指標策略測試
# ============================================================
def test_stochastic_golden_cross_should_buy():
    """%K 向上穿越 %D → 應該 buy。"""
    df = pd.DataFrame({"close": [10, 10, 10, 9, 12]})
    strategy = StochasticStrategy({"k_period": 3, "d_period": 2})
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.BUY, f"預期 buy，實際 {signal}（{reason}）"
    print(f"✅ KD 黃金交叉測試通過：{reason}")


# ============================================================
# 動量策略測試
# ============================================================
def test_momentum_up_should_buy():
    """10 日漲超過門檻 → 應該 buy。"""
    df = pd.DataFrame({"close": [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 130]})
    strategy = MomentumStrategy({"period": 10, "threshold": 5})
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.BUY, f"預期 buy，實際 {signal}（{reason}）"
    print(f"✅ 動量追漲測試通過：{reason}")


def test_momentum_down_should_sell():
    """10 日跌超過門檻 → 應該 sell。"""
    df = pd.DataFrame({"close": [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 70]})
    strategy = MomentumStrategy({"period": 10, "threshold": 5})
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.SELL, f"預期 sell，實際 {signal}（{reason}）"
    print(f"✅ 動量殺跌測試通過：{reason}")


if __name__ == "__main__":
    # 直接用 python 執行時，把所有測試都跑一遍
    # 均線交叉
    test_golden_cross_should_buy()
    test_death_cross_should_sell()
    test_not_enough_data_should_hold()
    test_no_cross_should_hold()
    # RSI
    test_rsi_oversold_should_buy()
    test_rsi_overbought_should_sell()
    # MACD
    test_macd_golden_cross_should_buy()
    test_macd_death_cross_should_sell()
    # 布林通道
    test_bollinger_below_lower_should_buy()
    test_bollinger_above_upper_should_sell()
    # 唐奇安
    test_donchian_breakout_should_buy()
    test_donchian_breakdown_should_sell()
    # KD
    test_stochastic_golden_cross_should_buy()
    # 動量
    test_momentum_up_should_buy()
    test_momentum_down_should_sell()
    print("\n🎉 全部策略測試通過！")
