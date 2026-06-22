"""
Bot 執行迴圈（出場監測）測試
============================
驗證 run_bot_once 的關鍵行為，重點在「風控出場」這條跟錢有關的路徑：
- 持倉中即使策略觀望(HOLD)，只要觸發止損就要賣出（這是舊版會漏掉的 bug）。
- 持倉中沒觸發風控、策略也不賣 → 續抱，不重複下單。
- 空手中策略買進訊號 → 進場。
- 休市跳過。
- 追蹤止損讀持久化最高價。
- Phase 6 step-06：run_bot_once 收 bot_id、每輪重查最新值（改風控立即生效）；
  Bot 被刪後再觸發 → 安全 no-op 並移除殭屍排程。

用一顆臨時 SQLite 當測試 DB（monkeypatch bm.SessionLocal），run_bot_once 會從這顆 DB
用 bot_id 重查 Bot；下單 / 查價 / 開市 / 通知 / 審計都 monkeypatch 成假的，
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

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.bots.bot_manager as bm
from backend.config import settings
from backend.database import Base
from backend.models import Bot
from backend.strategies import Signal
from backend.strategies.lookback import required_lookback_days


class FakePosition:
    """假的 Alpaca 持倉物件，只給測試用到的兩個屬性。"""
    def __init__(self, avg_entry_price, qty):
        self.avg_entry_price = avg_entry_price
        self.qty = qty


def _setup_db(tmp_path, monkeypatch):
    """建臨時 SQLite 測試 DB，讓 run_bot_once 的「用 id 重查」走這顆 DB。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    monkeypatch.setattr(bm, "SessionLocal", TestSession)
    return TestSession


def _create_bot(TestSession, **risk) -> int:
    """在測試 DB 建一筆真 Bot，回傳 id。"""
    s = TestSession()
    bot = Bot(
        name="測試Bot", strategy="ma_crossover", symbol="TEST", params={},
        trade_amount=1000.0,
        take_profit_pct=risk.get("take_profit_pct"),
        stop_loss_pct=risk.get("stop_loss_pct"),
        trailing_stop_pct=risk.get("trailing_stop_pct"),
        peak_price=risk.get("peak_price"),
    )
    s.add(bot)
    s.commit()
    bot_id = bot.id
    s.close()
    return bot_id


def _patch_common(monkeypatch, position, price, orders, protective=None):
    """把下單、查持倉、查價、DB 紀錄、開市判斷、組合層守門都換成假的。

    :param protective: 若給一個 list，券商端保護單的掛單動作會記進來
        （("stop", symbol, qty, stop_price) / ("trailing_stop", symbol, qty, trail_percent)）。
    """
    monkeypatch.setattr(bm.alpaca_client, "is_market_open", lambda: True)
    monkeypatch.setattr(bm.alpaca_client, "get_position", lambda s: position)
    monkeypatch.setattr(bm.alpaca_client, "get_latest_price", lambda s: price)
    monkeypatch.setattr(
        bm.alpaca_client, "submit_market_order",
        lambda symbol, qty, side: orders.append((symbol, qty, side)) or "fake_order",
    )
    # 券商端保護單相關（維運安全軌 H1）：預設掛單成功、撤單成功、查無訂單
    protective = protective if protective is not None else []
    monkeypatch.setattr(
        bm.alpaca_client, "submit_stop_order",
        lambda symbol, qty, stop_price, side="sell", time_in_force="gtc":
            protective.append(("stop", symbol, qty, stop_price)) or SimpleNamespace(id="fake-stop-id"),
    )
    monkeypatch.setattr(
        bm.alpaca_client, "submit_trailing_stop_order",
        lambda symbol, qty, trail_percent, side="sell", time_in_force="gtc":
            protective.append(("trailing_stop", symbol, qty, trail_percent)) or SimpleNamespace(id="fake-trail-id"),
    )
    monkeypatch.setattr(bm.alpaca_client, "cancel_order", lambda order_id: True)
    monkeypatch.setattr(bm.alpaca_client, "get_order", lambda order_id: None)
    # 避免寫真資料庫 / 真通知 / 真審計
    monkeypatch.setattr(bm, "_record_and_notify", lambda *a, **k: None)
    monkeypatch.setattr(bm, "_record_decision", lambda *a, **k: None)
    monkeypatch.setattr(bm, "_mark_checked", lambda bot: None)
    # 最高價持久化會碰資料庫，測試裡換成「只更新記憶體物件」的假版本
    monkeypatch.setattr(bm, "_persist_peak", lambda bot, peak: setattr(bot, "peak_price", peak))
    # 組合層守門預設放行（熔斷未觸發、購買力不限），個別測試要驗證守門時再覆寫
    monkeypatch.setattr(bm, "check_breaker", lambda db=None: {"tripped": False})
    monkeypatch.setattr(bm, "_available_buying_power", lambda: None)


def test_stop_loss_sells_even_when_strategy_hold(tmp_path, monkeypatch):
    """持倉 + 止損觸發：就算策略觀望也要賣出，且根本不該去問策略。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders = []
    _patch_common(monkeypatch, FakePosition(avg_entry_price=100, qty=10), price=94, orders=orders)
    # 若流程正確，止損先觸發就 return，不會呼叫策略 → 這裡設成一呼叫就爆，當作護欄
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (_ for _ in ()).throw(AssertionError("止損時不該再問策略")))

    bm.run_bot_once(_create_bot(TestSession, stop_loss_pct=0.05))

    assert len(orders) == 1, orders
    assert orders[0][2] == "sell", orders
    print("✅ 止損優先賣出（策略觀望也賣）測試通過")


def test_holding_no_trigger_holds(tmp_path, monkeypatch):
    """持倉 + 風控未觸發 + 策略觀望 → 不下任何單（續抱）。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders = []
    _patch_common(monkeypatch, FakePosition(avg_entry_price=100, qty=10), price=101, orders=orders)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.HOLD, "觀望"))

    bm.run_bot_once(_create_bot(TestSession, stop_loss_pct=0.05, take_profit_pct=0.10))

    assert orders == [], orders
    print("✅ 風控未觸發續抱測試通過")


def test_flat_buy_on_signal(tmp_path, monkeypatch):
    """空手 + 策略買進 → 進場買單，數量＝金額/價格。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders = []
    _patch_common(monkeypatch, position=None, price=50, orders=orders)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.BUY, "黃金交叉"))

    bm.run_bot_once(_create_bot(TestSession))

    assert len(orders) == 1, orders
    assert orders[0][2] == "buy", orders
    assert orders[0][1] == round(1000.0 / 50, 4), orders  # 1000/50 = 20 股
    print("✅ 空手買進測試通過")


def test_market_closed_skips(tmp_path, monkeypatch):
    """休市中：就算止損條件成立也不下單（整個流程直接跳過）。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders = []
    _patch_common(monkeypatch, FakePosition(avg_entry_price=100, qty=10), price=94, orders=orders)
    monkeypatch.setattr(bm.alpaca_client, "is_market_open", lambda: False)  # 蓋掉成休市

    bm.run_bot_once(_create_bot(TestSession, stop_loss_pct=0.05))  # 預設遵守開市

    assert orders == [], orders
    print("✅ 休市跳過測試通過")


def test_trailing_stop_uses_persisted_peak(tmp_path, monkeypatch):
    """追蹤止損改讀 Bot 上的最高價：peak=120、現價 116、回落 3% → 賣出。

    這顆 Bot 的 peak_price 預設是 120（模擬「資料庫存的、重啟後仍在的最高價」），
    證明追蹤止損是吃持久化的值、不是每次從進場價重算。
    """
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders = []
    # 進場價 100、現價 116；若用進場價當基準不會觸發，用 peak=120 才會（120→116 跌 3.3%）
    _patch_common(monkeypatch, FakePosition(avg_entry_price=100, qty=10), price=116, orders=orders)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.HOLD, "觀望"))

    bm.run_bot_once(_create_bot(TestSession, trailing_stop_pct=0.03, peak_price=120))

    assert len(orders) == 1, orders
    assert orders[0][2] == "sell", orders
    print("✅ 追蹤止損讀持久化最高價測試通過")


def test_refetch_uses_fresh_risk(tmp_path, monkeypatch):
    """Phase 6 step-06：run_bot_once 每輪用 id 重查，改了風控（DB）下一輪就用新值。

    建 Bot 時沒有止損；之後直接改 DB 把 stop_loss_pct 設成 0.05，
    再跑一次——check_exit 收到的門檻必須是新值 0.05（證明吃的是重查後的新鮮 Bot）。
    """
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders = []
    _patch_common(monkeypatch, FakePosition(avg_entry_price=100, qty=10), price=94, orders=orders)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.HOLD, "觀望"))

    captured = {}

    def fake_check_exit(**kwargs):
        captured.update(kwargs)
        return (True, "觸發止損")  # 回賣出，方便順帶確認有走出場

    monkeypatch.setattr(bm, "check_exit", fake_check_exit)

    bot_id = _create_bot(TestSession)  # 建立時 stop_loss_pct=None
    # 模擬使用者用 PUT /bots/{id}/risk 改了止損（直接改 DB）
    s = TestSession()
    s.query(Bot).filter(Bot.id == bot_id).first().stop_loss_pct = 0.05
    s.commit()
    s.close()

    bm.run_bot_once(bot_id)

    assert captured.get("stop_loss_pct") == 0.05, captured  # 用的是重查後的新值
    assert len(orders) == 1 and orders[0][2] == "sell", orders
    print("✅ 每輪重查用新風控值測試通過")


def test_deleted_bot_is_noop_and_removes_job(tmp_path, monkeypatch):
    """Phase 6 step-06：對已刪除的 Bot 觸發一次 → 安全 no-op，且移除殭屍排程。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders = []
    _patch_common(monkeypatch, position=None, price=50, orders=orders)

    removed = []
    monkeypatch.setattr(bm.bot_manager, "stop_bot", lambda bot_id: removed.append(bot_id))
    # 若誤入主流程才會用到策略，這裡設成一被呼叫就爆當護欄
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (_ for _ in ()).throw(AssertionError("已刪 Bot 不該跑策略")))

    bm.run_bot_once(99999)  # 不存在的 id

    assert orders == [], orders
    assert removed == [99999], removed
    print("✅ 已刪 Bot 安全 no-op + 移除殭屍排程測試通過")


def test_persist_peak_survives_restart(tmp_path, monkeypatch):
    """_persist_peak 真的寫進資料庫、重開 session（模擬重啟）後讀得回來。"""
    TestSession = _setup_db(tmp_path, monkeypatch)

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


def test_run_strategy_uses_unified_data_path(monkeypatch):
    """Phase 6 step-01：實盤抓 K 線要走 market_data、帶 settings.DATA_SOURCE、
    帶『依策略參數推算』的回看天數——不再寫死 60、不再直接打 alpaca_client.get_bars。"""
    captured = {}

    def fake_get_bars(symbol, days, source):
        captured["symbol"] = symbol
        captured["days"] = days
        captured["source"] = source
        # 回一份夠長的假 K 線，讓策略能正常跑（內容不影響本測試重點）
        n = 200
        return pd.DataFrame({
            "open": [100.0] * n, "high": [101.0] * n, "low": [99.0] * n,
            "close": [100.0] * n, "volume": [1000] * n,
        })

    # 走 market_data 分派器（非 alpaca_client）；若有人改回直打 alpaca_client 就會炸
    monkeypatch.setattr(bm.market_data, "get_bars", fake_get_bars)
    monkeypatch.setattr(
        bm.alpaca_client, "get_bars",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("實盤不該直接打 alpaca_client.get_bars")),
    )

    bot = SimpleNamespace(symbol="TEST", strategy="ma_crossover",
                          params={"short_window": 5, "long_window": 120})

    bm._run_strategy(bot)

    assert captured["symbol"] == "TEST", captured
    assert captured["source"] == settings.DATA_SOURCE, captured
    assert captured["days"] == required_lookback_days("ma_crossover", bot.params), captured
    assert captured["days"] != 60, "不該再寫死 60"
    print("✅ 實盤資料路徑統一（market_data + DATA_SOURCE + 推算天數）測試通過")


# ====================================================================
# 券商端止損託管（維運安全軌 H1 Step 3）
# ====================================================================

def test_buy_places_broker_stop_with_whole_shares(tmp_path, monkeypatch):
    """空手買進（有設止損）→ 整股買 + 掛券商端 stop 單 + 訂單 id 落 DB。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders, protective = [], []
    _patch_common(monkeypatch, position=None, price=333.0, orders=orders, protective=protective)
    monkeypatch.setattr(settings, "BROKER_STOP_ENABLED", True)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.BUY, "黃金交叉"))

    bot_id = _create_bot(TestSession, stop_loss_pct=0.05)
    bm.run_bot_once(bot_id)

    # 整股：1000/333 = 3.003 → 3 股（不是碎股 3.003）
    assert orders == [("TEST", 3, "buy")], orders
    # 掛了 stop 保護單：觸發價 = 333 ×0.95（round 2 位）
    assert protective == [("stop", "TEST", 3, round(333.0 * 0.95, 2))], protective
    # 訂單 id 持久化到 DB（重啟後才知道券商端掛著哪張單）
    s = TestSession()
    assert s.query(Bot).filter(Bot.id == bot_id).first().protective_order_id == "fake-stop-id"
    s.close()
    print("✅ 買進掛券商端 stop 單（整股 + id 落 DB）測試通過")


def test_buy_skipped_when_cannot_afford_whole_share(tmp_path, monkeypatch):
    """trade_amount 買不起 1 股（高價股）→ 跳過買進、不送任何單。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders, protective = [], []
    _patch_common(monkeypatch, position=None, price=2000.0, orders=orders, protective=protective)
    monkeypatch.setattr(settings, "BROKER_STOP_ENABLED", True)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.BUY, "黃金交叉"))

    bm.run_bot_once(_create_bot(TestSession, stop_loss_pct=0.05))

    assert orders == [] and protective == [], (orders, protective)
    print("✅ 買不起 1 股跳過進場測試通過")


def test_trailing_setting_uses_native_trailing_stop(tmp_path, monkeypatch):
    """trailing_stop_pct 有設 → 掛原生 trailing stop（優先於固定 stop），單位轉百分比數字。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders, protective = [], []
    _patch_common(monkeypatch, position=None, price=50.0, orders=orders, protective=protective)
    monkeypatch.setattr(settings, "BROKER_STOP_ENABLED", True)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.BUY, "突破"))

    bm.run_bot_once(_create_bot(TestSession, stop_loss_pct=0.05, trailing_stop_pct=0.03))

    assert protective == [("trailing_stop", "TEST", 20, 3.0)], protective  # 0.03 → 3.0
    print("✅ trailing 優先掛原生追蹤止損單測試通過")


def test_ensure_replaces_missing_protective_order(tmp_path, monkeypatch):
    """持倉 + 有止損設定，但券商端保護單失蹤（沒 id）→ 每輪自癒補掛。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders, protective = [], []
    # 進場 100、現價 101：不觸發止損、策略觀望 → 唯一動作應是補掛保護單
    _patch_common(monkeypatch, FakePosition(avg_entry_price=100, qty=10), price=101,
                  orders=orders, protective=protective)
    monkeypatch.setattr(settings, "BROKER_STOP_ENABLED", True)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.HOLD, "觀望"))

    bm.run_bot_once(_create_bot(TestSession, stop_loss_pct=0.05))

    assert orders == [], orders
    assert protective == [("stop", "TEST", 10, 95.0)], protective  # 100 ×0.95、整股 10
    print("✅ 保護單失蹤自癒補掛測試通過")


def test_local_exit_cancels_protective_order_first(tmp_path, monkeypatch):
    """本機風控出場 → 先撤券商端保護單、再送市價賣（順序不可反）。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    sequence = []
    orders = []
    _patch_common(monkeypatch, FakePosition(avg_entry_price=100, qty=10), price=94, orders=orders)
    monkeypatch.setattr(settings, "BROKER_STOP_ENABLED", True)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.HOLD, "觀望"))
    # 自癒這輪不動作（單視為活著且正確），聚焦撤單順序
    monkeypatch.setattr(bm, "_ensure_protective_order", lambda bot, position: None)
    monkeypatch.setattr(
        bm.alpaca_client, "cancel_order",
        lambda order_id: sequence.append(("cancel", order_id)) or True,
    )
    monkeypatch.setattr(
        bm.alpaca_client, "submit_market_order",
        lambda symbol, qty, side: sequence.append(("sell", symbol)) or "fake_order",
    )

    bot_id = _create_bot(TestSession, stop_loss_pct=0.05)
    s = TestSession()
    s.query(Bot).filter(Bot.id == bot_id).first().protective_order_id = "ord-9"
    s.commit()
    s.close()

    bm.run_bot_once(bot_id)

    assert sequence == [("cancel", "ord-9"), ("sell", "TEST")], sequence
    # 撤掉後 id 應清空
    s = TestSession()
    assert s.query(Bot).filter(Bot.id == bot_id).first().protective_order_id is None
    s.close()
    print("✅ 本機出場先撤保護單再賣測試通過")


def test_local_exit_aborts_when_cancel_fails(tmp_path, monkeypatch):
    """撤單失敗（= 券商端已先成交）→ 放棄本機賣出，等下一輪回填，不能雙重賣。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders = []
    _patch_common(monkeypatch, FakePosition(avg_entry_price=100, qty=10), price=94, orders=orders)
    monkeypatch.setattr(settings, "BROKER_STOP_ENABLED", True)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.HOLD, "觀望"))
    monkeypatch.setattr(bm, "_ensure_protective_order", lambda bot, position: None)
    monkeypatch.setattr(bm.alpaca_client, "cancel_order", lambda order_id: False)  # 撤不掉

    bot_id = _create_bot(TestSession, stop_loss_pct=0.05)
    s = TestSession()
    s.query(Bot).filter(Bot.id == bot_id).first().protective_order_id = "ord-9"
    s.commit()
    s.close()

    bm.run_bot_once(bot_id)

    assert orders == [], orders  # 沒送本機賣單
    s = TestSession()
    assert s.query(Bot).filter(Bot.id == bot_id).first().protective_order_id == "ord-9"  # id 保留給回填
    s.close()
    print("✅ 撤單失敗放棄本機賣出測試通過")


def test_settle_broker_exit_backfills_trade(tmp_path, monkeypatch):
    """空手 + DB 記著保護單 id + 券商端已成交 → 回填交易/決策紀錄、清 id 與 peak。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders = []
    _patch_common(monkeypatch, position=None, price=96.0, orders=orders)
    monkeypatch.setattr(settings, "BROKER_STOP_ENABLED", True)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.HOLD, "觀望"))

    filled = SimpleNamespace(id="ord-5", status="filled", filled_qty="10", filled_avg_price="95.5")
    monkeypatch.setattr(bm.alpaca_client, "get_order", lambda order_id: filled)

    trades, decisions = [], []
    monkeypatch.setattr(bm, "_record_and_notify",
                        lambda bot, side, qty, price, order, reason: trades.append((side, qty, price)))
    monkeypatch.setattr(bm, "_record_decision",
                        lambda bot, signal, reason, price, action, **k: decisions.append((signal, action)))

    bot_id = _create_bot(TestSession, stop_loss_pct=0.05, peak_price=120.0)
    s = TestSession()
    s.query(Bot).filter(Bot.id == bot_id).first().protective_order_id = "ord-5"
    s.commit()
    s.close()

    bm.run_bot_once(bot_id)

    assert ("sell", 10.0, 95.5) in trades, trades  # 用券商端「實際成交價」回填，不是現價
    assert (Signal.SELL, bm.ACTION_SOLD) in decisions, decisions
    s = TestSession()
    row = s.query(Bot).filter(Bot.id == bot_id).first()
    assert row.protective_order_id is None, row.protective_order_id
    s.close()
    print("✅ 券商端成交回填帳測試通過")


def test_broker_stop_disabled_keeps_legacy_behavior(tmp_path, monkeypatch):
    """BROKER_STOP_ENABLED=False → 行為與舊版完全一致：碎股買進、不掛任何保護單。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    orders, protective = [], []
    _patch_common(monkeypatch, position=None, price=333.0, orders=orders, protective=protective)
    monkeypatch.setattr(settings, "BROKER_STOP_ENABLED", False)
    monkeypatch.setattr(bm, "_run_strategy", lambda bot: (Signal.BUY, "黃金交叉"))

    bm.run_bot_once(_create_bot(TestSession, stop_loss_pct=0.05))

    assert orders == [("TEST", round(1000.0 / 333.0, 4), "buy")], orders  # 碎股維持舊版
    assert protective == [], protective  # 不掛券商端保護單
    print("✅ 開關關閉退回舊版行為（回歸）測試通過")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
