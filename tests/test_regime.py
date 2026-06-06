"""
市場狀態分類器測試（Phase 7 step-02）
=======================================
驗證 regime.classify_regime 的規則式決策樹：各狀態的代表性特徵分對。
純函式、不連網。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_regime.py -v
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import settings
from backend.services.regime import (
    classify_regime,
    REGIME_TRENDING,
    REGIME_RANGING,
    REGIME_HIGH_VOLUME_STALL,
    REGIME_HIGH_VOLATILITY,
    REGIME_UNKNOWN,
)


def _features(**kw):
    """造一組完整特徵 dict，未指定的鍵預設中性（不觸發任何特例）。"""
    base = {
        "volume_ratio": 1.0,
        "return_5d": 0.05,
        "return_20d": 0.05,
        "volatility_20d": 0.1,
        "trend_strength": 10.0,
        "atr_pct": 0.02,
        "range_position": 0.5,
    }
    base.update(kw)
    return base


def test_high_volatility_takes_priority():
    """年化波動超標 → high_volatility（最優先，連趨勢都讓位）。"""
    f = _features(volatility_20d=settings.REGIME_HIGH_VOL_THRESHOLD + 0.1, trend_strength=99)
    assert classify_regime(f) == REGIME_HIGH_VOLATILITY


def test_high_volume_stall():
    """量比高 + 近 5 日報酬 ≈ 0 → 爆量滯漲（你舉的「量大卻沒漲幅」）。"""
    f = _features(volume_ratio=settings.REGIME_VOLUME_SPIKE + 0.5, return_5d=0.0)
    assert classify_regime(f) == REGIME_HIGH_VOLUME_STALL


def test_volume_spike_but_big_move_is_not_stall():
    """量大但同時大漲 → 不是滯漲（有趨勢就歸趨勢）。"""
    f = _features(
        volume_ratio=settings.REGIME_VOLUME_SPIKE + 0.5,
        return_5d=0.20,
        trend_strength=settings.REGIME_ADX_TREND + 5,
    )
    assert classify_regime(f) == REGIME_TRENDING


def test_trending():
    """ADX 夠強 → trending。"""
    f = _features(trend_strength=settings.REGIME_ADX_TREND + 5)
    assert classify_regime(f) == REGIME_TRENDING


def test_ranging_is_catch_all():
    """無高波動、無爆量滯漲、ADX 不強 → 盤整。"""
    f = _features(trend_strength=settings.REGIME_ADX_TREND - 5)
    assert classify_regime(f) == REGIME_RANGING


def test_unknown_when_core_features_missing():
    """核心特徵全缺 → unknown（上層應保守）。"""
    f = _features(volatility_20d=None, volume_ratio=None, trend_strength=None)
    assert classify_regime(f) == REGIME_UNKNOWN


def test_partial_none_does_not_crash():
    """部分特徵 None：該規則不觸發、往下走，不應崩。"""
    f = _features(volatility_20d=None, return_5d=None)
    # 波動未知不觸發高波動；報酬未知不觸發滯漲；ADX 弱 → 盤整
    assert classify_regime(f) == REGIME_RANGING


if __name__ == "__main__":
    test_high_volatility_takes_priority()
    test_high_volume_stall()
    test_volume_spike_but_big_move_is_not_stall()
    test_trending()
    test_ranging_is_catch_all()
    test_unknown_when_core_features_missing()
    test_partial_none_does_not_crash()
    print("\n🎉 全部市場狀態分類器測試通過！")
