"""
事件驅動風險閘測試（Phase 7 step-06）
=======================================
驗證：
1. 重大負面情緒 → brake（不開新倉，size_factor=0）。
2. 偏弱但未達否決 → 縮部位（size_factor<1）。
3. 中性/正向 → 照常（size_factor=1）。
4. best-effort：沒情緒資料 / 總開關關 → 不煞車（size_factor=1）。
5. **不猜方向**：bullish 高分不會放大部位（factor 上限 1.0）。

純函式、不連網。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_event_risk.py -v
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.event_risk import assess_event_risk


def _sent(label, score):
    return {"label": label, "score": score, "reason": ""}


def test_bearish_brakes():
    """重大負面（bearish）→ 不開新倉。"""
    r = assess_event_risk(_sent("bearish", -50), veto_score=-20, caution_score=0, size_factor=0.5)
    assert r["brake"] is True and r["size_factor"] == 0.0


def test_caution_band_shrinks():
    """偏弱（分數低於 caution 但未達否決）→ 縮部位。"""
    r = assess_event_risk(_sent("neutral", -10), veto_score=-20, caution_score=0, size_factor=0.5)
    assert r["brake"] is False and r["size_factor"] == 0.5


def test_neutral_normal():
    """中性/正向 → 照常，不縮。"""
    r = assess_event_risk(_sent("bullish", 30), veto_score=-20, caution_score=0, size_factor=0.5)
    assert r["brake"] is False and r["size_factor"] == 1.0


def test_no_direction_bet():
    """不猜方向：bullish 高分 size_factor 仍上限 1.0，不放大部位。"""
    r = assess_event_risk(_sent("bullish", 99), veto_score=-20, caution_score=0, size_factor=0.5)
    assert r["size_factor"] <= 1.0


def test_best_effort_no_data():
    """沒情緒資料（None）→ 不煞車（離線不阻斷）。"""
    r = assess_event_risk(None, veto_score=-20, caution_score=0, size_factor=0.5)
    assert r["brake"] is False and r["size_factor"] == 1.0


def test_disabled_passthrough():
    """總開關關 → 完全不縮（向後相容）。"""
    r = assess_event_risk(_sent("bearish", -99), enabled=False)
    assert r["brake"] is False and r["size_factor"] == 1.0


if __name__ == "__main__":
    test_bearish_brakes()
    test_caution_band_shrinks()
    test_neutral_normal()
    test_no_direction_bet()
    test_best_effort_no_data()
    test_disabled_passthrough()
    print("\n🎉 全部事件驅動風險閘測試通過！")
