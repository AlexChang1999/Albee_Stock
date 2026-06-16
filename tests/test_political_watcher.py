"""
政治專討員 — 雲端洗版根治測試
================================
針對「修雲端狂洗版 + 漏抓」的根治改動，涵蓋：
1. 回補路徑 notify_on_alert=False → 偏空也不發通知（殺重啟洗版）。
2. 即時路徑 notify_on_alert=True → 偏空發一則通知。
3. 同一則重判（撞 (author, posted_at) 唯一鍵 / 已存在）→ 不重發通知。
4. _alert_allowed 同作者節流：冷卻期內第二則回 False；cooldown<=0 不節流。
5. record_event 撞唯一鍵 → 回 None、不拋例外、不重複落表。
6. latest_event_time：空表回 None、有資料回最大 posted_at。

不連網、不連 Discord：臨時 SQLite + monkeypatch LLM。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_political_watcher.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import PoliticalEvent
from backend.services import political
from backend.services.political import record_event, latest_event_time
from backend.bots import political_watcher


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'political_watcher.db'}")
    Base.metadata.create_all(engine)  # 含 (author, posted_at) 唯一鍵
    return sessionmaker(bind=engine)()


def _patch_llm_bearish(monkeypatch):
    """讓 judge_post_best_effort 一律回偏空（離線、可控）。"""
    monkeypatch.setattr(political.llm, "get_client", lambda: object())
    monkeypatch.setattr(political.llm, "cloud_blocked", lambda: False)
    monkeypatch.setattr(
        political.llm, "complete",
        lambda client, messages, **kw: '{"label":"bearish","score":-80,"reason":"tariffs"}',
    )
    monkeypatch.setattr(political_watcher.settings, "POLITICAL_AUTHOR_FILTER", "")


def _capture_notify(monkeypatch):
    """攔截 notifier.notify，回收到的訊息清單。"""
    sent = []
    monkeypatch.setattr(political_watcher.notifier, "notify", lambda msg: sent.append(msg))
    return sent


# ---------- 1. 回補路徑不發通知 ----------
def test_backfill_path_does_not_notify(monkeypatch, tmp_path):
    _patch_llm_bearish(monkeypatch)
    sent = _capture_notify(monkeypatch)
    db = _session(tmp_path)

    verdict = political_watcher._handle_message(
        content="Massive tariffs incoming", author_name="trump",
        channel_name="c", posted_at=datetime.now(),
        history=defaultdict(list), db=db, notify_on_alert=False,
    )
    assert verdict["label"] == "bearish"          # 有判讀、有落表
    assert db.query(PoliticalEvent).count() == 1
    assert sent == []                              # 但回補不發通知


# ---------- 2. 即時路徑發一則通知 ----------
def test_live_path_notifies_once(monkeypatch, tmp_path):
    _patch_llm_bearish(monkeypatch)
    sent = _capture_notify(monkeypatch)
    db = _session(tmp_path)

    political_watcher._handle_message(
        content="Massive tariffs incoming", author_name="trump",
        channel_name="c", posted_at=datetime.now(),
        history=defaultdict(list), db=db, notify_on_alert=True, alert_state={},
    )
    assert len(sent) == 1
    assert "政治風險訊號" in sent[0]


# ---------- 3. 重判同一則（已存在）不重發 ----------
def test_duplicate_event_not_notified(monkeypatch, tmp_path):
    _patch_llm_bearish(monkeypatch)
    sent = _capture_notify(monkeypatch)
    db = _session(tmp_path)
    now = datetime.now()
    alert_state = {}

    # 先落一筆（模擬已收過）
    record_event(db, source="discord:c", author="trump", text="tariffs",
                 posted_at=now, verdict={"label": "bearish", "score": -80, "reason": "x"})

    # 即時又收到同 (author, posted_at) → record_event 撞唯一鍵回 None → 不發通知
    political_watcher._handle_message(
        content="tariffs again", author_name="trump", channel_name="c",
        posted_at=now, history=defaultdict(list), db=db,
        notify_on_alert=True, alert_state=alert_state,
    )
    assert sent == []
    assert db.query(PoliticalEvent).count() == 1   # 沒重複落表


# ---------- 4. 同作者節流純函式 ----------
def test_alert_cooldown_throttles_same_author():
    now = datetime(2026, 6, 15, 12, 0, 0)
    state = {}
    assert political_watcher._alert_allowed("trump", now, state, 10) is True
    # 冷卻期內（5 分鐘後）同作者 → 擋
    assert political_watcher._alert_allowed("trump", now + timedelta(minutes=5), state, 10) is False
    # 冷卻過後（11 分鐘）→ 放行
    assert political_watcher._alert_allowed("trump", now + timedelta(minutes=11), state, 10) is True
    # 不同作者不互相影響
    assert political_watcher._alert_allowed("biden", now + timedelta(minutes=5), state, 10) is True


def test_alert_cooldown_disabled_when_zero():
    now = datetime(2026, 6, 15, 12, 0, 0)
    state = {}
    assert political_watcher._alert_allowed("trump", now, state, 0) is True
    assert political_watcher._alert_allowed("trump", now, state, 0) is True  # 不節流


# ---------- 5. record_event 撞唯一鍵 ----------
def test_record_event_duplicate_returns_none(tmp_path):
    db = _session(tmp_path)
    now = datetime.now()
    v = {"label": "bearish", "score": -80, "reason": "x"}
    first = record_event(db, source="discord:c", author="trump", text="a", posted_at=now, verdict=v)
    assert first is not None
    # 同 (author, posted_at) 再落 → 回 None、不拋例外
    second = record_event(db, source="discord:c", author="trump", text="b", posted_at=now, verdict=v)
    assert second is None
    assert db.query(PoliticalEvent).count() == 1


# ---------- 6. latest_event_time ----------
def test_latest_event_time(tmp_path):
    db = _session(tmp_path)
    assert latest_event_time(db) is None            # 空表

    t1 = datetime(2026, 6, 15, 10, 0, 0)
    t2 = datetime(2026, 6, 15, 12, 0, 0)
    v = {"label": "neutral", "score": 0, "reason": ""}
    record_event(db, source="c", author="a", text="x", posted_at=t1, verdict=v)
    record_event(db, source="c", author="b", text="y", posted_at=t2, verdict=v)
    assert latest_event_time(db) == t2              # 取最新
