"""
分數凱利部位測試（Phase 7 step-04）
=====================================
驗證：
1. kelly_fraction：手算驗證、分數凱利係數、硬上限夾住、負期望/缺賠率回 0。
2. kelly_trade_amount：百分比→比例換算、樣本不足回 0、部位受現金量約束。

純函式、不連網。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_sizing.py -v
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.sizing import kelly_fraction, kelly_trade_amount


def test_kelly_fraction_textbook():
    """W=0.6、R=2（avg_win=2、avg_loss=1）→ f*=0.4；¼ 凱利 → 0.1。"""
    f = kelly_fraction(0.6, avg_win=2.0, avg_loss=1.0, fraction=0.25, cap=0.5)
    assert abs(f - 0.1) < 1e-9


def test_kelly_cap_clamps_blowup():
    """估計偏高導致 f 暴衝時，硬上限把它夾住。"""
    # 全凱利 f*=0.4，fraction=1.0 → 0.4，但 cap=0.2 → 夾到 0.2
    f = kelly_fraction(0.6, avg_win=2.0, avg_loss=1.0, fraction=1.0, cap=0.2)
    assert abs(f - 0.2) < 1e-9


def test_kelly_negative_edge_returns_zero():
    """負期望（f*<=0）→ 回 0，不下注。"""
    # W=0.4、R=1 → f*=0.4-0.6/1 = -0.2 → 0
    assert kelly_fraction(0.4, avg_win=1.0, avg_loss=1.0, fraction=0.25, cap=0.2) == 0.0


def test_kelly_missing_odds_returns_zero():
    """缺賠率原料（avg_win 或 avg_loss <= 0）→ 回 0。"""
    assert kelly_fraction(0.9, avg_win=0.0, avg_loss=1.0) == 0.0
    assert kelly_fraction(0.9, avg_win=1.0, avg_loss=0.0) == 0.0


def test_trade_amount_scales_cash():
    """部位金額 = 可用現金 × 凱利比例。"""
    # f=0.1（同 textbook）→ 10000 × 0.1 = 1000
    amt = kelly_trade_amount(
        10000, win_rate_pct=60, avg_win=2.0, avg_loss=1.0,
        num_round_trips=20, fraction=0.25, cap=0.5,
    )
    assert abs(amt - 1000.0) < 1e-6


def test_trade_amount_insufficient_sample_zero():
    """OOS 回合數不足 → W/R 不可信，回 0（不下注）。"""
    amt = kelly_trade_amount(
        10000, win_rate_pct=99, avg_win=5.0, avg_loss=1.0,
        num_round_trips=3, fraction=0.25, cap=0.5, min_round_trips=10,
    )
    assert amt == 0.0


if __name__ == "__main__":
    test_kelly_fraction_textbook()
    test_kelly_cap_clamps_blowup()
    test_kelly_negative_edge_returns_zero()
    test_kelly_missing_odds_returns_zero()
    test_trade_amount_scales_cash()
    test_trade_amount_insufficient_sample_zero()
    print("\n🎉 全部分數凱利部位測試通過！")
