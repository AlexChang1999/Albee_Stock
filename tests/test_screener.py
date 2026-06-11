"""
AI 策略探勘 / 漏斗式篩選測試
============================
兩部分：
1. 純函式：volume_ratio / passes_volume_filter / parse_sentiment / parse_watchlist
2. GET /ai-recommendations 整合（把漏斗各層換成假資料，免連網 / 免 LLM）

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe tests\\test_screener.py
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import screener
import backend.routers.recommendations as rec_router
from backend.services.screener import (
    volume_ratio,
    passes_volume_filter,
    parse_sentiment,
    parse_watchlist,
)


def _df_with_volumes(vols):
    """造一份只在意 volume 的假 DataFrame。"""
    return pd.DataFrame({"volume": vols})


# ---------- 1. 純函式 ----------
def test_volume_ratio_spike():
    """最後一根爆量時，量比應明顯 > 1。"""
    vols = [100] * 20 + [300]  # 前 20 根均量 100，最後一根 300 → 量比 3.0
    ratio = volume_ratio(_df_with_volumes(vols))
    assert abs(ratio - 3.0) < 1e-6, ratio


def test_volume_ratio_insufficient():
    """資料太少 / 均量為 0 → None。"""
    assert volume_ratio(_df_with_volumes([100])) is None
    assert volume_ratio(_df_with_volumes([0, 0, 0])) is None


def test_passes_volume_filter():
    vols = [100] * 20 + [300]
    assert passes_volume_filter(_df_with_volumes(vols), 2.5) is True
    assert passes_volume_filter(_df_with_volumes(vols), 5.0) is False


def test_parse_sentiment_json():
    raw = '亂講一通 {"label":"bullish","score":80,"reason":"財報超預期"} 後面雜訊'
    s = parse_sentiment(raw)
    assert s["label"] == "bullish" and s["score"] == 80, s


def test_parse_sentiment_fallback():
    """抓不到 JSON → 中性預設；score 超界會被夾住。"""
    assert parse_sentiment("完全沒有 json")["label"] == "neutral"
    assert parse_sentiment('{"label":"bullish","score":9999}')["score"] == 100


def test_parse_watchlist():
    assert parse_watchlist("aapl, MSFT ,aapl,") == ["AAPL", "MSFT"]
    print("✅ 漏斗純函式全通過")


# ---------- 2. API 整合 ----------
def test_recommendations_endpoint(monkeypatch):
    """
    GET /ai-recommendations 應回推薦清單。
    把第一/二/三層都換成假的，驗證編排與回傳格式，不連網不呼叫 LLM。
    """
    # 第一層：直接回兩檔「已爆量」的 survivor
    monkeypatch.setattr(
        screener, "_layer1_volume",
        lambda symbols, days, source: [
            {"symbol": "AAPL", "volume_ratio": 3.0},
            {"symbol": "TSLA", "volume_ratio": 2.8},
        ],
    )
    # 第三層前的批次暖快取也換掉（避免真打網路）
    monkeypatch.setattr(screener.bar_cache, "get_bars_cached_multi", lambda *a, **k: {})
    # 第二層：跳過情緒（None）
    monkeypatch.setattr(
        screener, "_layer2_sentiment",
        lambda picks: [{**p, "sentiment": None} for p in picks],
    )
    # 第三層：假回測，AAPL OOS EV 正、TSLA OOS EV 負（應被濾掉）
    # Phase 6 step-04：海選看「樣本外 EV」，故 EV 放 oos_expected_value
    def fake_scan(symbol, days, initial_cash, source):
        ev = 50.0 if symbol == "AAPL" else -10.0
        return {"best": {
            "strategy_key": "rsi", "params": {"period": 14},
            "metrics": {"oos_expected_value": ev, "oos_win_rate_pct": 60},
        }}
    monkeypatch.setattr(screener, "run_auto_backtest", fake_scan)
    # 清快取避免吃到舊結果
    rec_router._CACHE.clear()

    with TestClient(app) as client:
        resp = client.get("/ai-recommendations?refresh=true")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # 只有 AAPL（EV>0）入選
        assert body["recommended"] == 1, body
        assert body["recommendations"][0]["symbol"] == "AAPL", body
    print("✅ GET /ai-recommendations 整合通過")


if __name__ == "__main__":
    test_volume_ratio_spike()
    test_volume_ratio_insufficient()
    test_passes_volume_filter()
    test_parse_sentiment_json()
    test_parse_sentiment_fallback()
    test_parse_watchlist()
    # __main__ 直跑：手動替換漏斗各層再還原（含批次暖快取，避免真打網路）
    _warm = screener.bar_cache.get_bars_cached_multi
    screener.bar_cache.get_bars_cached_multi = lambda *a, **k: {}
    _l1, _l2, _scan = screener._layer1_volume, screener._layer2_sentiment, screener.run_auto_backtest
    screener._layer1_volume = lambda symbols, days, source: [
        {"symbol": "AAPL", "volume_ratio": 3.0},
        {"symbol": "TSLA", "volume_ratio": 2.8},
    ]
    screener._layer2_sentiment = lambda picks: [{**p, "sentiment": None} for p in picks]
    screener.run_auto_backtest = lambda symbol, days, initial_cash, source: {
        "best": {"strategy_key": "rsi", "params": {"period": 14},
                 "metrics": {"oos_expected_value": 50.0 if symbol == "AAPL" else -10.0, "oos_win_rate_pct": 60}}
    }
    rec_router._CACHE.clear()
    try:
        with TestClient(app) as client:
            resp = client.get("/ai-recommendations?refresh=true")
            body = resp.json()
            assert body["recommended"] == 1 and body["recommendations"][0]["symbol"] == "AAPL", body
        print("✅ GET /ai-recommendations 整合通過")
    finally:
        screener._layer1_volume, screener._layer2_sentiment, screener.run_auto_backtest = _l1, _l2, _scan
        screener.bar_cache.get_bars_cached_multi = _warm
    print("\n🎉 全部漏斗 / 推薦 API 測試通過！")
