"""
Bot 教訓摘要端點測試（Phase 15）
=================================
涵蓋 POST /chat/bot-lessons 的安全閘與往返（全程不連網、不真打 LLM）：
- 沒設 LLM（LLM_MODEL 空）→ 400。
- LLM 指向雲端又沒開外送閘 → 400（在查 DB / 打 LLM 之前擋下）。
- 找不到 Bot → 404（閘都過了才查 DB，仍在 _complete 之前）。
- 正常：stub 掉 _complete，回 200 + lessons。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_bot_lessons.py -q
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
from fastapi.testclient import TestClient

import backend.routers.chat as chat
from backend.database import Base
from backend.models import Bot, DecisionLog
from backend.models.decision_log import ACTION_BOUGHT


def _session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'lessons.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _local_llm(monkeypatch):
    """強制本機 LLM 設定（_get_client 非 None、非 cloud-blocked），不受 .env 影響。"""
    monkeypatch.setattr(chat.settings, "LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setattr(chat.settings, "LLM_MODEL", "llama3.1")
    monkeypatch.setattr(chat.settings, "LLM_ALLOW_CLOUD", False)


def test_no_llm_returns_400(monkeypatch):
    monkeypatch.setattr(chat.settings, "LLM_MODEL", "")  # _get_client → None
    from backend.main import app
    with TestClient(app) as c:
        r = c.post("/chat/bot-lessons", json={"bot_id": 1})
        assert r.status_code == 400
        assert "LLM" in r.json()["detail"]


def test_cloud_blocked_returns_400(monkeypatch):
    monkeypatch.setattr(chat.settings, "LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(chat.settings, "LLM_MODEL", "gpt-4o")
    monkeypatch.setattr(chat.settings, "LLM_ALLOW_CLOUD", False)
    from backend.main import app
    with TestClient(app) as c:
        r = c.post("/chat/bot-lessons", json={"bot_id": 1})
        assert r.status_code == 400


def test_missing_bot_returns_404(tmp_path, monkeypatch):
    _local_llm(monkeypatch)
    monkeypatch.setattr(chat, "SessionLocal", _session(tmp_path))  # 空庫 → 查無 bot
    from backend.main import app
    with TestClient(app) as c:
        r = c.post("/chat/bot-lessons", json={"bot_id": 99999})
        assert r.status_code == 404


def test_success_with_stubbed_llm(tmp_path, monkeypatch):
    _local_llm(monkeypatch)
    TestSession = _session(tmp_path)
    monkeypatch.setattr(chat, "SessionLocal", TestSession)
    monkeypatch.setattr(chat, "_complete", lambda *a, **k: "教訓：量縮時別追高。")

    s = TestSession()
    bot = Bot(name="教訓Bot", strategy="rsi", symbol="AAPL", params={"period": 14})
    s.add(bot)
    s.commit()
    bid = bot.id
    s.add(DecisionLog(
        bot_id=bid, symbol="AAPL", signal="buy", reason="RSI<30",
        price=180.0, volume=1234567.0, qty=5.0,
        indicators={"rsi": 28.1}, action=ACTION_BOUGHT,
    ))
    s.commit()
    s.close()

    from backend.main import app
    with TestClient(app) as c:
        r = c.post("/chat/bot-lessons", json={"bot_id": bid})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["bot_id"] == bid
        assert "教訓" in body["lessons"]
        assert body["stub"] is False
