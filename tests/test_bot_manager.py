"""
Bot 執行迴圈（出場監測）測試
============================
驗證 run_bot_once 的關鍵行為，重點在「風控出場」這條跟錢有關的路徑：
- 持倉中即使策略觀望(HOLD)，只要觸發止損就要賣出（這是舊版會漏掉的 bug）。
- 持倉中沒觸發風控、策略也不賣 → 續抱，不重複下單。
- 空手中策略買進訊號 → 進場。

用 monkeypatch 把 Alpaca 下單、資料抓取、DB 紀錄全部換成假的，
所以這個測試「不連網、不碰真資料庫」，純驗證流程邏輯。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_bot_manager.py
"""

import sys
from pathlib import Path
from types import SimpleNamespace

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import backend.bots.bot_manager as bm
from backend.strategies import Signal


class FakePosition:
    """假的 Alpaca 持倉物件，只給測試用到的兩個屬性。"""
    def __init__(self, avg_entry_price, qty):
        self.avg_entry_price = avg_entry_price
        self.qty = qty


def _make_bot(**risk):
    """造一個最小的 Bot-like 物件（不碰資料庫）。"""
    return SimpleNamespace(
        id=999,
        name="測試Bot",
        symbol="TEST",
        strategy="ma_crossover",
        params={},
        trade_amount=1000.0,
        take_profit_pct=risk.get("take_profit_pct"),
        stop_loss_pct=risk.get("stop_loss_pct"),
        trailing_stop_pct=risk.get("trailing_stop_pct"),
    )


def _patch_common(monkeypatch, position, price, orders):
    """把下單、查持倉、查價、DB 紀錄、開市判斷都換成假的。"""
    monkeypatch.setattr(bm.alpaca_client, "is_market_open", lambda: True)
    monkeypatch.setattr(bm.alpaca_client, "get_position", lambda s: position)
    monkeypatch.setattr(bm.alpaca_client, "get_latest_price", lambda s: price)
    monkeypatch.setattr(
        bm.alpaca_client, "submit_market_order",
        lambda symbol, qty, side: orders.append((symbol, qty, side)) or "fake_order",
    )
    # 避免寫真資料庫 / 真通知
    monkeypatch.setattr(bm, "_record_and_notify", lambda *a, **k: None)


def test_stop_loss_sells_even_when_strategy_hold(monkeypatch):
    """持倉 + 止損觸發：就算策略觀望也要賣出，且根本不該去問策略。"""
    bm._peak_prices.pop(999, None)
    orders = []
    _patch_common(monkeypatch, FakePosition(avg_entry_price=100, qty=10), price=94, orders=orders)
    # 若流程正確，止損先觸發就 return，不會呼叫策略 → 這裡設成一呼叫就爆，當作護欄
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (_ for _ in ()).throw(AssertionError("止損時不該再問策略")))

    bm.run_bot_once(_make_bot(stop_loss_pct=0.05))

    assert len(orders) == 1, orders
    assert orders[0][2] == "sell", orders
    print("✅ 止損優先賣出（策略觀望也賣）測試通過")


def test_holding_no_trigger_holds(monkeypatch):
    """持倉 + 風控未觸發 + 策略觀望 → 不下任何單（續抱）。"""
    bm._peak_prices.pop(999, None)
    orders = []
    _patch_common(monkeypatch, FakePosition(avg_entry_price=100, qty=10), price=101, orders=orders)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.HOLD, "觀望"))

    bm.run_bot_once(_make_bot(stop_loss_pct=0.05, take_profit_pct=0.10))

    assert orders == [], orders
    print("✅ 風控未觸發續抱測試通過")


def test_flat_buy_on_signal(monkeypatch):
    """空手 + 策略買進 → 進場買單，數量＝金額/價格。"""
    bm._peak_prices.pop(999, None)
    orders = []
    _patch_common(monkeypatch, position=None, price=50, orders=orders)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.BUY, "黃金交叉"))

    bm.run_bot_once(_make_bot())

    assert len(orders) == 1, orders
    assert orders[0][2] == "buy", orders
    assert orders[0][1] == round(1000.0 / 50, 4), orders  # 1000/50 = 20 股
    print("✅ 空手買進測試通過")


def test_market_closed_skips(monkeypatch):
    """休市中：就算止損條件成立也不下單（整個流程直接跳過）。"""
    bm._peak_prices.pop(999, None)
    orders = []
    _patch_common(monkeypatch, FakePosition(avg_entry_price=100, qty=10), price=94, orders=orders)
    monkeypatch.setattr(bm.alpaca_client, "is_market_open", lambda: False)  # 蓋掉成休市

    bm.run_bot_once(_make_bot(stop_loss_pct=0.05))  # 預設遵守開市

    assert orders == [], orders
    print("✅ 休市跳過測試通過")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
