"""
候選自動批次驗證測試（Phase 12 step-03）
==========================================
涵蓋（全程 monkeypatch evolution.validate_candidate，不回測、不連網）：
1. 通過 → validated（並驗 symbol 來自 AUTO_VALIDATE_SYMBOL）。
2. verdict 拒絕 → rejected（oos_metrics 含 "verdict"、無 "auto_validate"）。
3. 丟例外 → 維持 candidate + 失敗計數 1（不放行也不誤殺）。
4. 連續失敗達 3 次 → rejected + rejected_by=auto_validate（重查 DB 驗 JSON 重新賦值持久化）。
5. 失敗 2 次後成功 → "auto_validate" 計數鍵消失（evolution 整顆覆蓋 oos_metrics）。
6. AUTO_VALIDATE_BATCH_SIZE 上限生效。
7. 冪等：已 validated/rejected 的不再送驗。
8. AUTO_VALIDATE_ENABLED=false → no-op。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_auto_validate.py -q
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
from backend.models.strategy_knowledge import StrategyKnowledge
from backend.services import auto_validate
from backend.services.auto_validate import run_auto_validate


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'auto_validate.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _enable(monkeypatch, batch_size=3, symbols="SPY,AAPL,JPM"):
    monkeypatch.setattr(auto_validate.settings, "AUTO_VALIDATE_ENABLED", True)
    monkeypatch.setattr(auto_validate.settings, "AUTO_VALIDATE_BATCH_SIZE", batch_size)
    # 驗證標的現在統一吃籃子（auto_validate_symbols property 拆這個逗號字串）
    monkeypatch.setattr(auto_validate.settings, "AUTO_VALIDATE_SYMBOLS", symbols)


def _seed(db, n=1, status="candidate", oos_metrics=None):
    rows = []
    for i in range(n):
        k = StrategyKnowledge(
            name=f"候選 {status}-{i}", strategy_key="rsi",
            params={"period": 14}, status=status, oos_metrics=oos_metrics,
        )
        db.add(k)
        rows.append(k)
    db.commit()
    return rows


def test_pass_marks_validated(monkeypatch, tmp_path):
    db = _session(tmp_path)
    _seed(db)
    _enable(monkeypatch, symbols="QQQ,DIA,IWM")
    seen = {}

    def _fake(row, symbols, days=365, **kw):
        seen["symbols"] = symbols
        row.status = "validated"
        row.oos_metrics = {"expected_value": 1.2, "verdict": {"worth_it": True}}
        return {"id": row.id, "status": "validated", "oos_metrics": row.oos_metrics}

    monkeypatch.setattr(auto_validate.evolution, "validate_candidate", _fake)
    stats = run_auto_validate(db)
    assert stats == {"processed": 1, "validated": 1, "rejected": 0, "failed": 0}
    # 驗證標的統一吃籃子（candidate 無自帶 symbol；property 拆逗號 + 大寫）
    assert seen["symbols"] == ["QQQ", "DIA", "IWM"]
    assert db.query(StrategyKnowledge).first().status == "validated"


def test_verdict_reject_marks_rejected(monkeypatch, tmp_path):
    db = _session(tmp_path)
    _seed(db)
    _enable(monkeypatch)

    def _fake(row, symbol, days=365, **kw):
        row.status = "rejected"
        row.oos_metrics = {"expected_value": -3.0, "verdict": {"worth_it": False}}
        return {"id": row.id, "status": "rejected", "oos_metrics": row.oos_metrics}

    monkeypatch.setattr(auto_validate.evolution, "validate_candidate", _fake)
    stats = run_auto_validate(db)
    assert stats["rejected"] == 1 and stats["failed"] == 0
    row = db.query(StrategyKnowledge).first()
    # evolution 判的拒絕：有 verdict、沒有操作性失敗鍵（兩種 rejected 可稽核區分）
    assert "verdict" in row.oos_metrics and "auto_validate" not in row.oos_metrics


def test_exception_keeps_candidate_records_failure(monkeypatch, tmp_path):
    db = _session(tmp_path)
    _seed(db)
    _enable(monkeypatch)

    def _boom(row, symbol, days=365, **kw):
        raise ValueError("抓不到歷史資料")

    monkeypatch.setattr(auto_validate.evolution, "validate_candidate", _boom)
    stats = run_auto_validate(db)
    assert stats == {"processed": 1, "validated": 0, "rejected": 0, "failed": 1}
    row = db.query(StrategyKnowledge).first()
    # 不放行也不誤殺：維持 candidate，下批重試
    assert row.status == "candidate"
    assert row.oos_metrics["auto_validate"]["failures"] == 1
    assert "抓不到" in row.oos_metrics["auto_validate"]["last_error"]


def test_three_strikes_rejects_with_reason(monkeypatch, tmp_path):
    db = _session(tmp_path)
    _seed(db, oos_metrics={"auto_validate": {"failures": 2, "last_error": "x"}})
    _enable(monkeypatch)

    def _boom(row, symbol, days=365, **kw):
        raise ValueError("第三次也炸")

    monkeypatch.setattr(auto_validate.evolution, "validate_candidate", _boom)
    stats = run_auto_validate(db)
    assert stats["failed"] == 1 and stats["rejected"] == 1

    # 重開 session 重查：釘住「JSON 欄位重新賦值才持久化」的行為
    db.expire_all()
    row = db.query(StrategyKnowledge).first()
    assert row.status == "rejected"
    info = row.oos_metrics["auto_validate"]
    assert info["failures"] == 3
    assert info["rejected_by"] == "auto_validate"  # 操作性放棄，非策略不好
    assert info["rejected_at"]
    assert "verdict" not in row.oos_metrics


def test_success_after_failures_clears_counter(monkeypatch, tmp_path):
    db = _session(tmp_path)
    _seed(db, oos_metrics={"auto_validate": {"failures": 2, "last_error": "x"}})
    _enable(monkeypatch)

    def _fake(row, symbol, days=365, **kw):
        row.status = "validated"
        row.oos_metrics = {"expected_value": 0.8, "verdict": {"worth_it": True}}
        return {"id": row.id, "status": "validated", "oos_metrics": row.oos_metrics}

    monkeypatch.setattr(auto_validate.evolution, "validate_candidate", _fake)
    run_auto_validate(db)
    row = db.query(StrategyKnowledge).first()
    # evolution 成功時整顆覆蓋 oos_metrics → 失敗計數自然歸零
    assert row.status == "validated" and "auto_validate" not in row.oos_metrics


def test_batch_size_cap(monkeypatch, tmp_path):
    db = _session(tmp_path)
    _seed(db, n=5)
    _enable(monkeypatch, batch_size=2)
    calls = {"n": 0}

    def _fake(row, symbol, days=365, **kw):
        calls["n"] += 1
        row.status = "validated"
        row.oos_metrics = {"expected_value": 1.0, "verdict": {}}
        return {"id": row.id, "status": "validated", "oos_metrics": row.oos_metrics}

    monkeypatch.setattr(auto_validate.evolution, "validate_candidate", _fake)
    stats = run_auto_validate(db)
    assert calls["n"] == 2 and stats["processed"] == 2  # 一輪最多 BATCH_SIZE 筆
    assert db.query(StrategyKnowledge).filter_by(status="candidate").count() == 3


def test_idempotent_skips_validated_and_rejected(monkeypatch, tmp_path):
    db = _session(tmp_path)
    _seed(db, status="validated")
    _seed(db, status="rejected")
    _enable(monkeypatch)
    calls = {"n": 0}

    def _count(row, symbol, days=365, **kw):
        calls["n"] += 1
        return {"status": "validated"}

    monkeypatch.setattr(auto_validate.evolution, "validate_candidate", _count)
    stats = run_auto_validate(db)
    # 沒有 candidate → 一次都不該驗（已定案的永不重驗）
    assert calls["n"] == 0
    assert stats == {"processed": 0, "validated": 0, "rejected": 0, "failed": 0}


def test_disabled_is_noop(monkeypatch, tmp_path):
    db = _session(tmp_path)
    _seed(db, n=2)
    monkeypatch.setattr(auto_validate.settings, "AUTO_VALIDATE_ENABLED", False)
    calls = {"n": 0}

    def _count(row, symbol, days=365, **kw):
        calls["n"] += 1
        return {"status": "validated"}

    monkeypatch.setattr(auto_validate.evolution, "validate_candidate", _count)
    stats = run_auto_validate(db)
    assert calls["n"] == 0
    assert stats == {"processed": 0, "validated": 0, "rejected": 0, "failed": 0}
    assert db.query(StrategyKnowledge).filter_by(status="candidate").count() == 2


def test_force_bypasses_disabled(monkeypatch, tmp_path):
    db = _session(tmp_path)
    _seed(db)
    # ENABLED=false，但 force=True（手動「跑一次」端點）仍驗；判準不變
    monkeypatch.setattr(auto_validate.settings, "AUTO_VALIDATE_ENABLED", False)
    monkeypatch.setattr(auto_validate.settings, "AUTO_VALIDATE_BATCH_SIZE", 3)
    monkeypatch.setattr(auto_validate.settings, "AUTO_VALIDATE_SYMBOLS", "SPY,AAPL")

    def _fake(row, symbols, days=365, **kw):
        row.status = "validated"
        row.oos_metrics = {"expected_value": 1.0, "verdict": {}}
        return {"id": row.id, "status": "validated", "oos_metrics": row.oos_metrics}

    monkeypatch.setattr(auto_validate.evolution, "validate_candidate", _fake)
    stats = run_auto_validate(db, force=True)
    assert stats["processed"] == 1 and stats["validated"] == 1
