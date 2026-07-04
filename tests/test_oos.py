"""
樣本外（OOS）驗證測試（Phase 6 step-04）
=========================================
驗證 optimizer 把過擬合從口號變成程式層硬約束：
- split_train_test：切分點正確、測試段在時間軸後段、不洩漏、不洗牌。
- run_auto_backtest：每組都帶 in-sample 與 OOS 指標；冠軍是「OOS EV 最高」者，
  排行榜依 OOS EV 由高到低；並能看到「樣本內漂亮、樣本外掉下來」的過擬合落差。

不連網：monkeypatch market_data.get_bars 餵合成資料。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_oos.py -q
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

from backend.services import optimizer
from backend.services.optimizer import split_train_test, run_auto_backtest


def test_split_train_test_time_order_no_leak():
    """切分點 = 前 70% 訓練、後 30% 測試；測試段必須是後段、不洗牌。"""
    df = pd.DataFrame({"close": list(range(10))})
    train, test = split_train_test(df, test_ratio=0.3)
    assert len(train) == 7 and len(test) == 3, (len(train), len(test))
    assert train["close"].tolist() == [0, 1, 2, 3, 4, 5, 6], train["close"].tolist()
    assert test["close"].tolist() == [7, 8, 9], test["close"].tolist()  # 後段、原順序
    print("✅ split_train_test 切分/時序/無洩漏測試通過")


def _regime_ohlc(n=220, seed=7):
    """造「訓練段強趨勢上行、測試段震盪下行」的資料，讓樣本內與樣本外冠軍會不同。"""
    rs = np.random.RandomState(seed)
    steps = rs.normal(0.0, 0.012, n)
    cut = int(n * 0.7)
    steps[:cut] += 0.02     # 訓練段：明顯上行（很多策略樣本內都好看）
    steps[cut:] -= 0.02     # 測試段：反轉下行（樣本外見真章）
    close = 100 * np.cumprod(1 + steps)
    return pd.DataFrame({
        "timestamp": pd.bdate_range("2023-01-02", periods=n).astype(str),
        "open": close, "high": close * 1.005, "low": close * 0.995,
        "close": close, "volume": rs.randint(1_000_000, 5_000_000, n),
    })


def test_auto_backtest_ranks_by_oos(monkeypatch):
    """冠軍依『樣本外 EV』排名；排行榜每筆都帶 oos / is 指標且依 OOS 由高到低。"""
    # 資料抓取已改走 bar_cache（Phase 11 step-04）；patch 新 seam 注入合成資料、免連網免落盤。
    monkeypatch.setattr(optimizer.bar_cache, "get_bars_cached",
                        lambda symbol, days=60, source="alpaca", today=None, timeframe="1Day": _regime_ohlc())

    scan = run_auto_backtest("TEST")
    lb = scan["leaderboard"]
    assert lb, "排行榜不應為空"

    # 每筆都要同時帶樣本外與樣本內 EV
    for e in lb:
        m = e["metrics"]
        assert "oos_expected_value" in m and "is_expected_value" in m, m

    oos_vals = [e["metrics"]["oos_expected_value"] for e in lb]
    # 冠軍 = OOS EV 最高者
    assert scan["best"]["metrics"]["oos_expected_value"] == max(oos_vals), scan["best"]["metrics"]
    # 排行榜依 OOS EV 由高到低（前一筆 >= 後一筆）
    assert all(oos_vals[i] >= oos_vals[i + 1] for i in range(len(oos_vals) - 1)), oos_vals
    print(f"✅ 冠軍依 OOS EV 排名測試通過：冠軍 OOS EV = {scan['best']['metrics']['oos_expected_value']}")


def test_overfitting_visible(monkeypatch):
    """過擬合可見：上行訓練段下，至少有組合『樣本內 EV > 樣本外 EV』（樣本外掉下來）。"""
    # 資料抓取已改走 bar_cache（Phase 11 step-04）；patch 新 seam 注入合成資料、免連網免落盤。
    monkeypatch.setattr(optimizer.bar_cache, "get_bars_cached",
                        lambda symbol, days=60, source="alpaca", today=None, timeframe="1Day": _regime_ohlc())

    scan = run_auto_backtest("TEST")
    lb = scan["leaderboard"]
    # 找出樣本內 EV 最高的組合，它在反轉的測試段通常掉下來
    is_best = max(lb, key=lambda e: e["metrics"]["is_expected_value"])
    assert is_best["metrics"]["is_expected_value"] > is_best["metrics"]["oos_expected_value"], (
        is_best["metrics"]["is_expected_value"], is_best["metrics"]["oos_expected_value"]
    )
    print("✅ 過擬合落差可見測試通過（樣本內漂亮、樣本外掉下來）")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
