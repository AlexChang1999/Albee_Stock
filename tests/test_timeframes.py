"""
多 timeframe 資料地基測試（M2）
===============================
驗證：
1. timeframes 模組：合法/不合法 key、年化基數、bar→日曆天換算
2. lookback：required_lookback_days 的 timeframe 泛化（1Day 行為不變）
3. analytics：extended_metrics 年化基數（1Day 與舊行為一致；日內 calmar/cagr 誠實回 None）
4. bar_cache：不同 timeframe 不撞檔（1Day 沿用舊路徑、日內另開子目錄）
5. yfinance：日內超限誠實拋錯
6. backtest_engine._resolve_source：日內一律 alpaca
"""

import pytest

from backend.services import timeframes


# ---------- 1. timeframes 模組 ----------

def test_validate_accepts_all_and_rejects_bad():
    for tf in timeframes.ALL_TIMEFRAMES:
        assert timeframes.validate(tf) == tf
    assert timeframes.validate("5min") == "5Min"  # 大小寫容錯
    with pytest.raises(ValueError):
        timeframes.validate("3Min")


def test_periods_per_year():
    """年化基數：日 K 必須等於舊常數 252，分鐘 K 依每日 bar 數放大。"""
    assert timeframes.periods_per_year("1Day") == 252
    assert timeframes.periods_per_year("1Min") == 252 * 390
    assert timeframes.periods_per_year("5Min") == 252 * 78
    assert timeframes.periods_per_year("1Hour") == 252 * 6.5


def test_bars_to_calendar_days():
    """78 根 5 分 K = 1 個交易日 → 換算後最少也要 2 天；390 根 = 5 個交易日 → 12 天。"""
    assert timeframes.bars_to_calendar_days(78, "5Min") >= 2
    assert timeframes.bars_to_calendar_days(78 * 5, "5Min") == 12  # ceil(5*7/5)+5


# ---------- 2. lookback 泛化 ----------

def test_lookback_days_default_unchanged():
    """不帶 timeframe（= 1Day）的結果必須與舊版公式一字不差（零改動相容）。"""
    import math
    from backend.strategies.lookback import required_lookback_days

    old = math.ceil(math.ceil(21 * 1.6) * 7 / 5) + 5  # ma_crossover long=20 → 21 根
    assert required_lookback_days("ma_crossover", {"long_window": 20}) == old


def test_lookback_days_intraday_much_shorter():
    """同一策略在 5Min 框架下需要的『日曆天』遠少於日 K（一天有 78 根）。"""
    from backend.strategies.lookback import required_lookback_days

    daily = required_lookback_days("ma_crossover", {"long_window": 20})
    intraday = required_lookback_days("ma_crossover", {"long_window": 20}, timeframe="5Min")
    assert intraday < daily
    assert intraday >= 2  # 最少也要跨一個交易日


# ---------- 3. analytics 年化 ----------

def test_extended_metrics_1day_matches_legacy():
    """1Day 的 sharpe 與『不帶 timeframe』完全一致（預設值零改動相容）。"""
    from backend.services.analytics import extended_metrics

    equity = [10000 + i * 7 + (i % 5) * 13 for i in range(120)]
    legacy = extended_metrics(equity)
    explicit = extended_metrics(equity, timeframe="1Day")
    assert legacy == explicit


def test_extended_metrics_intraday_scales_and_nulls():
    """日內：sharpe 依年化基數放大（√(78) 倍階），calmar/cagr 誠實回 None。"""
    from backend.services.analytics import extended_metrics

    equity = [10000 + i * 7 + (i % 5) * 13 for i in range(120)]
    daily = extended_metrics(equity, timeframe="1Day")
    m5 = extended_metrics(equity, timeframe="5Min")
    assert m5["calmar"] is None and m5["cagr_pct"] is None
    if daily["sharpe"] is not None and m5["sharpe"] is not None:
        # 同一組報酬、年化基數 ×78 → sharpe 應約放大 √78 ≈ 8.8 倍
        assert m5["sharpe"] > daily["sharpe"] * 5


# ---------- 4. bar_cache 不撞檔 ----------

def test_cache_paths_separated_by_timeframe(monkeypatch, tmp_path):
    """1Day 沿用舊路徑（零遷移）；日內另開 {source}/{timeframe}/ 子目錄，不互撞。"""
    from backend.config import settings
    from backend.services.bar_cache import _cache_paths

    monkeypatch.setattr(settings, "BAR_CACHE_DIR", str(tmp_path))
    day_pq, _ = _cache_paths("alpaca", "AMD")            # 預設 1Day
    day_pq2, _ = _cache_paths("alpaca", "AMD", "1Day")
    m5_pq, _ = _cache_paths("alpaca", "AMD", "5Min")
    assert day_pq == day_pq2                              # 1Day = 舊路徑
    assert day_pq != m5_pq
    assert "5Min" in str(m5_pq)


def test_cached_fetch_passes_timeframe(monkeypatch, tmp_path):
    """get_bars_cached 首抓把 timeframe 透傳給 market_data.get_bars。"""
    import datetime as dt
    import pandas as pd
    from backend.config import settings
    from backend.services import bar_cache, market_data

    monkeypatch.setattr(settings, "BAR_CACHE_DIR", str(tmp_path))
    seen = {}

    def fake_get_bars(symbol, days=60, source="alpaca", timeframe="1Day"):
        seen["timeframe"] = timeframe
        ts = pd.date_range("2026-06-01 09:30", periods=5, freq="5min")
        return pd.DataFrame({
            "timestamp": ts, "open": 1.0, "high": 1.0, "low": 1.0,
            "close": 1.0, "volume": 100,
        })

    monkeypatch.setattr(market_data, "get_bars", fake_get_bars)
    df = bar_cache.get_bars_cached(
        "AMD", days=5, source="alpaca", today=dt.date(2026, 6, 2), timeframe="5Min"
    )
    assert seen["timeframe"] == "5Min"
    assert not df.empty


def test_intraday_today_always_refetches_tail(monkeypatch, tmp_path):
    """日內：涵蓋到今天仍視為尾缺口（盤中新 bar 要進得來）；日 K 維持 0 次 API。"""
    import datetime as dt
    import pandas as pd
    from backend.config import settings
    from backend.services import bar_cache, market_data

    monkeypatch.setattr(settings, "BAR_CACHE_DIR", str(tmp_path))
    today = dt.date(2026, 6, 2)
    calls = {"n": 0}

    def fake_get_bars(symbol, days=60, source="alpaca", timeframe="1Day"):
        calls["n"] += 1
        ts = pd.date_range("2026-06-01 09:30", periods=5, freq="5min")
        return pd.DataFrame({
            "timestamp": ts, "open": 1.0, "high": 1.0, "low": 1.0,
            "close": 1.0, "volume": 100,
        })

    monkeypatch.setattr(market_data, "get_bars", fake_get_bars)
    # 首抓 + 同請求第二次：日內應再打 1 次（今天永遠是尾缺口）
    bar_cache.get_bars_cached("AMD", days=5, source="alpaca", today=today, timeframe="5Min")
    n_after_first = calls["n"]
    bar_cache.get_bars_cached("AMD", days=5, source="alpaca", today=today, timeframe="5Min")
    assert calls["n"] == n_after_first + 1

    # 對照組：日 K 同請求第二次 = 全命中 0 次 API（舊行為不變）
    calls["n"] = 0
    bar_cache.get_bars_cached("NVDA", days=5, source="alpaca", today=today, timeframe="1Day")
    n_after_first = calls["n"]
    bar_cache.get_bars_cached("NVDA", days=5, source="alpaca", today=today, timeframe="1Day")
    assert calls["n"] == n_after_first  # 0 次新 API


# ---------- 5. yfinance 限制 ----------

def test_yfinance_rejects_out_of_range_intraday():
    from backend.services.yfinance_client import _to_interval

    assert _to_interval("1Day", 3650) == "1d"
    assert _to_interval("5Min", 30) == "5m"
    with pytest.raises(ValueError):
        _to_interval("5Min", 120)   # 超過 60 天上限
    with pytest.raises(ValueError):
        _to_interval("2Hour", 10)   # yfinance 無此 interval


# ---------- 6. 回測資料源切換 ----------

def test_resolve_source_intraday_forces_alpaca():
    from backend.services.backtest_engine import _resolve_source, ALPACA_MAX_DAYS

    assert _resolve_source("yfinance", 30, "5Min") == "alpaca"
    assert _resolve_source("alpaca", 30, "5Min") == "alpaca"
    # 日 K 舊行為不變：超長自動切 yfinance
    assert _resolve_source("alpaca", ALPACA_MAX_DAYS + 1) == "yfinance"
    assert _resolve_source("alpaca", 365) == "alpaca"
