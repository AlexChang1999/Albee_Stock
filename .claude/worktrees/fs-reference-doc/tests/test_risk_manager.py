"""
風控（止盈/止損/追蹤止損）單元測試
==================================
驗證 check_exit 在各種情境下是否正確判斷「該不該出場」。
純函式運算，完全不需連線 Alpaca、不需資料庫。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe tests\\test_risk_manager.py
"""

import sys
from pathlib import Path

# Windows 主控台 cp950 印 emoji 會崩潰，強制改 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.risk_manager import check_exit


def test_no_threshold_holds():
    """三個門檻都沒設 → 不論漲跌都續抱。"""
    should_exit, reason = check_exit(entry_price=100, current_price=80)
    assert should_exit is False, reason
    assert reason is None, reason
    print("✅ 無門檻續抱測試通過")


def test_stop_loss_triggers():
    """止損 5%：進場 100、現價 94（跌 6%）→ 出場。"""
    should_exit, reason = check_exit(
        entry_price=100, current_price=94, stop_loss_pct=0.05
    )
    assert should_exit is True, reason
    assert "止損" in reason, reason
    print(f"✅ 止損觸發測試通過：{reason}")


def test_stop_loss_not_triggered():
    """止損 5%：現價 96（只跌 4%，未到 95）→ 續抱。"""
    should_exit, reason = check_exit(
        entry_price=100, current_price=96, stop_loss_pct=0.05
    )
    assert should_exit is False, reason
    print("✅ 止損未觸發測試通過")


def test_take_profit_triggers():
    """止盈 10%：進場 100、現價 111（漲 11%）→ 出場。"""
    should_exit, reason = check_exit(
        entry_price=100, current_price=111, take_profit_pct=0.10
    )
    assert should_exit is True, reason
    assert "止盈" in reason, reason
    print(f"✅ 止盈觸發測試通過：{reason}")


def test_trailing_stop_triggers():
    """
    追蹤止損 3%：進場 100，曾漲到最高 120，現價 116（從高點回落 3.3%）→ 出場。
    注意：此時離進場價還是賺的，固定止損不會動，靠追蹤止損鎖利。
    """
    should_exit, reason = check_exit(
        entry_price=100,
        current_price=116,
        peak_price=120,
        trailing_stop_pct=0.03,
    )
    assert should_exit is True, reason
    assert "追蹤止損" in reason, reason
    print(f"✅ 追蹤止損觸發測試通過：{reason}")


def test_trailing_stop_not_triggered():
    """追蹤止損 3%：最高 120、現價 118（只回落 1.7%）→ 續抱。"""
    should_exit, reason = check_exit(
        entry_price=100,
        current_price=118,
        peak_price=120,
        trailing_stop_pct=0.03,
    )
    assert should_exit is False, reason
    print("✅ 追蹤止損未觸發測試通過")


def test_stop_loss_priority_over_take_profit():
    """同時設止損與止盈、價格大跌：應先判止損（保護優先）。"""
    should_exit, reason = check_exit(
        entry_price=100,
        current_price=90,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
    )
    assert should_exit is True, reason
    assert "止損" in reason, reason
    print(f"✅ 止損優先測試通過：{reason}")


def test_invalid_entry_price_holds():
    """進場價不合理（0 / None）→ 不判斷、續抱，避免除以零或錯誤結論。"""
    assert check_exit(entry_price=0, current_price=50, stop_loss_pct=0.05) == (False, None)
    assert check_exit(entry_price=None, current_price=50, stop_loss_pct=0.05) == (False, None)
    print("✅ 無效進場價防呆測試通過")


if __name__ == "__main__":
    test_no_threshold_holds()
    test_stop_loss_triggers()
    test_stop_loss_not_triggered()
    test_take_profit_triggers()
    test_trailing_stop_triggers()
    test_trailing_stop_not_triggered()
    test_stop_loss_priority_over_take_profit()
    test_invalid_entry_price_holds()
    print("\n🎉 全部風控測試通過！")
