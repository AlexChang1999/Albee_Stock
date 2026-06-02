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
        peak_price=risk.get("peak_price"),  # 持倉最高價（None=空手），改存資料庫後放在 Bot 上
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
    # 最高價持久化會碰資料庫，測試裡換成「只更新記憶體物件」的假版本
    monkeypatch.setattr(bm, "_persist_peak", lambda bot, peak: setattr(bot, "peak_price", peak))
    # 記錄檢查時間也會碰資料庫，測試裡換成 no-op
    monkeypatch.setattr(bm, "_mark_checked", lambda bot: None)


def test_stop_loss_sells_even_when_strategy_hold(monkeypatch):
    """持倉 + 止損觸發：就算策略觀望也要賣出，且根本不該去問策略。"""
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
    orders = []
    _patch_common(monkeypatch, FakePosition(avg_entry_price=100, qty=10), price=101, orders=orders)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.HOLD, "觀望"))

    bm.run_bot_once(_make_bot(stop_loss_pct=0.05, take_profit_pct=0.10))

    assert orders == [], orders
    print("✅ 風控未觸發續抱測試通過")


def test_flat_buy_on_signal(monkeypatch):
    """空手 + 策略買進 → 進場買單，數量＝金額/價格。"""
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
    orders = []
    _patch_common(monkeypatch, FakePosition(avg_entry_price=100, qty=10), price=94, orders=orders)
    monkeypatch.setattr(bm.alpaca_client, "is_market_open", lambda: False)  # 蓋掉成休市

    bm.run_bot_once(_make_bot(stop_loss_pct=0.05))  # 預設遵守開市

    assert orders == [], orders
    print("✅ 休市跳過測試通過")


def test_trailing_stop_uses_persisted_peak(monkeypatch):
    """追蹤止損改讀 Bot 上的最高價：peak=120、現價 116、回落 3% → 賣出。

    這顆 Bot 的 peak_price 預設是 120（模擬「資料庫存的、重啟後仍在的最高價」），
    證明追蹤止損是吃持久化的值、不是每次從進場價重算。
    """
    orders = []
    # 進場價 100、現價 116；若用進場價當基準不會觸發，用 peak=120 才會（120→116 跌 3.3%）
    _patch_common(monkeypatch, FakePosition(avg_entry_price=100, qty=10), price=116, orders=orders)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.HOLD, "觀望"))

    bm.run_bot_once(_make_bot(trailing_stop_pct=0.03, peak_price=120))

    assert len(orders) == 1, orders
    assert orders[0][2] == "sell", orders
    print("✅ 追蹤止損讀持久化最高價測試通過")


def test_persist_peak_survives_restart(tmp_path, monkeypatch):
    """_persist_peak 真的寫進資料庫、重開 session（模擬重啟）後讀得回來。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.database import Base
    from backend.models import Bot

    # 用一顆臨時 SQLite 檔當測試資料庫（不碰專案真 DB）
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    monkeypatch.setattr(bm, "SessionLocal", TestSession)  # 讓 _persist_peak 用測試 DB

    # 先建一筆 Bot
    s = TestSession()
    bot = Bot(name="持久化測試", strategy="ma_crossover", symbol="TEST")
    s.add(bot)
    s.commit()
    bot_id = bot.id
    s.close()

    # 寫入最高價（不靠手上物件，模擬排程帶舊物件進來）
    bm._persist_peak(SimpleNamespace(id=bot_id, peak_price=None), 123.45)

    # 重開一條 session（= 模擬後端重啟）讀回來
    s2 = TestSession()
    reloaded = s2.query(Bot).filter(Bot.id == bot_id).first()
    assert reloaded.peak_price == 123.45, reloaded.peak_price
    s2.close()
    print("✅ 最高價寫入資料庫並重啟後仍在 測試通過")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
