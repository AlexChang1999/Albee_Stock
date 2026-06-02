"""
<策略名> 策略單元測試
============
用「假資料」測訊號判斷對不對，完全不需連線 Alpaca，純測演算法。

執行（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_<name>.py -q
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

from backend.strategies.template import TemplateStrategy  # <-- 改成你的策略
from backend.strategies.base import Signal

# 測試用參數（用小值方便構造精確情境）
PARAMS = {"period": 3}


def test_should_buy():
    """<設計一段必然觸發 BUY 的合成 close 序列>。"""
    df = pd.DataFrame({"close": [10, 10, 10, 9, 12]})  # <-- 換成能逼出 BUY 的資料
    signal, reason = TemplateStrategy(PARAMS).generate_signal(df)
    assert signal == Signal.BUY, f"預期 buy，實際 {signal}（{reason}）"
    print(f"✅ BUY 測試通過：{reason}")


def test_should_sell():
    """<設計一段必然觸發 SELL 的合成 close 序列>。"""
    df = pd.DataFrame({"close": [10, 10, 10, 13, 5]})  # <-- 換成能逼出 SELL 的資料
    signal, reason = TemplateStrategy(PARAMS).generate_signal(df)
    assert signal == Signal.SELL, f"預期 sell，實際 {signal}（{reason}）"
    print(f"✅ SELL 測試通過：{reason}")


def test_not_enough_data_should_hold():
    """資料筆數不足 → 應該觀望(hold)。"""
    df = pd.DataFrame({"close": [10, 10]})  # 短於 period+1
    signal, reason = TemplateStrategy(PARAMS).generate_signal(df)
    assert signal == Signal.HOLD, f"預期 hold，實際 {signal}（{reason}）"
    print(f"✅ 資料不足測試通過：{reason}")


if __name__ == "__main__":
    test_should_buy()
    test_should_sell()
    test_not_enough_data_should_hold()
    print("\n🎉 全部測試通過！")
