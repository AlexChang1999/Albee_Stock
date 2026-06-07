"""
meta-labeling 二級過濾測試（Phase 7 step-05）
===============================================
驗證：
1. should_take 只過濾進場（BUY）；SELL 放行、HOLD 不動作。
2. 低品質狀態（高波動/爆量滯漲/未知）的 BUY 被否決；趨勢盤高品質 BUY 放行。
3. confidence：趨勢盤 > 盤整盤；高信心可餵凱利當 W。

純函式、不連網。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_meta_label.py -v
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.meta_label import should_take, meta_confidence
from backend.services.regime import (
    REGIME_TRENDING,
    REGIME_RANGING,
    REGIME_HIGH_VOLATILITY,
    REGIME_UNKNOWN,
)
from backend.strategies.base import Signal


def _feat(trend=30.0, ret5=0.0):
    return {"trend_strength": trend, "return_5d": ret5}


def test_only_gates_buy():
    """SELL 一律放行（出場不受二級門檻）；HOLD 不算動作。"""
    take_sell, _ = should_take(Signal.SELL, _feat(), REGIME_HIGH_VOLATILITY)
    take_hold, _ = should_take(Signal.HOLD, _feat(), REGIME_TRENDING)
    assert take_sell is True
    assert take_hold is False


def test_chaotic_regime_vetoes_buy():
    """高波動 / 未知狀態 → 二級否決進場。"""
    assert should_take(Signal.BUY, _feat(), REGIME_HIGH_VOLATILITY)[0] is False
    assert should_take(Signal.BUY, _feat(), REGIME_UNKNOWN)[0] is False


def test_trending_buy_passes():
    """趨勢盤、趨勢扎實的 BUY → 放行，且信心達門檻。"""
    take, conf = should_take(Signal.BUY, _feat(trend=40.0), REGIME_TRENDING)
    assert take is True
    assert conf >= 0.5


def test_confidence_trending_beats_ranging():
    """同特徵下，趨勢盤信心 > 盤整盤。"""
    c_trend = meta_confidence(_feat(), REGIME_TRENDING)
    c_range = meta_confidence(_feat(), REGIME_RANGING)
    assert c_trend > c_range


def test_overheated_reduces_confidence():
    """近 5 日漲幅過大（追高）→ 信心被扣，低於不過熱時。"""
    cool = meta_confidence(_feat(ret5=0.0), REGIME_TRENDING)
    hot = meta_confidence(_feat(ret5=0.15), REGIME_TRENDING)
    assert hot < cool


if __name__ == "__main__":
    test_only_gates_buy()
    test_chaotic_regime_vetoes_buy()
    test_trending_buy_passes()
    test_confidence_trending_beats_ranging()
    test_overheated_reduces_confidence()
    print("\n🎉 全部 meta-labeling 二級過濾測試通過！")
