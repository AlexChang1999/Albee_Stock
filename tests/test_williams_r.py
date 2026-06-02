"""
威廉指標（Williams %R）策略單元測試
============
用「假資料」測訊號判斷對不對，完全不需連線 Alpaca，純測演算法。

執行（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_williams_r.py -q
"""

import sys
from pathlib import Path

# Windows 主控台 cp950 印中文/emoji 會崩潰，強制改 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 讓測試 import 得到 backend（把專案根目錄加進搜尋路徑）
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from backend.strategies.williams_r import WilliamsRStrategy
from backend.strategies.base import Signal

# 用小回看期數方便精確構造情境
PARAMS = {"period": 3}


def test_oversold_should_buy():
    """收盤跌到近 3 日最低 → %R 接近 -100（超賣）→ 應該 buy。"""
    # 最後 3 根 [10, 9, 7]：max=10 min=7 close=7 → %R=-100 < -80
    df = pd.DataFrame({"close": [12, 11, 10, 9, 7]})
    signal, reason = WilliamsRStrategy(PARAMS).generate_signal(df)
    assert signal == Signal.BUY, f"預期 buy，實際 {signal}（{reason}）"
    print(f"✅ 超賣測試通過：{reason}")


def test_overbought_should_sell():
    """收盤漲到近 3 日最高 → %R 接近 0（超買）→ 應該 sell。"""
    # 最後 3 根 [10, 11, 12]：max=12 min=10 close=12 → %R=0 > -20
    df = pd.DataFrame({"close": [7, 8, 10, 11, 12]})
    signal, reason = WilliamsRStrategy(PARAMS).generate_signal(df)
    assert signal == Signal.SELL, f"預期 sell，實際 {signal}（{reason}）"
    print(f"✅ 超買測試通過：{reason}")


def test_not_enough_data_should_hold():
    """資料筆數不足（少於 period）→ 應該觀望(hold)。"""
    df = pd.DataFrame({"close": [10, 10]})
    signal, reason = WilliamsRStrategy(PARAMS).generate_signal(df)
    assert signal == Signal.HOLD, f"預期 hold，實際 {signal}（{reason}）"
    print(f"✅ 資料不足測試通過：{reason}")


if __name__ == "__main__":
    test_oversold_should_buy()
    test_overbought_should_sell()
    test_not_enough_data_should_hold()
    print("\n🎉 全部測試通過！")
