"""
策略方案 + 回測紀錄 API 測試 ── Phase 5
================================================
用 FastAPI TestClient 測 presets CRUD，以及 backtest-runs 依 EV 排序、收藏篩選。
刻意「不」測 POST /presets/{id}/backtest（那個會連 Alpaca 抓資料）——
回測引擎本身的數學已在 test_backtest.py 驗過，這裡只測 API 與資料層。

回測紀錄的排序測試，直接用 SessionLocal 塞假資料（不經回測），驗排序邏輯。

執行（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_presets.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from backend.main import app
from backend.database import SessionLocal
from backend.models import BacktestRun

client = TestClient(app)


def test_preset_crud():
    """方案的建立 → 列出 → 編輯 → 刪除 完整往返。"""
    # 建立
    payload = {
        "name": "測試-AAPL威廉指標",
        "strategy_key": "williams_r",
        "symbol": "aapl",  # 故意小寫，驗證後端轉大寫
        "params": {"period": 14},
        "notes": "單元測試用",
    }
    r = client.post("/presets", json=payload)
    assert r.status_code == 200, r.text
    created = r.json()
    pid = created["id"]
    assert created["symbol"] == "AAPL", "symbol 應轉大寫"
    assert created["strategy_key"] == "williams_r"

    # 列出，應含剛建的
    r = client.get("/presets")
    assert r.status_code == 200, r.text
    assert any(p["id"] == pid for p in r.json()), "列表找不到剛建的方案"

    # 編輯：改名 + 收藏
    upd = {**payload, "name": "改名後", "is_favorite": True}
    r = client.put(f"/presets/{pid}", json=upd)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "改名後"
    assert r.json()["is_favorite"] is True

    # 刪除
    r = client.delete(f"/presets/{pid}")
    assert r.status_code == 200, r.text

    # 確認已不在列表
    r = client.get("/presets")
    assert not any(p["id"] == pid for p in r.json()), "刪除後仍出現在列表"
    print("✅ 方案 CRUD 往返測試通過")


def test_update_missing_preset_404():
    """編輯不存在的方案 → 404。"""
    r = client.put("/presets/999999", json={"name": "x", "symbol": "AAPL"})
    assert r.status_code == 404, r.text
    print("✅ 不存在方案回 404 測試通過")


def test_backtest_runs_sorted_by_ev():
    """塞兩筆假回測（EV 高/低），驗 GET /backtest-runs 依 EV 由高到低排，且 favorite 篩選有效。"""
    db = SessionLocal()
    low = BacktestRun(
        strategy_key="rsi", symbol="AAPL", params={}, period_days=365,
        metrics={"expected_value": 10.0, "win_rate_pct": 80.0}, is_good=False,
    )
    high = BacktestRun(
        strategy_key="rsi", symbol="AAPL", params={}, period_days=365,
        metrics={"expected_value": 99.0, "win_rate_pct": 40.0}, is_good=True,
    )
    db.add_all([low, high])
    db.commit()
    low_id, high_id = low.id, high.id
    db.close()

    try:
        # 全部：高 EV 應排在低 EV 前面
        r = client.get("/backtest-runs")
        assert r.status_code == 200, r.text
        rows = r.json()
        ids = [row["id"] for row in rows]
        assert high_id in ids and low_id in ids
        assert ids.index(high_id) < ids.index(low_id), "高 EV 應排在低 EV 前"

        # 收藏篩選：只回 is_good=True 的那筆
        r = client.get("/backtest-runs", params={"favorite": True})
        fav_ids = [row["id"] for row in r.json()]
        assert high_id in fav_ids, "收藏的高 EV 應在 favorite 清單"
        assert low_id not in fav_ids, "未收藏的不該出現在 favorite 清單"
        print("✅ 回測紀錄 EV 排序 + 收藏篩選測試通過")
    finally:
        # 清理假資料
        db = SessionLocal()
        for rid in (low_id, high_id):
            obj = db.query(BacktestRun).filter(BacktestRun.id == rid).first()
            if obj:
                db.delete(obj)
        db.commit()
        db.close()


if __name__ == "__main__":
    test_preset_crud()
    test_update_missing_preset_404()
    test_backtest_runs_sorted_by_ev()
    print("\n🎉 全部 presets 測試通過！")
