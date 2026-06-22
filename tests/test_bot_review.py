"""
bot 汰弱審查員測試（Phase 13）
==============================
自足：temp sqlite + create_all；monkeypatch 掉 notify 與 bot_manager.stop_bot（不發通知、不碰排程器）。

純函式 review_bot：
1. 爛 bot（夠久夠多筆、勝率/報酬不及格）→ cull=True、verdict="poor"。
2. 好 bot → verdict="good"、cull=False。
3. 年齡不足 / 樣本不足 → 不汰（verdict 仍依績效，但 cull=False）。

批次器 run_bot_review：
4. ENABLED=false → no-op。
5. 爛 paper bot → 軟汰弱（is_active=False + culled_at + cull_reason）、落 DecisionLog、fit=poor。
6. 好 paper bot → 不動、fit=good。
7. 樣本不足 → 不汰、fit=insufficient、skipped_insufficient 計數。
8. 只碰 paper：proposed_live/approved_live 的爛 bot 一律不動。
9. 冪等：已 culled 的 bot 下輪不再處理。
10. MAX_CULL_PER_RUN 上限：一輪最多汰這麼多支。
11. fit upsert：同 (策略,標的) 只留一筆。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_bot_review.py -q
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import Bot, TradeLog, StrategySymbolFit, DecisionLog
from backend.models.decision_log import ACTION_BOT_CULLED
from backend.services import bot_review
from backend.services.bot_review import run_bot_review, review_bot


# ---------- fixtures ----------
@pytest.fixture(autouse=True)
def _enable_and_stub(monkeypatch):
    """開審查員 + 固定門檻 + 掉通知/排程副作用。"""
    s = bot_review.settings
    monkeypatch.setattr(s, "BOT_REVIEW_ENABLED", True)
    monkeypatch.setattr(s, "BOT_REVIEW_MIN_ROUND_TRIPS", 10)
    monkeypatch.setattr(s, "BOT_REVIEW_MIN_AGE_DAYS", 14)
    monkeypatch.setattr(s, "BOT_REVIEW_GOOD_WINRATE", 55)
    monkeypatch.setattr(s, "BOT_REVIEW_CULL_WINRATE", 40)
    monkeypatch.setattr(s, "BOT_REVIEW_CULL_RETURN_PCT", 0)
    monkeypatch.setattr(s, "BOT_REVIEW_CULL_MAX_DD", 35)
    monkeypatch.setattr(s, "BOT_REVIEW_MAX_CULL_PER_RUN", 20)
    monkeypatch.setattr(bot_review, "notify", lambda *a, **k: None)
    from backend.bots.bot_manager import bot_manager
    monkeypatch.setattr(bot_manager, "stop_bot", lambda *a, **k: None)


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'bot_review.db'}")
    Base.metadata.create_all(engine)  # model 已含新表/欄
    return sessionmaker(bind=engine)()


def _bot(db, strategy="rsi", symbol="SPY", *, status="paper", age_days=30, active=True):
    b = Bot(
        name=f"{strategy}@{symbol}", strategy=strategy, symbol=symbol, params={},
        promotion_status=status, is_active=active,
        created_at=datetime.now() - timedelta(days=age_days),
    )
    db.add(b)
    db.commit()
    return b


def _round_trips(db, bot, n, win):
    """加 n 組完整買賣（buy@100 → sell@110(贏)/90(輸)），created_at 嚴格遞增。"""
    base = datetime.now() - timedelta(days=2)
    seq = 0
    for _ in range(n):
        db.add(TradeLog(bot_id=bot.id, symbol=bot.symbol, side="buy", qty=1,
                        price=100.0, created_at=base + timedelta(seconds=seq)))
        seq += 1
        db.add(TradeLog(bot_id=bot.id, symbol=bot.symbol, side="sell", qty=1,
                        price=(110.0 if win else 90.0), created_at=base + timedelta(seconds=seq)))
        seq += 1
    db.commit()


# ---------- 純函式 review_bot ----------
def test_review_bot_culls_loser():
    v = review_bot({"num_round_trips": 12, "win_rate_pct": 25, "return_pct": -8, "max_drawdown_pct": 12},
                   30, min_round_trips=10, min_age_days=14, good_winrate=55,
                   cull_winrate=40, cull_return_pct=0, cull_max_dd=35)
    assert v["verdict"] == "poor" and v["cull"] is True and "勝率" in v["reason"]


def test_review_bot_keeps_winner():
    v = review_bot({"num_round_trips": 12, "win_rate_pct": 70, "return_pct": 15, "max_drawdown_pct": 8},
                   30, min_round_trips=10, min_age_days=14, good_winrate=55,
                   cull_winrate=40, cull_return_pct=0, cull_max_dd=35)
    assert v["verdict"] == "good" and v["cull"] is False


def test_review_bot_young_not_culled():
    v = review_bot({"num_round_trips": 12, "win_rate_pct": 5, "return_pct": -40, "max_drawdown_pct": 80},
                   3, min_round_trips=10, min_age_days=14, good_winrate=55,
                   cull_winrate=40, cull_return_pct=0, cull_max_dd=35)
    assert v["verdict"] == "poor" and v["cull"] is False  # 年齡不足，不汰


def test_review_bot_insufficient():
    v = review_bot({"num_round_trips": 3, "win_rate_pct": 0, "return_pct": -99, "max_drawdown_pct": 99},
                   99, min_round_trips=10, min_age_days=14, good_winrate=55,
                   cull_winrate=40, cull_return_pct=0, cull_max_dd=35)
    assert v["verdict"] == "insufficient" and v["cull"] is False  # 樣本不足，不汰


def test_review_bot_high_drawdown_culls():
    """勝率/報酬都還行，但回撤過大也汰。"""
    v = review_bot({"num_round_trips": 12, "win_rate_pct": 60, "return_pct": 5, "max_drawdown_pct": 50},
                   30, min_round_trips=10, min_age_days=14, good_winrate=55,
                   cull_winrate=40, cull_return_pct=0, cull_max_dd=35)
    assert v["cull"] is True and "回撤" in v["reason"]


# ---------- 批次器 run_bot_review ----------
def test_disabled_noop(tmp_path, monkeypatch):
    db = _session(tmp_path)
    b = _bot(db)
    _round_trips(db, b, 12, win=False)
    monkeypatch.setattr(bot_review.settings, "BOT_REVIEW_ENABLED", False)
    stats = run_bot_review(db)
    assert stats == {"reviewed": 0, "fits_updated": 0, "culled": 0,
                     "skipped_insufficient": 0, "failed": 0}
    db.refresh(b)
    assert b.is_active is True and b.culled_at is None


def test_cull_loser(tmp_path):
    db = _session(tmp_path)
    b = _bot(db, strategy="rsi", symbol="SPY")
    _round_trips(db, b, 12, win=False)
    stats = run_bot_review(db)

    assert stats["reviewed"] == 1 and stats["culled"] == 1
    db.refresh(b)
    assert b.is_active is False
    assert b.culled_at is not None
    assert b.cull_reason and "勝率" in b.cull_reason
    # fit 記成 poor
    fit = db.query(StrategySymbolFit).filter_by(strategy_key="rsi", symbol="SPY").one()
    assert fit.verdict == "poor" and fit.num_round_trips == 12 and fit.sample_bot_id == b.id
    # 落 DecisionLog 審計
    dl = db.query(DecisionLog).filter_by(action=ACTION_BOT_CULLED, bot_id=b.id).all()
    assert len(dl) == 1


def test_keep_winner(tmp_path):
    db = _session(tmp_path)
    b = _bot(db, strategy="macd", symbol="QQQ")
    _round_trips(db, b, 12, win=True)
    stats = run_bot_review(db)

    assert stats["culled"] == 0 and stats["reviewed"] == 1
    db.refresh(b)
    assert b.is_active is True and b.culled_at is None
    fit = db.query(StrategySymbolFit).filter_by(strategy_key="macd", symbol="QQQ").one()
    assert fit.verdict == "good"


def test_insufficient_not_culled(tmp_path):
    db = _session(tmp_path)
    b = _bot(db)
    _round_trips(db, b, 3, win=False)  # < 10 筆
    stats = run_bot_review(db)
    assert stats["culled"] == 0 and stats["skipped_insufficient"] == 1
    db.refresh(b)
    assert b.is_active is True
    fit = db.query(StrategySymbolFit).filter_by(strategy_key="rsi", symbol="SPY").one()
    assert fit.verdict == "insufficient"


def test_only_paper_bots_touched(tmp_path):
    """proposed_live / approved_live 的爛 bot 一律不碰（真錢相關不動）。"""
    db = _session(tmp_path)
    for st in ("proposed_live", "approved_live"):
        b = _bot(db, symbol=st.upper()[:4], status=st)
        _round_trips(db, b, 12, win=False)
    stats = run_bot_review(db)
    assert stats["reviewed"] == 0 and stats["culled"] == 0
    # 兩支都沒被動
    for b in db.query(Bot).all():
        assert b.is_active is True and b.culled_at is None


def test_idempotent_skip_culled(tmp_path):
    db = _session(tmp_path)
    b = _bot(db)
    _round_trips(db, b, 12, win=False)
    s1 = run_bot_review(db)
    assert s1["culled"] == 1
    # 第二輪：已 culled（culled_at 有值）→ 不再撈到
    s2 = run_bot_review(db)
    assert s2["reviewed"] == 0 and s2["culled"] == 0


def test_max_cull_per_run_cap(tmp_path, monkeypatch):
    db = _session(tmp_path)
    monkeypatch.setattr(bot_review.settings, "BOT_REVIEW_MAX_CULL_PER_RUN", 1)
    b1 = _bot(db, symbol="AAA")
    b2 = _bot(db, symbol="BBB")
    _round_trips(db, b1, 12, win=False)
    _round_trips(db, b2, 12, win=False)
    stats = run_bot_review(db)
    assert stats["culled"] == 1  # 上限 1，另一支留下輪
    culled = db.query(Bot).filter(Bot.culled_at.isnot(None)).count()
    assert culled == 1


def test_fit_upsert_unique(tmp_path):
    """同 (策略,標的) 兩支 bot → fit 只留一筆（upsert）。"""
    db = _session(tmp_path)
    b1 = _bot(db, strategy="rsi", symbol="SPY")
    b2 = _bot(db, strategy="rsi", symbol="SPY")
    _round_trips(db, b1, 12, win=True)
    _round_trips(db, b2, 12, win=True)
    run_bot_review(db)
    fits = db.query(StrategySymbolFit).filter_by(strategy_key="rsi", symbol="SPY").all()
    assert len(fits) == 1


if __name__ == "__main__":
    print("（需 pytest 的 tmp_path / monkeypatch，請用 pytest 執行）")
