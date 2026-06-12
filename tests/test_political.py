"""
政治專討員測試（Phase 10 step-05）
====================================
涵蓋：
1. 純函式 summarize_post / frequency_features：摘要截斷、24h/1h 發文數。
2. judge_post：monkeypatch LLM 回 JSON → 解析成 {label,score,reason}；空白 / 例外 → 中性。
3. event_to_sentiment / latest_event_sentiment：轉情緒格式、取最新、太舊退場。
4. ★ political_size_factor bridge：預設關 → 放行；啟用 + 偏空事件 → 接 event_risk 煞車
   （不開新倉 / 縮部位）；啟用但無事件 → best-effort 不煞車。
5. runner glue _handle_message：作者過濾 + 判讀 + 落表（monkeypatch LLM，不連 Discord）。
6. GET /political/events + /political/risk 往返。

不連網、不連 Discord：用臨時 SQLite + monkeypatch LLM。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_political.py -q
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
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.database import Base, get_db
from backend.models import PoliticalEvent
from backend.services import political
from backend.services.political import (
    summarize_post,
    frequency_features,
    judge_post,
    event_to_sentiment,
    latest_event_sentiment,
    political_size_factor,
    record_event,
)
from backend.bots import political_watcher


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'political.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# ---------- 1. 純函式 ----------
def test_summarize_post_collapses_and_truncates():
    assert summarize_post("  hello   world  ") == "hello world"
    long = "x" * 1000
    out = summarize_post(long, limit=50)
    assert len(out) == 50 and out.endswith("…")


def test_frequency_features_counts_windows():
    now = datetime(2026, 6, 9, 12, 0, 0)
    ts = [
        now,                          # 本則
        now - timedelta(minutes=30),  # 1h 內
        now - timedelta(hours=2),     # 24h 內、非 1h
        now - timedelta(hours=30),    # 超過 24h
    ]
    f = frequency_features(ts, now)
    assert f["posts_last_24h"] == 3
    assert f["posts_last_1h"] == 2


# ---------- 2. judge_post（monkeypatch LLM） ----------
def test_judge_post_parses_llm_json(monkeypatch):
    monkeypatch.setattr(
        political.llm, "complete",
        lambda client, messages, **kw: '{"label":"bearish","score":-70,"reason":"關稅升溫"}',
    )
    out = judge_post(object(), "Big new tariffs on imports!")
    assert out["label"] == "bearish"
    assert out["score"] == -70
    assert "關稅" in out["reason"]


def test_judge_post_empty_is_neutral():
    assert judge_post(object(), "   ")["label"] == "neutral"


def test_judge_post_llm_error_is_neutral(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("ollama down")
    monkeypatch.setattr(political.llm, "complete", _boom)
    out = judge_post(object(), "something")
    assert out["label"] == "neutral" and out["score"] == 0


# ---------- 3. event_to_sentiment / latest_event_sentiment ----------
def test_event_to_sentiment_from_dict():
    s = event_to_sentiment({"label": "bearish", "score": -50, "reason": "x"})
    assert s == {"label": "bearish", "score": -50, "reason": "x"}
    assert event_to_sentiment(None) is None


def test_latest_event_sentiment_newest_and_staleness(tmp_path):
    db = _session(tmp_path)
    now = datetime(2026, 6, 9, 12, 0, 0)
    # 舊的偏多、新的偏空 → 取最新（偏空）
    db.add_all([
        PoliticalEvent(author="t", label="bullish", score=30, reason="old", posted_at=now - timedelta(hours=5)),
        PoliticalEvent(author="t", label="bearish", score=-60, reason="new", posted_at=now - timedelta(hours=1)),
    ])
    db.commit()
    s = latest_event_sentiment(db, max_age_hours=24, now=now)
    assert s["label"] == "bearish" and s["score"] == -60

    # 太舊（max_age 0.5h，最新事件在 1h 前）→ 退場回 None
    assert latest_event_sentiment(db, max_age_hours=0.5, now=now) is None


def test_latest_event_sentiment_none_when_empty(tmp_path):
    db = _session(tmp_path)
    assert latest_event_sentiment(db, now=datetime(2026, 6, 9, 12, 0, 0)) is None


# ---------- 4. ★ political_size_factor bridge ----------
def test_bridge_disabled_passes_through(tmp_path):
    db = _session(tmp_path)
    # 即使有偏空事件，旗標關 → 一律放行（不影響現行下單）
    db.add(PoliticalEvent(author="t", label="bearish", score=-90, reason="x", posted_at=datetime.now()))
    db.commit()
    out = political_size_factor(db, enabled=False)
    assert out["brake"] is False and out["size_factor"] == 1.0


def test_bridge_enabled_bearish_brakes(tmp_path):
    db = _session(tmp_path)
    now = datetime.now()
    db.add(PoliticalEvent(author="t", label="bearish", score=-90, reason="重大負面", posted_at=now))
    db.commit()
    out = political_size_factor(db, enabled=True, now=now)
    # 偏空 → 接 event_risk 的否決語意：不開新倉（size_factor=0）
    assert out["brake"] is True
    assert out["size_factor"] == 0.0


def test_bridge_enabled_no_event_no_brake(tmp_path):
    db = _session(tmp_path)
    out = political_size_factor(db, enabled=True, now=datetime.now())
    # 沒政治資料 → best-effort 不煞車（離線不阻斷）
    assert out["brake"] is False and out["size_factor"] == 1.0


# ---------- 5. runner glue _handle_message ----------
def test_handle_message_records_and_filters(monkeypatch, tmp_path):
    db = _session(tmp_path)
    monkeypatch.setattr(
        political.llm, "get_client", lambda: object(),
    )
    monkeypatch.setattr(political.llm, "cloud_blocked", lambda: False)
    monkeypatch.setattr(
        political.llm, "complete",
        lambda client, messages, **kw: '{"label":"bearish","score":-80,"reason":"tariffs"}',
    )
    monkeypatch.setattr(political_watcher.notifier, "notify", lambda msg: None)
    # 無作者過濾
    monkeypatch.setattr(political_watcher.settings, "POLITICAL_AUTHOR_FILTER", "")

    from collections import defaultdict
    history = defaultdict(list)
    now = datetime.now()
    verdict = political_watcher._handle_message(
        content="Massive tariffs incoming",
        author_name="realDonaldTrump",
        channel_name="trump-mirror",
        posted_at=now,
        history=history,
        db=db,
    )
    assert verdict["label"] == "bearish"
    rows = db.query(PoliticalEvent).all()
    assert len(rows) == 1
    assert rows[0].author == "realDonaldTrump"
    assert rows[0].posts_last_24h == 1

    # 作者過濾擋掉不符的作者 → 不落表
    monkeypatch.setattr(political_watcher.settings, "POLITICAL_AUTHOR_FILTER", "trump")
    out = political_watcher._handle_message(
        content="hi", author_name="someone_else", channel_name="c",
        posted_at=now, history=history, db=db,
    )
    assert out is None
    assert db.query(PoliticalEvent).count() == 1  # 沒新增


# ---------- 5b. 啟動回補：防重 + 該不該收 ----------
def test_event_exists_dedup(tmp_path):
    """同 (author, posted_at) 已落表 → True；不同 → False（回補防重鍵）。"""
    db = _session(tmp_path)
    now = datetime.now()
    record_event(
        db, source="discord:c", author="realDonaldTrump", text="tariffs",
        posted_at=now, verdict={"label": "bearish", "score": -80, "reason": "x"},
    )
    assert political.event_exists(db, author="realDonaldTrump", posted_at=now) is True
    assert political.event_exists(db, author="realDonaldTrump", posted_at=now + timedelta(seconds=1)) is False
    assert political.event_exists(db, author="someone_else", posted_at=now) is False


def test_should_backfill_message(monkeypatch):
    """回補只收「有文字 + 過作者過濾」的訊息；空白 / 純圖片（空文字）不收。"""
    monkeypatch.setattr(political_watcher.settings, "POLITICAL_AUTHOR_FILTER", "trump")
    assert political_watcher._should_backfill_message("Big news", "TrumpTruthSocial_Bot") is True
    assert political_watcher._should_backfill_message("", "TrumpTruthSocial_Bot") is False
    assert political_watcher._should_backfill_message("   ", "TrumpTruthSocial_Bot") is False
    assert political_watcher._should_backfill_message("Big news", "someone_else") is False
    # 過濾留空 = 收全頻道
    monkeypatch.setattr(political_watcher.settings, "POLITICAL_AUTHOR_FILTER", "")
    assert political_watcher._should_backfill_message("hello", "anyone") is True
    # 內容指紋防回音：自己警報 / 心跳的固定開頭不收（舊 webhook 留在頻道的歷史警報）
    assert political_watcher._should_backfill_message("🏛️ 政治風險訊號：xxx 偏空", "anyone") is False
    assert political_watcher._should_backfill_message("💓 [心跳] 2026-06-12 系統存活", "anyone") is False


def test_own_notification_guard():
    """自我回饋防護：自己通知 webhook 發的訊息要認得出來、不能吃。"""
    wid = political_watcher._notifier_webhook_id(
        "https://discord.com/api/webhooks/123456789/secret-token"
    )
    assert wid == "123456789"
    # 同 webhook id（不論 int / str）→ 是自己的通知 → 擋
    assert political_watcher._is_own_notification(123456789, wid) is True
    assert political_watcher._is_own_notification("123456789", wid) is True
    # 不同 webhook（鏡像 bot）/ 非 webhook 訊息 → 放行
    assert political_watcher._is_own_notification(999, wid) is False
    assert political_watcher._is_own_notification(None, wid) is False
    # 沒設通知 webhook → 不過濾
    assert political_watcher._notifier_webhook_id("") == ""
    assert political_watcher._is_own_notification(123, "") is False


# ---------- 6. GET /political/events + /political/risk ----------
@contextmanager
def _isolated_client(tmp_path):
    from backend.main import app

    engine = create_engine(
        f"sqlite:///{tmp_path / 'app_political.db'}",
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


def test_political_api_events_and_risk(monkeypatch, tmp_path):
    with _isolated_client(tmp_path) as (client, TestingSession):
        db = TestingSession()
        try:
            now = datetime.now()
            db.add_all([
                PoliticalEvent(author="t", label="bearish", score=-60, reason="a", posted_at=now),
                PoliticalEvent(author="t", label="neutral", score=0, reason="b", posted_at=now - timedelta(hours=1)),
            ])
            db.commit()
        finally:
            db.close()

        # 列出（新到舊）
        rows = client.get("/political/events").json()
        assert [r["label"] for r in rows] == ["bearish", "neutral"]

        # label 篩選
        bearish = client.get("/political/events?label=bearish").json()
        assert len(bearish) == 1 and bearish[0]["score"] == -60

        # /political/risk：預設旗標關 → 放行（size_factor=1.0），不影響下單
        monkeypatch.setattr(political.settings, "POLITICAL_ENABLED", False)
        risk = client.get("/political/risk").json()
        assert risk["brake"] is False and risk["size_factor"] == 1.0
