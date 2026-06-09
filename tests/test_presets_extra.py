"""
Phase 5 選配：好策略一鍵轉 Bot + 主動提醒 測試
=================================================
涵蓋：
1. preset_to_bot：把方案複製成 Bot（欄位對映正確、symbol 轉大寫、name 可覆寫）。
2. _build_reminders：
   - 負 EV 且未檢討 → review_negative_ev。
   - 有檢討 / 正 EV → 不提醒。
   - 好策略(is_good)未實跑 → deploy_good_strategy；建出對應 Bot 後 → 提醒消失。

不連網：用臨時 SQLite + 直接呼叫 router 內的純函式（不經 run_backtest）。

執行（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_presets_extra.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import StrategyPreset, BacktestRun, Bot
from backend.routers.presets import preset_to_bot, _build_reminders, ToBotIn


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'presets.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# ---------- 1. preset_to_bot ----------
def test_preset_to_bot_copies_fields(tmp_path):
    """方案 → Bot：策略/標的/參數照抄，symbol 轉大寫。"""
    db = _session(tmp_path)
    p = StrategyPreset(name="AAPL RSI 保守", strategy_key="rsi",
                       symbol="aapl", params={"period": 14})
    db.add(p)
    db.commit()
    db.refresh(p)

    out = preset_to_bot(p.id, ToBotIn(trade_amount=2000.0), db)
    bot = db.query(Bot).filter(Bot.id == out["id"]).first()
    assert bot is not None
    assert bot.name == "AAPL RSI 保守"   # 沒帶 name → 用方案名
    assert bot.strategy == "rsi"
    assert bot.symbol == "AAPL"          # 轉大寫
    assert bot.params == {"period": 14}
    assert bot.trade_amount == 2000.0


def test_preset_to_bot_name_override(tmp_path):
    """帶 name → 覆寫 Bot 名稱。"""
    db = _session(tmp_path)
    p = StrategyPreset(name="原方案名", strategy_key="macd", symbol="TSLA", params={})
    db.add(p)
    db.commit()
    db.refresh(p)

    out = preset_to_bot(p.id, ToBotIn(name="我的 TSLA Bot"), db)
    bot = db.query(Bot).filter(Bot.id == out["id"]).first()
    assert bot.name == "我的 TSLA Bot"


# ---------- 2. _build_reminders ----------
def _run(db, *, ev, is_good=False, postmortem=None, symbol="NVDA", strategy="rsi"):
    r = BacktestRun(
        strategy_key=strategy, params={}, symbol=symbol, period_days=365,
        metrics={"expected_value": ev}, is_good=is_good, claude_postmortem=postmortem,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def test_reminder_negative_ev_without_postmortem(tmp_path):
    """負 EV 且未檢討 → 出現 review_negative_ev。"""
    db = _session(tmp_path)
    _run(db, ev=-12.5)
    types = [r["type"] for r in _build_reminders(db)]
    assert "review_negative_ev" in types


def test_reminder_negative_ev_with_postmortem_silent(tmp_path):
    """負 EV 但已檢討 → 不提醒。"""
    db = _session(tmp_path)
    _run(db, ev=-12.5, postmortem="已分析：進場太頻繁")
    types = [r["type"] for r in _build_reminders(db)]
    assert "review_negative_ev" not in types


def test_reminder_positive_ev_silent(tmp_path):
    """正 EV → 不該有負 EV 提醒。"""
    db = _session(tmp_path)
    _run(db, ev=33.0)
    types = [r["type"] for r in _build_reminders(db)]
    assert "review_negative_ev" not in types


def test_reminder_good_strategy_not_deployed(tmp_path):
    """好策略未實跑 → deploy_good_strategy；建出對應 Bot 後消失。"""
    db = _session(tmp_path)
    _run(db, ev=50.0, is_good=True, symbol="MSFT", strategy="macd")
    types = [r["type"] for r in _build_reminders(db)]
    assert "deploy_good_strategy" in types

    # 建一個同 標的+策略 的 Bot → 提醒應消失
    db.add(Bot(name="MSFT MACD", strategy="macd", symbol="MSFT", params={}, trade_amount=1000.0))
    db.commit()
    types2 = [r["type"] for r in _build_reminders(db)]
    assert "deploy_good_strategy" not in types2


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        test_preset_to_bot_copies_fields(p)
        test_preset_to_bot_name_override(p)
        test_reminder_negative_ev_without_postmortem(p)
        test_reminder_negative_ev_with_postmortem_silent(p)
        test_reminder_positive_ev_silent(p)
        test_reminder_good_strategy_not_deployed(p)
    print("✅ Phase 5 選配測試通過")
