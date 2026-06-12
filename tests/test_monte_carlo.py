"""
蒙地卡羅壓力測試（monte_carlo.py）測試
========================================
驗 bootstrap 路徑生成與分布統計：同 seed 可重現、形狀正確、
全零報酬不漲不跌、百分位排序合理、樣本太少拒算。
純函式、不連線。

執行（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_monte_carlo.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

from backend.services.monte_carlo import bootstrap_paths, stress_summary


def _sample_returns(n=250, seed=7):
    """造一組帶波動的日報酬（平均 +0.05%、標準差 1%），結果可重現。"""
    rng = np.random.default_rng(seed)
    return rng.normal(0.0005, 0.01, size=n).tolist()


def test_bootstrap_paths_shape():
    paths = bootstrap_paths(_sample_returns(), n_paths=50, seed=1)
    assert paths.shape == (50, 250)  # horizon 預設 = 原序列長度
    paths2 = bootstrap_paths(_sample_returns(), n_paths=10, horizon=100, seed=1)
    assert paths2.shape == (10, 100)


def test_same_seed_is_deterministic():
    a = bootstrap_paths(_sample_returns(), n_paths=20, seed=42)
    b = bootstrap_paths(_sample_returns(), n_paths=20, seed=42)
    assert np.array_equal(a, b)  # 同 seed 完全重現
    c = bootstrap_paths(_sample_returns(), n_paths=20, seed=43)
    assert not np.array_equal(a, c)  # 不同 seed 應不同


def test_all_zero_returns_final_equals_initial():
    # 每天報酬 0% → 任何重排都不漲不跌
    s = stress_summary([0.0] * 100, initial_equity=10000.0, n_paths=100, seed=1)
    assert s["final_equity_p5"] == 10000.0
    assert s["final_equity_p50"] == 10000.0
    assert s["final_equity_p95"] == 10000.0
    assert s["max_drawdown_p95"] == 0.0
    assert s["prob_ruin"] == 0.0


def test_percentiles_ordered():
    s = stress_summary(_sample_returns(), n_paths=500, seed=9)
    assert s["final_equity_p5"] <= s["final_equity_p50"] <= s["final_equity_p95"]
    assert s["max_drawdown_p50"] <= s["max_drawdown_p95"]
    # 機率欄位在 0~100 之間
    assert 0.0 <= s["prob_drawdown_exceeds_pct"] <= 100.0
    assert 0.0 <= s["prob_ruin"] <= 100.0


def test_short_input_raises():
    with pytest.raises(ValueError):
        bootstrap_paths([0.01] * 29)  # < 30 筆 → 拒算


# ---------- API 端點測試（POST /backtest/stress/{run_id}） ----------

def test_stress_endpoint_roundtrip():
    """建一筆臨時 BacktestRun → 打壓力測試端點 → 驗回應 → 清掉，不留垃圾。"""
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.database import SessionLocal
    from backend.models import BacktestRun

    # 造一條 100 天、帶波動的資金曲線存進 DB
    rng = np.random.default_rng(5)
    eq = [10000.0]
    for r in rng.normal(0.0005, 0.01, size=100):
        eq.append(eq[-1] * (1.0 + float(r)))

    # 進 with 區塊才會跑 app lifespan（初始化資料表），DB 操作都要在裡面
    with TestClient(app) as client:
        db = SessionLocal()
        run = BacktestRun(
            preset_id=None, strategy_key="ma_crossover", params={},
            symbol="TEST", period_days=100,
            metrics={"initial_cash": 10000.0, "equity_curve": eq},
        )
        db.add(run)
        db.commit()
        run_id = run.id
        try:
            r = client.post(f"/backtest/stress/{run_id}",
                            json={"n_paths": 200, "seed": 11})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["run_id"] == run_id
            assert body["method"] == "bootstrap"
            assert body["final_equity_p5"] <= body["final_equity_p50"] <= body["final_equity_p95"]

            # 不存在的 run → 404
            r404 = client.post("/backtest/stress/999999999", json={})
            assert r404.status_code == 404
        finally:
            db.delete(db.get(BacktestRun, run_id))
            db.commit()
            db.close()


def test_summary_keys_json_friendly():
    s = stress_summary(_sample_returns(), n_paths=50, seed=3)
    for key in ("method", "n_paths", "horizon_days", "final_equity_p5",
                "final_equity_p50", "final_equity_p95", "max_drawdown_p50",
                "max_drawdown_p95", "prob_drawdown_exceeds_pct", "prob_ruin"):
        assert key in s
    assert s["method"] == "bootstrap"
    # 全部是 JSON 可序列化純量
    import json
    json.dumps(s)
