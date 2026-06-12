"""
tracking error 對帳 + 自動降級測試（維運安全軌 H3 Step 7）
============================================================
驗證：
- evaluate_tracking 純函式全分支（樣本不足 / 無基準 / oos≤0 / 恰在門檻 / 違規）。
- run_tracking_check 編排：連續 N 次「新樣本」違規才降級；回合沒增加不計數；
  回升歸零；降級後**不撤券商端保護單、不平倉**（持倉保護不中斷）。

用臨時 SQLite + monkeypatch（不連網、不碰真 DB）。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_tracking.py -q
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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.services.tracking as tk
from backend.config import settings
from backend.database import Base
from backend.models import Bot, TradeLog, Opportunity, DecisionLog
from backend.models.decision_log import ACTION_DEMOTED


# ---------- evaluate_tracking（純函式） ----------

def test_eval_no_baseline_not_comparable():
    """無 OOS 基準 → 不對帳、不違規（不冤殺）。"""
    v = tk.evaluate_tracking([1.0] * 10, None)
    assert v["comparable"] is False and v["breach"] is False


def test_eval_insufficient_samples_not_comparable():
    """回合數 < min_round_trips → 樣本不足不對帳。"""
    v = tk.evaluate_tracking([5.0, 5.0], 2.0, min_round_trips=5)
    assert v["comparable"] is False and v["breach"] is False


def test_eval_breach_when_below_half_oos():
    """實跑均值 < OOS × 0.5 → 違規。"""
    v = tk.evaluate_tracking([0.4] * 6, 2.0, min_round_trips=5, demote_ratio=0.5)
    assert v["comparable"] is True
    assert v["threshold_pct"] == 1.0  # 2.0 × 0.5
    assert v["breach"] is True


def test_eval_pass_when_at_threshold():
    """恰好等於門檻 → 不違規（嚴格小於才算）。"""
    v = tk.evaluate_tracking([1.0] * 6, 2.0, min_round_trips=5, demote_ratio=0.5)
    assert v["breach"] is False


def test_eval_negative_oos_clamped_to_zero():
    """OOS ≤ 0（理論上部署閘擋掉，防衛性處理）→ 門檻夾成 0：實跑負才違規。"""
    v = tk.evaluate_tracking([0.1] * 6, -3.0, min_round_trips=5)
    assert v["threshold_pct"] == 0.0 and v["breach"] is False
    v2 = tk.evaluate_tracking([-0.5] * 6, -3.0, min_round_trips=5)
    assert v2["breach"] is True


def test_eval_rolling_window():
    """滾動窗只看最近 window 回合：前面爛、最近好 → 不違規。"""
    returns = [-5.0] * 10 + [3.0] * 5
    v = tk.evaluate_tracking(returns, 2.0, min_round_trips=5, window=5)
    assert v["paper_ev_pct"] == 3.0 and v["breach"] is False


# ---------- run_tracking_check（編排，臨時 SQLite） ----------

def _setup(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'trk.db'}")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    monkeypatch.setattr(tk, "SessionLocal", TestSession)
    return TestSession


def _make_bot(TestSession, **kw) -> int:
    s = TestSession()
    bot = Bot(name="追蹤Bot", strategy="ma_crossover", symbol="TEST", params={},
              is_active=True, **kw)
    s.add(bot)
    s.commit()
    bot_id = bot.id
    s.close()
    return bot_id


def _add_round_trips(TestSession, bot_id: int, returns_pct: list[float], entry=100.0):
    """灌 N 組完整買賣，使每回合報酬率 = returns_pct 的對應值。"""
    s = TestSession()
    for r in returns_pct:
        s.add(TradeLog(bot_id=bot_id, symbol="TEST", side="buy", qty=1, price=entry))
        s.add(TradeLog(bot_id=bot_id, symbol="TEST", side="sell", qty=1,
                       price=entry * (1 + r / 100)))
    s.commit()
    s.close()


def _add_opportunity(TestSession, expectancy_pct: float):
    s = TestSession()
    s.add(Opportunity(symbol="TEST", strategy_key="ma_crossover", params={},
                      oos_expectancy_pct=expectancy_pct))
    s.commit()
    s.close()


def _patch_orchestration(monkeypatch):
    """停掉真排程器/通知，記錄降級與撤單呼叫。"""
    notified, stopped, cancels = [], [], []
    monkeypatch.setattr(tk, "notify", lambda msg: notified.append(msg))

    class FakeManager:
        def stop_bot(self, bot_id):
            stopped.append(bot_id)

    import backend.bots.bot_manager as bm
    monkeypatch.setattr(bm, "bot_manager", FakeManager())
    # 降級流程「不該」碰券商端撤單——記錄以驗證沒被呼叫
    monkeypatch.setattr(
        bm.alpaca_client, "cancel_order",
        lambda order_id: cancels.append(order_id) or True,
    )
    # 門檻參數固定，不受 .env 影響
    monkeypatch.setattr(settings, "TRACKING_MIN_ROUND_TRIPS", 5)
    monkeypatch.setattr(settings, "TRACKING_WINDOW", 10)
    monkeypatch.setattr(settings, "TRACKING_DEMOTE_RATIO", 0.5)
    monkeypatch.setattr(settings, "TRACKING_DEMOTE_AFTER", 3)
    return notified, stopped, cancels


def test_demotes_after_three_breaches_with_new_samples(tmp_path, monkeypatch):
    """連續 3 個「有新回合」的對帳日都違規 → 第三次降級；保護單不被撤。"""
    TestSession = _setup(tmp_path, monkeypatch)
    notified, stopped, cancels = _patch_orchestration(monkeypatch)

    bot_id = _make_bot(TestSession, protective_order_id="ord-keep")
    _add_opportunity(TestSession, expectancy_pct=2.0)  # 門檻 = 1.0%

    for i in range(3):
        _add_round_trips(TestSession, bot_id, [0.1] * (5 if i == 0 else 1))  # 每天有新回合、都低於門檻
        tk.run_tracking_check()

    s = TestSession()
    bot = s.query(Bot).filter(Bot.id == bot_id).first()
    assert bot.is_active is False, "連續三次違規應自動降級"
    assert bot.tracking_breach_count == 3
    assert bot.demoted_at is not None and "違規" in (bot.demote_reason or "")
    assert bot.protective_order_id == "ord-keep", "降級不該撤券商端保護單"
    # 落了 demoted 決策審計
    assert s.query(DecisionLog).filter(DecisionLog.action == ACTION_DEMOTED).count() == 1
    s.close()
    assert stopped == [bot_id]
    assert len(notified) == 1 and "自動降級" in notified[0]
    assert cancels == [], "降級流程不該呼叫撤單"
    print("✅ 連續三次違規自動降級（保護單不動）測試通過")


def test_no_new_round_trips_does_not_count(tmp_path, monkeypatch):
    """回合數沒增加 → 同一批爛樣本連跑三天也不累計（防重複扣分）。"""
    TestSession = _setup(tmp_path, monkeypatch)
    _patch_orchestration(monkeypatch)

    bot_id = _make_bot(TestSession)
    _add_opportunity(TestSession, expectancy_pct=2.0)
    _add_round_trips(TestSession, bot_id, [0.1] * 6)  # 一批爛樣本

    for _ in range(3):
        tk.run_tracking_check()  # 第一次計 1，之後回合數沒變 → 跳過

    s = TestSession()
    bot = s.query(Bot).filter(Bot.id == bot_id).first()
    assert bot.is_active is True, "不該被降級"
    assert bot.tracking_breach_count == 1, bot.tracking_breach_count
    s.close()
    print("✅ 無新回合不重複計數測試通過")


def test_recovery_resets_breach_count(tmp_path, monkeypatch):
    """違規兩次後回升 → 計數歸零（要「連續」違規才降）。"""
    TestSession = _setup(tmp_path, monkeypatch)
    _patch_orchestration(monkeypatch)

    bot_id = _make_bot(TestSession)
    _add_opportunity(TestSession, expectancy_pct=2.0)

    _add_round_trips(TestSession, bot_id, [0.1] * 5)
    tk.run_tracking_check()  # 違規 1
    _add_round_trips(TestSession, bot_id, [0.1])
    tk.run_tracking_check()  # 違規 2
    _add_round_trips(TestSession, bot_id, [30.0, 30.0, 30.0])  # 大賺，滾動均值回門檻上
    tk.run_tracking_check()  # 回升 → 歸零

    s = TestSession()
    bot = s.query(Bot).filter(Bot.id == bot_id).first()
    assert bot.is_active is True
    assert bot.tracking_breach_count == 0, bot.tracking_breach_count
    s.close()
    print("✅ 回升歸零測試通過")


def test_insufficient_samples_never_demotes(tmp_path, monkeypatch):
    """樣本不足（< min_round_trips）→ 永不違規、永不降級。"""
    TestSession = _setup(tmp_path, monkeypatch)
    _patch_orchestration(monkeypatch)

    bot_id = _make_bot(TestSession)
    _add_opportunity(TestSession, expectancy_pct=2.0)
    _add_round_trips(TestSession, bot_id, [0.1] * 3)  # 只有 3 回合 < 5

    tk.run_tracking_check()

    s = TestSession()
    bot = s.query(Bot).filter(Bot.id == bot_id).first()
    assert bot.is_active is True and bot.tracking_breach_count == 0
    assert bot.tracking_last_rt_count == 3  # 回合數有記住（下次只看新增）
    s.close()
    print("✅ 樣本不足不冤殺測試通過")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
