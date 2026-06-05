"""
組合層資金 / 購買力守門測試（Phase 6 step-05）
================================================
純函式 plan_capital：依「可動用現金（已扣現金緩衝）」逐筆核可，扣到不夠其餘進 rejected。
情境：剛好夠 / 不夠 / 保留比例邊界 / cash_per_bot 為 0 / reserve 過大。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_capital.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.capital import plan_capital


def _recs(*symbols):
    return [{"symbol": s, "strategy_key": "rsi"} for s in symbols]


def test_enough_cash_all_approved():
    """現金充足：3 檔全核可、無 rejected。"""
    approved, rejected = plan_capital(
        _recs("AAPL", "MSFT", "NVDA"),
        available_cash=1000, cash_per_bot=200, reserve_ratio=0.2,  # usable=800，需 600
    )
    assert [r["symbol"] for r in approved] == ["AAPL", "MSFT", "NVDA"], approved
    assert rejected == [], rejected


def test_not_enough_rejects_rest():
    """現金不夠：usable=800、每個 300 → 只建得起 2 個，其餘進 rejected（附原因）。"""
    approved, rejected = plan_capital(
        _recs("AAPL", "MSFT", "NVDA", "TSLA"),
        available_cash=1000, cash_per_bot=300, reserve_ratio=0.2,  # usable=800
    )
    assert [r["symbol"] for r in approved] == ["AAPL", "MSFT"], approved
    assert [r["symbol"] for r in rejected] == ["NVDA", "TSLA"], rejected
    assert all("reason" in r for r in rejected), rejected


def test_reserve_ratio_boundary():
    """保留比例邊界：reserve=0.5、cash=1000 → usable=500、每個 200 → 核可 2、拒 1。"""
    approved, rejected = plan_capital(
        _recs("AAPL", "MSFT", "NVDA"),
        available_cash=1000, cash_per_bot=200, reserve_ratio=0.5,  # usable=500
    )
    assert [r["symbol"] for r in approved] == ["AAPL", "MSFT"], approved
    assert [r["symbol"] for r in rejected] == ["NVDA"], rejected


def test_cash_per_bot_zero_approves_all():
    """每個 Bot 配資為 0（不佔資金）→ 全核可。"""
    approved, rejected = plan_capital(
        _recs("AAPL", "MSFT"), available_cash=0, cash_per_bot=0, reserve_ratio=0.2,
    )
    assert [r["symbol"] for r in approved] == ["AAPL", "MSFT"], approved
    assert rejected == []


def test_reserve_full_rejects_all():
    """保留 100% → 可動用 0 → 全部拒（防呆：reserve 夾在 [0,1]）。"""
    approved, rejected = plan_capital(
        _recs("AAPL", "MSFT"), available_cash=1000, cash_per_bot=100, reserve_ratio=1.0,
    )
    assert approved == [], approved
    assert [r["symbol"] for r in rejected] == ["AAPL", "MSFT"], rejected
    print("✅ plan_capital 純函式全通過")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
