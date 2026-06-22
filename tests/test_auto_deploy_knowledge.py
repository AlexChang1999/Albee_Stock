"""
知識庫策略 → Paper Bot 自動部署測試
=====================================
涵蓋（自足：temp sqlite + create_all；monkeypatch 掉 explorations 檔案寫入）：

deploy_curated_to_bots（共用部署函式）：
1. 建 N 個 Paper Bot（每 symbol 一個）、strategy/params 映射、promotion_status=paper、戳 deployed_at。
2. activate 旗標：True→is_active=True（自動掛網跑）、False→False（人再 start）。
3. symbols 去重；全空白 → ValueError。

run_auto_deploy_knowledge（批次器）：
4. curated + deployed_at NULL → 建 bot、戳 deployed_at；**再跑一次冪等**（deployed_at 已戳 → 不重建）。
5. ENABLED=false → no-op。
6. AUTO_DEPLOY_FROM_STATUS 過濾（非目標狀態不碰）。
7. MAX_PER_RUN 上限。
8. SYMBOLS 為空 → no-op（不建任何 bot）。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_auto_deploy_knowledge.py -q
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

from backend.database import Base
from backend.models import Bot
from backend.models.strategy_knowledge import StrategyKnowledge
from backend.services import knowledge_deploy, auto_deploy_knowledge
from backend.services.knowledge_deploy import deploy_curated_to_bots
from backend.services.auto_deploy_knowledge import run_auto_deploy_knowledge


@pytest.fixture(autouse=True)
def _no_explorations(monkeypatch):
    """部署軌跡寫檔在單元測試裡沒意義，monkeypatch 掉避免碰檔案系統。"""
    monkeypatch.setattr(knowledge_deploy.explorations, "write_knowledge_note",
                        lambda *a, **k: "stub.md")


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'auto_deploy.db'}")
    Base.metadata.create_all(engine)  # model 已含 deployed_at，自動建出
    return sessionmaker(bind=engine)()


def _seed(db, status="curated", n=1, deployed=False):
    rows = []
    for i in range(n):
        k = StrategyKnowledge(
            name=f"策略-{status}-{i}", strategy_key="rsi",
            params={"period": 14}, status=status,
        )
        db.add(k)
        rows.append(k)
    db.commit()
    if deployed:
        from datetime import datetime
        for k in rows:
            k.deployed_at = datetime.now()
        db.commit()
    return rows


def _enable(monkeypatch, symbols="SPY,QQQ", status="curated", max_per_run=3):
    s = auto_deploy_knowledge.settings
    monkeypatch.setattr(s, "AUTO_DEPLOY_KNOWLEDGE_ENABLED", True)
    monkeypatch.setattr(s, "AUTO_DEPLOY_KNOWLEDGE_SYMBOLS", symbols)
    monkeypatch.setattr(s, "AUTO_DEPLOY_FROM_STATUS", status)
    monkeypatch.setattr(s, "AUTO_DEPLOY_KNOWLEDGE_MAX_PER_RUN", max_per_run)
    monkeypatch.setattr(s, "AUTO_DEPLOY_KNOWLEDGE_TRADE_AMOUNT", 1000.0)


# ---------- deploy_curated_to_bots（共用函式）----------
def test_deploy_helper_creates_paper_bots(tmp_path):
    db = _session(tmp_path)
    k = _seed(db)[0]
    bots = deploy_curated_to_bots(db, k, ["aapl", "MSFT"], trade_amount=2000.0, activate=False)
    db.commit()
    assert len(bots) == 2
    assert {b.symbol for b in bots} == {"AAPL", "MSFT"}
    for b in bots:
        assert b.strategy == "rsi"
        assert b.params == {"period": 14}
        assert b.trade_amount == 2000.0
        assert b.promotion_status == "paper"
        assert b.is_active is False
    assert k.deployed_at is not None  # 戳了冪等戳記


def test_deploy_helper_activate_true(tmp_path):
    db = _session(tmp_path)
    k = _seed(db)[0]
    bots = deploy_curated_to_bots(db, k, ["SPY"], activate=True)
    db.commit()
    assert bots[0].is_active is True
    assert bots[0].promotion_status == "paper"  # 啟用仍是 paper，不碰真錢


def test_deploy_helper_dedups_and_empty(tmp_path):
    db = _session(tmp_path)
    k = _seed(db)[0]
    bots = deploy_curated_to_bots(db, k, ["AAPL", "aapl", " AAPL "], activate=False)
    db.commit()
    assert len(bots) == 1 and bots[0].symbol == "AAPL"

    with pytest.raises(ValueError):
        deploy_curated_to_bots(db, k, ["  ", ""], activate=False)


# ---------- run_auto_deploy_knowledge（批次器）----------
def test_auto_deploy_creates_and_idempotent(tmp_path, monkeypatch):
    db = _session(tmp_path)
    _seed(db, status="curated", n=1)
    _enable(monkeypatch, symbols="SPY,QQQ")

    stats = run_auto_deploy_knowledge(db)
    assert stats["processed"] == 1
    assert stats["deployed_knowledge"] == 1
    assert stats["bots_created"] == 2  # SPY + QQQ
    assert db.query(Bot).count() == 2
    # 建出的 bot：active paper
    for b in db.query(Bot).all():
        assert b.is_active is True and b.promotion_status == "paper"

    # 再跑一次：deployed_at 已戳 → 不重建（冪等）
    stats2 = run_auto_deploy_knowledge(db)
    assert stats2["processed"] == 0 and stats2["bots_created"] == 0
    assert db.query(Bot).count() == 2


def test_auto_deploy_disabled_noop(tmp_path, monkeypatch):
    db = _session(tmp_path)
    _seed(db, status="curated")
    monkeypatch.setattr(auto_deploy_knowledge.settings, "AUTO_DEPLOY_KNOWLEDGE_ENABLED", False)
    stats = run_auto_deploy_knowledge(db)
    assert stats == {"processed": 0, "deployed_knowledge": 0, "bots_created": 0, "failed": 0}
    assert db.query(Bot).count() == 0


def test_auto_deploy_filters_status(tmp_path, monkeypatch):
    """只部署 AUTO_DEPLOY_FROM_STATUS（預設 curated）；candidate/validated 不碰。"""
    db = _session(tmp_path)
    _seed(db, status="candidate")
    _seed(db, status="validated")
    _enable(monkeypatch, status="curated")
    stats = run_auto_deploy_knowledge(db)
    assert stats["processed"] == 0 and db.query(Bot).count() == 0


def test_auto_deploy_from_validated(tmp_path, monkeypatch):
    """可切 validated 觸發（全自動模式）。"""
    db = _session(tmp_path)
    _seed(db, status="validated")
    _enable(monkeypatch, status="validated", symbols="SPY")
    stats = run_auto_deploy_knowledge(db)
    assert stats["deployed_knowledge"] == 1 and db.query(Bot).count() == 1


def test_auto_deploy_validated_threshold_includes_curated(tmp_path, monkeypatch):
    """門檻語義：from=validated 取「validated 及以上」→ 涵蓋已被人晉升的 curated，
    但不碰較低階的 candidate。"""
    db = _session(tmp_path)
    _seed(db, status="candidate")   # 階 0：不該部署
    _seed(db, status="validated")   # 階 1：該部署
    _seed(db, status="curated")     # 階 2：該部署（驗過再被人晉升，更該上）
    _enable(monkeypatch, status="validated", symbols="SPY", max_per_run=10)
    stats = run_auto_deploy_knowledge(db)
    assert stats["processed"] == 2          # validated + curated
    assert stats["bots_created"] == 2       # 各 1 symbol（SPY）
    # candidate 仍未部署
    assert db.query(StrategyKnowledge).filter(
        StrategyKnowledge.status == "candidate",
        StrategyKnowledge.deployed_at.is_(None),
    ).count() == 1


def test_auto_deploy_max_per_run(tmp_path, monkeypatch):
    db = _session(tmp_path)
    _seed(db, status="curated", n=5)
    _enable(monkeypatch, symbols="SPY", max_per_run=2)
    stats = run_auto_deploy_knowledge(db)
    assert stats["processed"] == 2 and stats["bots_created"] == 2
    # 剩 3 筆未部署
    assert db.query(StrategyKnowledge).filter(StrategyKnowledge.deployed_at.is_(None)).count() == 3


def test_auto_deploy_empty_symbols_noop(tmp_path, monkeypatch):
    db = _session(tmp_path)
    _seed(db, status="curated")
    _enable(monkeypatch, symbols="   ")  # 全空白 → property 回空清單
    stats = run_auto_deploy_knowledge(db)
    assert stats["bots_created"] == 0 and db.query(Bot).count() == 0


def test_force_bypasses_disabled(tmp_path, monkeypatch):
    """ENABLED=false 但 force=True（手動「跑一次」端點）仍部署；★仍只建 paper bot。"""
    db = _session(tmp_path)
    _seed(db, status="curated", n=1)
    _enable(monkeypatch, symbols="SPY")
    monkeypatch.setattr(auto_deploy_knowledge.settings, "AUTO_DEPLOY_KNOWLEDGE_ENABLED", False)
    stats = run_auto_deploy_knowledge(db, force=True)
    assert stats["deployed_knowledge"] == 1 and stats["bots_created"] == 1
    assert all(b.promotion_status == "paper" for b in db.query(Bot).all())


if __name__ == "__main__":
    print("（需 pytest 的 tmp_path / monkeypatch，請用 pytest 執行）")
