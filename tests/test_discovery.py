"""
探勘橋測試（Phase 12 step-02）
================================
涵蓋（全程 monkeypatch llm，不連網、不開 Ollama）：
1. 純函式 triage_find：正常提案 / 亂回 JSON / 回 null / 非法策略鍵 / composite /
   參數非數字 / 信心不足。
2. run_discovery_batch：
   - 正常提案 → StrategyKnowledge candidate 建立、find 標 built + knowledge_id 回填。
   - 不相關素材 → find 標 discarded + triage_note。
   - LLM 連不上（complete 丟例外）→ 整批跳過、find 維持 new。
   - 冪等：已 built/discarded 的 find 不再 triage。
   - DISCOVERY_BATCH_SIZE 上限生效。
   - DISCOVERY_ENABLED=false → no-op。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_discovery.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import RawStrategyFind
from backend.models.strategy_knowledge import StrategyKnowledge
from backend.services import discovery
from backend.services.discovery import triage_find, run_discovery_batch


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'discovery.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _find(**kw):
    """組一個最小可用的素材物件（純函式測試用，不碰 DB）。"""
    base = dict(title="RSI mean reversion", summary="Buy when RSI < 30.")
    base.update(kw)
    return SimpleNamespace(**base)


def _enable(monkeypatch, batch_size=5):
    monkeypatch.setattr(discovery.settings, "DISCOVERY_ENABLED", True)
    monkeypatch.setattr(discovery.settings, "DISCOVERY_BATCH_SIZE", batch_size)
    # 測試環境不見得有設 LLM：強制視為本機可用
    monkeypatch.setattr(discovery.llm, "cloud_blocked", lambda: False)
    monkeypatch.setattr(discovery.llm, "get_client", lambda: object())


def _seed_finds(db, n, status="new"):
    for i in range(n):
        db.add(RawStrategyFind(
            source="t", source_url=f"https://t.example.com/{status}-{i}",
            title=f"Article {i}", summary="Buy when RSI < 30.", status=status,
        ))
    db.commit()


# ---------- 1. triage_find（純函式） ----------
def test_triage_find_valid_proposal():
    reply = '{"strategy_key": "rsi", "params": {"period": 14}, "confidence": 0.8, "reason": "講 RSI 超賣"}'
    out = triage_find(_find(), reply)
    assert out == {"strategy_key": "rsi", "params": {"period": 14},
                   "confidence": 0.8, "reason": "講 RSI 超賣"}


def test_triage_find_tolerates_surrounding_text():
    reply = '好的，分析如下：{"strategy_key": "rsi", "params": {"period": 21}, "confidence": 0.9, "reason": "x"} 以上'
    out = triage_find(_find(), reply)
    assert out is not None and out["params"] == {"period": 21}


def test_triage_find_rejects_garbage_and_null():
    assert triage_find(_find(), "not json at all") is None
    assert triage_find(_find(), "") is None
    assert triage_find(_find(), "null") is None  # 模型判定不相關
    assert triage_find(_find(), '{"strategy_key": "rsi"}') is None  # 缺 params


def test_triage_find_rejects_unknown_key_and_composite():
    assert triage_find(_find(), '{"strategy_key": "nope", "params": {"a": 1}, "confidence": 0.9}') is None
    assert triage_find(_find(), '{"strategy_key": "composite", "params": {"a": 1}, "confidence": 0.9}') is None


def test_triage_find_rejects_non_numeric_params_and_low_confidence():
    # 參數塞字串（例如模型想回程式碼）= 違反「只提參數」合約
    assert triage_find(_find(), '{"strategy_key": "rsi", "params": {"code": "def f(): ..."}, "confidence": 0.9}') is None
    # 信心不足不採用
    assert triage_find(_find(), '{"strategy_key": "rsi", "params": {"period": 14}, "confidence": 0.2}') is None


# ---------- 2. run_discovery_batch ----------
def test_batch_builds_candidate_and_marks_find(monkeypatch, tmp_path):
    db = _session(tmp_path)
    _seed_finds(db, 1)
    _enable(monkeypatch)
    monkeypatch.setattr(
        discovery.llm, "complete",
        lambda client, messages, max_tokens=512:
            '{"strategy_key": "rsi", "params": {"period": 14}, "confidence": 0.8, "reason": "ok"}',
    )

    stats = run_discovery_batch(db)
    assert stats["built"] == 1 and stats["discarded"] == 0

    find = db.query(RawStrategyFind).first()
    k = db.query(StrategyKnowledge).first()
    assert k is not None and k.status == "candidate" and k.strategy_key == "rsi"
    assert find.status == "built"
    assert find.knowledge_id == k.id  # 審計：回查得到產了哪筆
    assert "rsi" in find.triage_note


def test_batch_discards_irrelevant(monkeypatch, tmp_path):
    db = _session(tmp_path)
    _seed_finds(db, 1)
    _enable(monkeypatch)
    monkeypatch.setattr(discovery.llm, "complete",
                        lambda client, messages, max_tokens=512: "null")

    stats = run_discovery_batch(db)
    assert stats["discarded"] == 1 and stats["built"] == 0
    find = db.query(RawStrategyFind).first()
    assert find.status == "discarded" and find.triage_note
    assert db.query(StrategyKnowledge).count() == 0


def test_batch_skips_all_when_llm_down(monkeypatch, tmp_path):
    db = _session(tmp_path)
    _seed_finds(db, 3)
    _enable(monkeypatch)

    def _boom(client, messages, max_tokens=512):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(discovery.llm, "complete", _boom)
    stats = run_discovery_batch(db)
    assert stats["built"] == 0 and stats["discarded"] == 0
    # 整批跳過：素材全部維持 new，不誤殺、下一輪再來
    assert db.query(RawStrategyFind).filter_by(status="new").count() == 3


def test_batch_idempotent_skips_processed(monkeypatch, tmp_path):
    db = _session(tmp_path)
    _seed_finds(db, 1, status="built")
    _seed_finds(db, 1, status="discarded")
    _enable(monkeypatch)
    calls = {"n": 0}

    def _count(client, messages, max_tokens=512):
        calls["n"] += 1
        return "null"

    monkeypatch.setattr(discovery.llm, "complete", _count)
    stats = run_discovery_batch(db)
    # 沒有 status=new 的素材 → LLM 一次都不該被呼叫
    assert calls["n"] == 0 and stats["processed"] == 0


def test_batch_size_cap(monkeypatch, tmp_path):
    db = _session(tmp_path)
    _seed_finds(db, 5)
    _enable(monkeypatch, batch_size=2)
    monkeypatch.setattr(discovery.llm, "complete",
                        lambda client, messages, max_tokens=512: "null")

    stats = run_discovery_batch(db)
    assert stats["processed"] == 2  # 一輪最多 BATCH_SIZE 筆
    assert db.query(RawStrategyFind).filter_by(status="new").count() == 3


def test_disabled_is_noop(monkeypatch, tmp_path):
    db = _session(tmp_path)
    _seed_finds(db, 2)
    monkeypatch.setattr(discovery.settings, "DISCOVERY_ENABLED", False)
    called = {"llm": 0}
    monkeypatch.setattr(discovery.llm, "get_client",
                        lambda: called.__setitem__("llm", called["llm"] + 1))

    stats = run_discovery_batch(db)
    assert stats == {"processed": 0, "built": 0, "discarded": 0, "skipped": 0}
    assert called["llm"] == 0  # 連 LLM client 都不該建
    assert db.query(RawStrategyFind).filter_by(status="new").count() == 2
