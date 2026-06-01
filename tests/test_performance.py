"""
Bot 績效計算單元測試
====================
驗證 compute_bot_stats 用真實交易紀錄算出的勝率/報酬率/交易次數/最大回撤正確。
純資料運算，完全不需連線 Alpaca。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe tests\\test_performance.py
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

from backend.services.performance import compute_bot_stats


def test_no_trades():
    """沒有任何交易 → 各項指標皆為 0。"""
    r = compute_bot_stats([])
    assert r["num_trades"] == 0, r
    assert r["num_round_trips"] == 0, r
    assert r["win_rate_pct"] == 0.0, r
    assert r["return_pct"] == 0.0, r
    assert r["max_drawdown_pct"] == 0.0, r
    print("✅ 無交易測試通過")


def test_single_winning_round_trip():
    """買 1 股 @100、賣 1 股 @120 → 賺 20，報酬率 20%、勝率 100%。"""
    trades = [
        {"side": "buy", "qty": 1, "price": 100},
        {"side": "sell", "qty": 1, "price": 120},
    ]
    r = compute_bot_stats(trades)
    assert r["num_trades"] == 2, r
    assert r["num_round_trips"] == 1, r
    assert r["win_rate_pct"] == 100.0, r
    assert r["total_profit"] == 20.0, r
    assert r["return_pct"] == 20.0, r
    assert r["max_drawdown_pct"] == 0.0, r
    print(f"✅ 單次獲利測試通過：報酬 {r['return_pct']}%")


def test_losing_round_trip():
    """買 2 股 @50、賣 2 股 @40 → 賠 20，報酬率 -20%、勝率 0%。"""
    trades = [
        {"side": "buy", "qty": 2, "price": 50},
        {"side": "sell", "qty": 2, "price": 40},
    ]
    r = compute_bot_stats(trades)
    assert r["num_round_trips"] == 1, r
    assert r["win_rate_pct"] == 0.0, r
    assert r["total_profit"] == -20.0, r
    assert r["return_pct"] == -20.0, r
    # 投入 100，賠到 80，回撤 20%
    assert r["max_drawdown_pct"] == 20.0, r
    print(f"✅ 單次虧損測試通過：報酬 {r['return_pct']}%、回撤 {r['max_drawdown_pct']}%")


def test_win_rate_two_of_three():
    """三組買賣兩賺一賠 → 勝率約 66.67%。"""
    trades = [
        {"side": "buy", "qty": 1, "price": 100},
        {"side": "sell", "qty": 1, "price": 110},  # +10 賺
        {"side": "buy", "qty": 1, "price": 100},
        {"side": "sell", "qty": 1, "price": 90},   # -10 賠
        {"side": "buy", "qty": 1, "price": 100},
        {"side": "sell", "qty": 1, "price": 130},  # +30 賺
    ]
    r = compute_bot_stats(trades)
    assert r["num_round_trips"] == 3, r
    assert r["win_rate_pct"] == 66.67, r
    assert r["total_profit"] == 30.0, r
    print(f"✅ 勝率測試通過：勝率 {r['win_rate_pct']}%")


def test_open_position_not_counted():
    """只有買、還沒賣 → 0 次完整買賣（未實現損益不計入）。"""
    trades = [{"side": "buy", "qty": 1, "price": 100}]
    r = compute_bot_stats(trades)
    assert r["num_trades"] == 1, r
    assert r["num_round_trips"] == 0, r
    assert r["win_rate_pct"] == 0.0, r
    print("✅ 未平倉不計入測試通過")


if __name__ == "__main__":
    test_no_trades()
    test_single_winning_round_trip()
    test_losing_round_trip()
    test_win_rate_two_of_three()
    test_open_position_not_counted()
    print("\n🎉 全部績效計算測試通過！")
