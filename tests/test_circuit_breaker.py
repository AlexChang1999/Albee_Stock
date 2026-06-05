"""
組合回撤熔斷測試（Phase 6 step-09）
====================================
兩部分：
1. 純函式 portfolio_circuit_breaker：未達 / 剛好 / 超過門檻 / 峰值為 0 / 創新高 等邊界。
2. check_breaker 編排：best-effort 更新持久化峰值、回是否熔斷；離線（查不到帳戶）放行。

不連網：用臨時 SQLite + monkeypatch alpaca_client.get_account。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_circuit_breaker.py -q
"""

import sys
from pathlib import Path
from types import SimpleNamespace

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.services.circuit_breaker as cb
from backend.config import settings
from backend.database import Base
from backend.models import PortfolioState
from backend.services.circuit_breaker import portfolio_circuit_breaker


# ---------- 1. 純函式 ----------
def test_pure_breaker_thresholds():
    # 峰值 100、門檻 20%
    assert portfolio_circuit_breaker(90, 100, 20) is False   # 回撤 10% < 20%
    assert portfolio_circuit_breaker(80, 100, 20) is True    # 回撤剛好 20% → 熔斷
    assert portfolio_circuit_breaker(70, 100, 20) is True    # 回撤 30% > 20%
    assert portfolio_circuit_breaker(110, 100, 20) is False  # 創新高 → 不熔斷


def test_pure_breaker_no_valid_peak():
    """峰值無效（None / 0 / 負）→ 不熔斷（還沒有有效水位）。"""
    assert portfolio_circuit_breaker(50, None, 20) is False
    assert portfolio_circuit_breaker(50, 0, 20) is False
    print("✅ portfolio_circuit_breaker 純函式全通過")


# ---------- 2. 編排 ----------
def _setup_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'cb.db'}")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    monkeypatch.setattr(cb, "SessionLocal", TestSession)
    return TestSession


def test_check_breaker_updates_peak_then_trips(tmp_path, monkeypatch):
    """先到高點建立峰值，後續權益跌破門檻 → 熔斷。"""
    TestSession = _setup_db(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "PORTFOLIO_MAX_DRAWDOWN_PCT", 20)

    equity = {"v": 1000.0}
    monkeypatch.setattr(cb.alpaca_client, "get_account",
                        lambda: SimpleNamespace(portfolio_value=equity["v"]))

    # 第一次：建立峰值 1000，未回撤 → 不熔斷
    r1 = cb.check_breaker()
    assert r1["tripped"] is False and r1["equity_peak"] == 1000.0, r1

    # 權益跌到 750（回撤 25% > 20%）→ 熔斷；峰值仍是 1000
    equity["v"] = 750.0
    r2 = cb.check_breaker()
    assert r2["tripped"] is True and r2["equity_peak"] == 1000.0, r2

    # 峰值有持久化
    s = TestSession()
    st = s.query(PortfolioState).filter(PortfolioState.id == 1).first()
    assert st.equity_peak == 1000.0, st.equity_peak
    s.close()
    print("✅ check_breaker 更新峰值並在跌破時熔斷測試通過")


def test_check_breaker_offline_is_safe(tmp_path, monkeypatch):
    """離線 / 查不到帳戶 → tripped=False（best-effort 放行，不阻斷流程）。"""
    _setup_db(tmp_path, monkeypatch)
    monkeypatch.setattr(cb.alpaca_client, "get_account",
                        lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    r = cb.check_breaker()
    assert r["tripped"] is False, r
    print("✅ check_breaker 離線安全放行測試通過")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
