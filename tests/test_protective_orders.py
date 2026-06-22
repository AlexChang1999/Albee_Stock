"""
券商端保護單規劃純函式測試（維運安全軌 H1 Step 2）
====================================================
驗證 protective_orders 三個純函式：
- whole_share_qty：整股取整（Alpaca stop 單只支援整股）
- plan_protective_order：trailing 優先序 / 都沒設回 None / stop_price 精度
- order_matches_plan：reconcile 容差比對

純函式、不碰網路/DB。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_protective_orders.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from backend.services.protective_orders import (
    order_matches_plan,
    plan_protective_order,
    whole_share_qty,
)


# ---------- whole_share_qty ----------

def test_whole_share_qty_floors():
    """1000 元買 333 元的股票 → 3 股（floor，不無條件進位）。"""
    assert whole_share_qty(1000.0, 333.0) == 3


def test_whole_share_qty_cannot_afford_one_share():
    """1000 元買 2000 元的高價股 → 0 股（呼叫端應跳過並記審計）。"""
    assert whole_share_qty(1000.0, 2000.0) == 0


def test_whole_share_qty_exact_division():
    """剛好整除不多買也不少買。"""
    assert whole_share_qty(1000.0, 250.0) == 4


def test_whole_share_qty_bad_inputs():
    """金額/價格不合理（0、負、None）一律回 0，不丟例外。"""
    assert whole_share_qty(0, 100.0) == 0
    assert whole_share_qty(1000.0, 0) == 0
    assert whole_share_qty(-1000.0, 100.0) == 0
    assert whole_share_qty(1000.0, -5.0) == 0


# ---------- plan_protective_order ----------

def test_plan_trailing_takes_priority():
    """trailing 與 stop_loss 都有設 → 用原生 trailing stop（券商端自追最高價）。"""
    plan = plan_protective_order(100.0, stop_loss_pct=0.05, trailing_stop_pct=0.03)
    assert plan == {"type": "trailing_stop", "trail_percent": 3.0}


def test_plan_stop_only():
    """只設固定止損 → stop 單，觸發價 = 進場價 ×(1−止損%)，round 2 位。"""
    plan = plan_protective_order(123.456, stop_loss_pct=0.05, trailing_stop_pct=None)
    assert plan == {"type": "stop", "stop_price": round(123.456 * 0.95, 2)}


def test_plan_none_when_no_risk_settings():
    """兩個風控都沒設 → 不掛保護單（回 None）。"""
    assert plan_protective_order(100.0, stop_loss_pct=None, trailing_stop_pct=None) is None


def test_plan_zero_pct_treated_as_unset():
    """0 或負的百分比視為沒設（防呆）。"""
    assert plan_protective_order(100.0, stop_loss_pct=0.0, trailing_stop_pct=0.0) is None


def test_plan_bad_entry_price():
    """進場價不合理 → 回 None，不丟例外。"""
    assert plan_protective_order(0, stop_loss_pct=0.05, trailing_stop_pct=None) is None
    assert plan_protective_order(-1.0, stop_loss_pct=0.05, trailing_stop_pct=None) is None


def test_plan_trail_percent_unit_conversion():
    """專案內 0.03（小數）→ Alpaca 的 3.0（百分比數字）。"""
    plan = plan_protective_order(50.0, stop_loss_pct=None, trailing_stop_pct=0.115)
    assert plan == {"type": "trailing_stop", "trail_percent": 11.5}


# ---------- order_matches_plan ----------

def test_matches_stop_within_tolerance():
    """stop 單觸發價在 0.5% 容差內 → 視為一致（不撤舊掛新）。"""
    plan = {"type": "stop", "stop_price": 95.0}
    assert order_matches_plan("stop", 95.0, None, plan) is True
    assert order_matches_plan("stop", 95.3, None, plan) is True  # 偏 0.32%，容差內


def test_mismatch_stop_price_drifted():
    """使用者改了 stop_loss_pct → 觸發價漂移超過容差 → 不一致。"""
    plan = {"type": "stop", "stop_price": 90.0}
    assert order_matches_plan("stop", 95.0, None, plan) is False


def test_mismatch_wrong_type():
    """型別不同（掛著 stop、計畫要 trailing）→ 不一致。"""
    plan = {"type": "trailing_stop", "trail_percent": 3.0}
    assert order_matches_plan("stop", 97.0, None, plan) is False


def test_matches_trailing():
    """trailing 單 trail_percent 一致 → True；漂移 → False。"""
    plan = {"type": "trailing_stop", "trail_percent": 3.0}
    assert order_matches_plan("trailing_stop", None, 3.0, plan) is True
    assert order_matches_plan("trailing_stop", None, 5.0, plan) is False


def test_mismatch_missing_values():
    """券商端訂單缺對應數值（None）→ 一律不一致（保守：撤舊掛新）。"""
    assert order_matches_plan("stop", None, None, {"type": "stop", "stop_price": 95.0}) is False
    assert order_matches_plan(
        "trailing_stop", None, None, {"type": "trailing_stop", "trail_percent": 3.0}
    ) is False


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
