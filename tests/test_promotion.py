"""
董事會核准測試（Phase 10 step-06）
====================================
涵蓋：
1. 純函式 evaluate_promotion_readiness：三道門檻（OOS EV / Paper 勝率 / 樣本數）皆過才達標。
2. 狀態流轉 propose → approve / reject（含冪等、未達標 409、退回理由寫入）。
3. propose 達標時主動通知一次（去抖：再 propose 不重複通知）。
4. _build_reminders 命中 propose_live_candidate（達標 Paper Bot 浮上提醒）。

不連網：臨時 SQLite + monkeypatch notify。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_promotion.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.database import Base, get_db
from backend.models import Bot, TradeLog, Opportunity
from backend.routers import promotion
from backend.routers.promotion import evaluate_promotion_readiness


# ---------- 1. evaluate_promotion_readiness（純函式） ----------
def _stats(win=80.0, trips=4):
    return {"win_rate_pct": win, "num_round_trips": trips, "return_pct": 12.0}


def test_readiness_all_pass():
    v = evaluate_promotion_readiness(
        _stats(), 300.0, ev_threshold=150.0, winrate_threshold=55.0
    )
    assert v["ready"] is True
    assert v["reasons"] == []


def test_readiness_fails_each_gate():
    # OOS EV 不足
    v = evaluate_promotion_readiness(_stats(), 100.0, ev_threshold=150.0, winrate_threshold=55.0)
    assert v["ready"] is False and any("OOS EV" in r for r in v["reasons"])
    # 沒對應候選（OOS EV=None）
    v = evaluate_promotion_readiness(_stats(), None, ev_threshold=150.0, winrate_threshold=55.0)
    assert v["ready"] is False
    # 勝率不足
    v = evaluate_promotion_readiness(_stats(win=40.0), 300.0, ev_threshold=150.0, winrate_threshold=55.0)
    assert v["ready"] is False and any("勝率" in r for r in v["reasons"])
    # 樣本不足
    v = evaluate_promotion_readiness(_stats(trips=1), 300.0, ev_threshold=150.0, winrate_threshold=55.0)
    assert v["ready"] is False and any("樣本不足" in r for r in v["reasons"])


# ---------- 共用：隔離 client + 種資料 ----------
@contextmanager
def _isolated_client(tmp_path):
    from backend.main import app

    engine = create_engine(
        f"sqlite:///{tmp_path / 'app_promo.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    def _override():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    try:
        with TestClient(app) as client:
            yield client, TestingSession
    finally:
        app.dependency_overrides.pop(get_db, None)


def _seed_ready_bot(db, *, symbol="AAPL", strategy="ma_crossover", name="達標 Bot"):
    """種一個 Paper 達標 Bot：4 次全勝 round trip + 對應高 OOS EV 機會。"""
    bot = Bot(name=name, strategy=strategy, symbol=symbol, params={}, promotion_status="paper")
    db.add(bot)
    db.commit()
    db.refresh(bot)
    for _ in range(4):
        db.add(TradeLog(bot_id=bot.id, symbol=symbol, side="buy", qty=1, price=100.0))
        db.add(TradeLog(bot_id=bot.id, symbol=symbol, side="sell", qty=1, price=110.0))
    db.add(Opportunity(symbol=symbol, strategy_key=strategy, oos_expected_value=300.0, status="new"))
    db.commit()
    return bot.id


# ---------- 2 + 3. 狀態流轉 + 通知去抖 ----------
def test_propose_approve_flow_and_notify_debounce(tmp_path, monkeypatch):
    notes = []
    monkeypatch.setattr(promotion.notifier, "notify", lambda msg: notes.append(msg))

    with _isolated_client(tmp_path) as (client, TestingSession):
        db = TestingSession()
        try:
            bot_id = _seed_ready_bot(db)
        finally:
            db.close()

        # 待核清單一開始為空（還沒提議）
        assert client.get("/promotions").json() == []

        # 提議 → proposed_live、通知一次、附證據
        r = client.post(f"/promotions/{bot_id}/propose").json()
        assert r["promotion_status"] == "proposed_live"
        assert r["promotion_reason"] and "OOS EV=300" in r["promotion_reason"]
        assert len(notes) == 1 and "達標 Bot" in notes[0]

        # 出現在待核清單
        pend = client.get("/promotions").json()
        assert len(pend) == 1 and pend[0]["bot_id"] == bot_id

        # 再提議 → 冪等、不重複通知（去抖）
        r2 = client.post(f"/promotions/{bot_id}/propose").json()
        assert r2["promotion_status"] == "proposed_live"
        assert len(notes) == 1

        # 核准 → approved_live、冪等
        a = client.post(f"/promotions/{bot_id}/approve").json()
        assert a["promotion_status"] == "approved_live"
        a2 = client.post(f"/promotions/{bot_id}/approve").json()
        assert a2["promotion_status"] == "approved_live"

        # 已核准的不在待核清單
        assert client.get("/promotions").json() == []
        # 但能用 status 查到
        approved = client.get("/promotions?status=approved_live").json()
        assert len(approved) == 1


def test_propose_blocked_when_not_ready(tmp_path):
    with _isolated_client(tmp_path) as (client, TestingSession):
        db = TestingSession()
        try:
            # 沒交易、沒機會 → 達不到門檻
            bot = Bot(name="弱 Bot", strategy="rsi", symbol="TSLA", params={}, promotion_status="paper")
            db.add(bot)
            db.commit()
            db.refresh(bot)
            bot_id = bot.id
        finally:
            db.close()

        r = client.post(f"/promotions/{bot_id}/propose")
        assert r.status_code == 409
        assert "尚未達標" in r.json()["detail"]


def test_reject_writes_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(promotion.notifier, "notify", lambda msg: None)
    with _isolated_client(tmp_path) as (client, TestingSession):
        db = TestingSession()
        try:
            bot_id = _seed_ready_bot(db, symbol="NVDA", strategy="macd")
        finally:
            db.close()

        client.post(f"/promotions/{bot_id}/propose")
        r = client.post(f"/promotions/{bot_id}/reject", json={"reason": "波動太大先觀望"}).json()
        assert r["promotion_status"] == "rejected"
        assert r["promotion_reason"] == "波動太大先觀望"

        # 退回後不在待核清單；不能核准（非 proposed_live）
        assert client.get("/promotions").json() == []
        assert client.post(f"/promotions/{bot_id}/approve").status_code == 409


def test_approve_requires_proposed(tmp_path):
    with _isolated_client(tmp_path) as (client, TestingSession):
        db = TestingSession()
        try:
            bot = Bot(name="新 Bot", strategy="rsi", symbol="META", params={}, promotion_status="paper")
            db.add(bot)
            db.commit()
            db.refresh(bot)
            bot_id = bot.id
        finally:
            db.close()
        # paper 狀態直接核准 → 409
        assert client.post(f"/promotions/{bot_id}/approve").status_code == 409


# ---------- 4. _build_reminders 命中 propose_live_candidate ----------
def test_reminder_hits_ready_paper_bot(tmp_path, monkeypatch):
    from backend.routers.presets import _build_reminders

    with _isolated_client(tmp_path) as (client, TestingSession):
        db = TestingSession()
        try:
            _seed_ready_bot(db, symbol="AMD", strategy="rsi")
            reminders = _build_reminders(db)
        finally:
            db.close()

        hits = [r for r in reminders if r["type"] == "propose_live_candidate"]
        assert len(hits) == 1
        assert hits[0]["symbol"] == "AMD"
