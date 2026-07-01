"""
探勘管線手動觸發 API 測試（Phase 14）
=======================================
涵蓋 /discovery 路由的薄觸發層 + 安全閘（不連網、不開 LLM）：
- POST /discovery/run / validate-batch / auto-deploy：force 觸發，空庫回 200 + 統計零。
- POST /discovery/triage/{id}：找不到素材 → 404；非 new/triaged → 400（都在 LLM 閘之前擋下）。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_discovery_api.py -q
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
from backend.models import RawStrategyFind


@contextmanager
def _isolated_client(tmp_path):
    from backend.main import app

    engine = create_engine(
        f"sqlite:///{tmp_path / 'app_discovery.db'}",
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


def test_pipeline_triggers_empty_db(tmp_path):
    with _isolated_client(tmp_path) as (client, _):
        # 空庫 + force：run/auto-deploy 同步回 200 + 統計 dict；validate-batch 非同步回 202
        # （都不早退、不連網、無候選可處理）。
        r1 = client.post("/discovery/run")
        assert r1.status_code == 200 and "built" in r1.json()
        # validate-batch 是 BackgroundTasks（38 籃子 walk-forward 太久，避免 HTTP 逾時），
        # 立刻回 202 + {"status": "started"}；驗證在背景跑，進度靠輪詢 /company/overview。
        r2 = client.post("/discovery/validate-batch")
        assert r2.status_code == 202 and r2.json().get("status") == "started"
        r3 = client.post("/discovery/auto-deploy")
        assert r3.status_code == 200 and "bots_created" in r3.json()


def test_triage_missing_and_bad_status(tmp_path):
    with _isolated_client(tmp_path) as (client, TestingSession):
        # 找不到素材 → 404（在 LLM 閘之前就擋下，不需 LLM）
        assert client.post("/discovery/triage/99999").status_code == 404

        # 非 new/triaged（built）→ 400
        db = TestingSession()
        try:
            db.add(RawStrategyFind(source="a", source_url="https://a.com/b",
                                   title="b", status="built"))
            db.commit()
            fid = db.query(RawStrategyFind).first().id
        finally:
            db.close()
        assert client.post(f"/discovery/triage/{fid}").status_code == 400
