"""
策略指標疊圖測試（Stage 4 策略可視化）
======================================
守三件事：
1. 映射覆蓋 STRATEGY_REGISTRY 的**所有**註冊策略（新增策略漏接這裡會炸——
   composite 明確回空也算覆蓋）。
2. 輸出格式正確：time 是 "YYYY-MM-DD"、value 無 NaN、色用色名（前端對 NEON 映射）。
3. params 覆寫生效（例：rsi period=7 與預設 14 的序列不同）。

另測 GET /bots/{id}/chart-data 煙霧往返（mock get_bars，不連網）。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_indicator_overlays.py -q
"""

import math
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from backend.services.indicator_overlays import OVERLAY_BUILDERS, compute_overlays
from backend.strategies import STRATEGY_REGISTRY

# 前端認得的色名（utils 對 NEON 映射），後端只准回這些
ALLOWED_COLORS = {"cyan", "gold", "green", "red"}


def _fake_df(n=120) -> pd.DataFrame:
    """合成一段有漲有跌的日 K（固定亂數種子，測試可重現）。"""
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0.1, 1.5, n))
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="D"),
        "open": close + rng.normal(0, 0.5, n),
        "high": close + abs(rng.normal(1, 0.5, n)),
        "low": close - abs(rng.normal(1, 0.5, n)),
        "close": close,
        "volume": rng.integers(1_000, 10_000, n),
    })


def _check_series_shape(line: dict):
    """單條序列的格式檢查：time 字串格式 + value 是有限 float。"""
    assert line["color"] in ALLOWED_COLORS, f"未知色名 {line['color']}（{line['id']}）"
    assert line["data"], f"{line['id']} 序列為空"
    for pt in line["data"]:
        assert len(pt["time"]) == 10 and pt["time"][4] == "-", pt["time"]
        assert isinstance(pt["value"], float) and math.isfinite(pt["value"]), pt


def test_every_registered_strategy_is_mapped():
    """STRATEGY_REGISTRY 的每個策略都要在映射裡（新策略漏接這裡會炸）。"""
    missing = set(STRATEGY_REGISTRY) - set(OVERLAY_BUILDERS)
    assert not missing, f"這些策略沒有指標疊圖映射：{missing}"
    print("✅ 映射覆蓋所有註冊策略測試通過")


def test_all_strategies_produce_clean_output():
    """每個策略算出的 overlays/pane 格式正確、無 NaN、色名合法。"""
    df = _fake_df()
    for name in STRATEGY_REGISTRY:
        result = compute_overlays(name, {}, df)
        assert set(result) == {"overlays", "pane"}, result.keys()
        for line in result["overlays"]:
            _check_series_shape(line)
        if result["pane"] is not None:
            assert result["pane"]["title"]
            assert isinstance(result["pane"]["levels"], list)
            for line in result["pane"]["series"]:
                _check_series_shape(line)
    print("✅ 全策略輸出格式/NaN/色名測試通過")


def test_known_shapes():
    """抽查幾個策略的結構符合預期（主圖 vs 副圖、線數、levels 吃參數）。"""
    df = _fake_df()
    ma = compute_overlays("ma_crossover", {"short_window": 5, "long_window": 20}, df)
    assert len(ma["overlays"]) == 2 and ma["pane"] is None
    assert ma["overlays"][0]["title"] == "MA5"

    bb = compute_overlays("bollinger", {}, df)
    assert len(bb["overlays"]) == 3 and bb["pane"] is None  # 上/中/下軌

    rsi = compute_overlays("rsi", {"oversold": 25, "overbought": 75}, df)
    assert rsi["overlays"] == [] and rsi["pane"]["levels"] == [25, 75]  # levels 吃參數

    adx = compute_overlays("adx_trend", {}, df)
    assert len(adx["pane"]["series"]) == 3  # ADX / +DI / −DI

    comp = compute_overlays("composite", {}, df)
    assert comp == {"overlays": [], "pane": None}  # 明確不支援
    print("✅ 結構抽查測試通過")


def test_params_override_changes_series():
    """params 覆寫生效：rsi period=7 與預設 14 的序列必須不同。"""
    df = _fake_df()
    rsi_7 = compute_overlays("rsi", {"period": 7}, df)["pane"]["series"][0]["data"]
    rsi_14 = compute_overlays("rsi", {}, df)["pane"]["series"][0]["data"]
    assert rsi_7 != rsi_14
    # 暖機期較短 → period=7 的有效點較多
    assert len(rsi_7) > len(rsi_14)
    print("✅ params 覆寫生效測試通過")


def test_unknown_or_empty_is_safe():
    """未知策略 / 空資料 → 安全回空，不拋例外。"""
    df = _fake_df()
    assert compute_overlays("no_such_strategy", {}, df) == {"overlays": [], "pane": None}
    assert compute_overlays("rsi", {}, pd.DataFrame()) == {"overlays": [], "pane": None}
    assert compute_overlays("rsi", {}, None) == {"overlays": [], "pane": None}
    print("✅ 未知策略/空資料防呆測試通過")


def test_chart_data_endpoint_smoke(tmp_path, monkeypatch):
    """GET /bots/{id}/chart-data：mock 資料源，驗證 candles/overlays/markers 齊全。"""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import backend.routers.bots as bots_router
    from backend.database import Base, get_db
    from backend.main import app
    from backend.models import Bot, TradeLog

    engine = create_engine(f"sqlite:///{tmp_path / 'chart.db'}")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    def _override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = _override_get_db
    monkeypatch.setattr(bots_router.market_data, "get_bars", lambda *a, **k: _fake_df())

    s = TestSession()
    bot = Bot(name="圖測", strategy="ma_crossover", symbol="TEST",
              params={"short_window": 5, "long_window": 20})
    s.add(bot)
    s.commit()
    bid = bot.id
    s.add(TradeLog(bot_id=bid, symbol="TEST", side="buy", qty=3, price=101.5,
                   order_id="o1", reason="黃金交叉"))
    s.commit()
    s.close()

    try:
        with TestClient(app) as client:
            resp = client.get(f"/bots/{bid}/chart-data?days=120")
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["symbol"] == "TEST"
            assert len(body["candles"]) > 0
            assert len(body["overlays"]) == 2  # MA 雙線
            assert body["pane"] is None
            trade_markers = [m for m in body["markers"] if m["kind"] == "trade"]
            assert len(trade_markers) == 1 and trade_markers[0]["side"] == "buy"
    finally:
        app.dependency_overrides.pop(get_db, None)
    print("✅ chart-data 端點煙霧測試通過")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
