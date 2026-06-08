"""
自動部署規則（DB 化）測試
==========================
涵蓋：
1. 服務層 get_config：空表自動 seed（用 .env 預設）、單列冪等。
2. 服務層 update_config：只改有帶欄位、驗證、回傳 scan_hour 是否變動。
3. API：PUT /automation 往返、scan_hour 變動觸發重掛 cron、驗證失敗回 400。

不連網：用臨時 SQLite。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_automation_config.py -q
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

from fastapi.testclient import TestClient

from backend.database import Base
from backend.config import settings
from backend.models import AutomationConfig
from backend.services.automation_config import get_config, update_config


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'autocfg.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# ---------- 1. get_config（load-or-seed） ----------
def test_get_config_seeds_from_env_defaults(tmp_path):
    """空表 → 用 .env 的 AUTO_DEPLOY_* 預設種一筆 id=1。"""
    db = _session(tmp_path)
    cfg = get_config(db)
    assert cfg.id == 1
    assert cfg.enabled == settings.AUTO_DEPLOY_ENABLED
    assert cfg.ev_threshold == settings.AUTO_DEPLOY_EV_THRESHOLD
    assert cfg.scan_hour == settings.AUTO_DEPLOY_HOUR
    # 再呼一次不會多種一列（單列冪等）
    get_config(db)
    assert db.query(AutomationConfig).count() == 1


# ---------- 2. update_config ----------
def test_update_only_provided_fields(tmp_path):
    """只改有帶的欄位；None 不動。回傳 scan_hour 是否變動。"""
    db = _session(tmp_path)
    cfg, hour_changed = update_config(db, ev_threshold=200.0, scan_hour=None)
    assert cfg.ev_threshold == 200.0
    assert hour_changed is False  # scan_hour 沒帶
    assert cfg.scan_hour == settings.AUTO_DEPLOY_HOUR  # 維持原值


def test_update_scan_hour_flags_change(tmp_path):
    """改 scan_hour 到不同值 → hour_changed=True。"""
    db = _session(tmp_path)
    start = get_config(db).scan_hour
    cfg, hour_changed = update_config(db, scan_hour=(start + 1) % 24)
    assert hour_changed is True
    # 帶相同值 → 不算變動
    _, again = update_config(db, scan_hour=cfg.scan_hour)
    assert again is False


def test_update_validation_rejects_bad_values(tmp_path):
    """超範圍值 → ValueError。"""
    db = _session(tmp_path)
    with pytest.raises(ValueError):
        update_config(db, scan_hour=24)        # 0~23
    with pytest.raises(ValueError):
        update_config(db, max_bots=0)          # >=1
    with pytest.raises(ValueError):
        update_config(db, winrate_threshold=150)  # 0~100
    with pytest.raises(ValueError):
        update_config(db, ev_threshold=-1)     # >=0


# ---------- 3. API ----------
def test_put_automation_roundtrip(monkeypatch):
    """PUT /automation 改值 → GET 看到新值（同一份 app DB）。"""
    import backend.bots.bot_manager as bm
    called = {"hour": None}
    monkeypatch.setattr(bm.bot_manager, "schedule_auto_deploy",
                        lambda hour: called.__setitem__("hour", hour))
    from backend.main import app
    with TestClient(app) as client:
        resp = client.put("/automation", json={"ev_threshold": 321.0, "scan_hour": 9})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ev_threshold"] == 321.0 and body["scan_hour"] == 9, body
        # scan_hour 有變 → 重掛 cron 被呼叫
        assert called["hour"] == 9
        # GET 拿到落 DB 的新值
        got = client.get("/automation").json()
        assert got["ev_threshold"] == 321.0 and got["scan_hour"] == 9, got


def test_put_automation_validation_400():
    """不合法值 → 400。"""
    from backend.main import app
    with TestClient(app) as client:
        resp = client.put("/automation", json={"scan_hour": 99})
        assert resp.status_code == 400, resp.text


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        test_get_config_seeds_from_env_defaults(p)
        test_update_only_provided_fields(p)
        test_update_scan_hour_flags_change(p)
        test_update_validation_rejects_bad_values(p)
    print("✅ 服務層測試通過（API 測試請用 pytest 跑）")
