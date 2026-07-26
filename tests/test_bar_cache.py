"""
多年 OHLCV 本機快取單元測試（Phase 11 step-02）
================================================
完全不連網：把 market_data.get_bars 換成「合成 K 線」假函式（含呼叫計數器），
快取資料夾用 pytest 的 tmp_path（測完即丟）。重點驗：
1. 首抓 → 打外部 API 一次、寫出 parquet。
2. 第二次同請求 → 命中快取、**0 次 API**。
3. 請求更晚 / 更早 → 只補對應缺口（尾 / 頭），結果無重複列、升冪。
4. 回傳區間嚴格 ⊆ 請求區間（不洩漏請求結束日之後的列）。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_bar_cache.py -q
"""

import sys
from datetime import date, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import pytest

from backend.config import settings
from backend.services import bar_cache, market_data

# 固定的「今天」基準（注入 get_bars_cached，讓缺口邏輯有確定性）
_T = date(2026, 1, 31)


class _FakeGetBars:
    """合成 K 線假 get_bars：記錄每次呼叫，回傳「截至 self.today、往回 days 天」的日 bar。"""

    def __init__(self):
        self.calls = []
        self.today = _T

    def __call__(self, symbol, days=60, source="alpaca", timeframe="1Day"):
        self.calls.append({"symbol": symbol, "days": days, "source": source, "timeframe": timeframe})
        end = self.today
        start = end - timedelta(days=days - 1)
        idx = pd.date_range(start, end, freq="D")
        # 用日期序數當值 → 好驗去重 / 切片正確
        vals = [float(d.toordinal()) for d in idx]
        return pd.DataFrame(
            {
                "timestamp": idx,
                "open": vals,
                "high": vals,
                "low": vals,
                "close": vals,
                "volume": [1000] * len(idx),
            }
        )


@pytest.fixture
def fake(tmp_path, monkeypatch):
    """把 BAR_CACHE_DIR 指到 tmp_path、market_data.get_bars 換成假函式。回傳假函式（含計數器）。"""
    monkeypatch.setattr(settings, "BAR_CACHE_DIR", str(tmp_path))
    f = _FakeGetBars()
    monkeypatch.setattr(market_data, "get_bars", f)
    return f


def _bar_dates(df):
    return pd.to_datetime(df["timestamp"]).dt.date


def test_first_fetch_calls_api_once_and_writes_parquet(fake, tmp_path):
    """首抓某 symbol 多年 → 打 API 一次、parquet 落地、回傳區間在請求內。"""
    df = bar_cache.get_bars_cached("AAPL", days=3650, source="yfinance", today=_T)
    assert len(fake.calls) == 1, fake.calls
    assert fake.calls[0]["days"] == 3650
    assert (tmp_path / "yfinance" / "AAPL.parquet").exists()
    assert (tmp_path / "yfinance" / "AAPL.meta.json").exists()
    assert not df.empty
    assert _bar_dates(df).min() >= _T - timedelta(days=3650)
    assert _bar_dates(df).max() <= _T


def test_second_identical_request_hits_cache_zero_api(fake):
    """第二次同 today + days → 全命中、0 次 API，且結果與第一次相同。"""
    df1 = bar_cache.get_bars_cached("AAPL", days=3650, source="yfinance", today=_T)
    fake.calls.clear()
    df2 = bar_cache.get_bars_cached("AAPL", days=3650, source="yfinance", today=_T)
    assert len(fake.calls) == 0, fake.calls  # ★ 命中快取、不打 API
    # parquet 來回會把 datetime64[s] 正規化成 [ms]，值相同即可（不比 dtype）
    pd.testing.assert_frame_equal(df1, df2, check_dtype=False)


def test_tail_gap_fetches_only_recent(fake):
    """請求更晚（today 往後 30 天）→ 只補尾缺口、抓 30 天，結果升冪無重複。"""
    bar_cache.get_bars_cached("AAPL", days=3650, source="yfinance", today=_T)
    later = _T + timedelta(days=30)
    fake.today = later
    fake.calls.clear()
    df = bar_cache.get_bars_cached("AAPL", days=3650, source="yfinance", today=later)
    assert len(fake.calls) == 1, fake.calls           # 只補一段
    assert fake.calls[0]["days"] == 30                # 尾缺口 = cov_end → today = 30 天
    ts = pd.to_datetime(df["timestamp"])
    assert ts.is_monotonic_increasing
    assert ts.duplicated().sum() == 0
    assert _bar_dates(df).max() <= later


def test_head_gap_fetches_full_span(fake):
    """請求更早（days 加大到 4000）→ 補頭缺口、抓滿 4000 天，結果升冪無重複。"""
    bar_cache.get_bars_cached("AAPL", days=3650, source="yfinance", today=_T)
    fake.calls.clear()
    df = bar_cache.get_bars_cached("AAPL", days=4000, source="yfinance", today=_T)
    assert len(fake.calls) == 1, fake.calls
    assert fake.calls[0]["days"] == 4000              # days-API 只能由今天回抓 → 抓滿整段
    ts = pd.to_datetime(df["timestamp"])
    assert ts.is_monotonic_increasing
    assert ts.duplicated().sum() == 0
    assert _bar_dates(df).min() >= _T - timedelta(days=4000)


def test_returned_range_strictly_within_request(fake):
    """快取已含到 _T 的列，但請求結束日較早 → 回傳不得洩漏結束日之後的列（且 0 次 API）。"""
    bar_cache.get_bars_cached("AAPL", days=3650, source="yfinance", today=_T)
    fake.calls.clear()
    earlier_end = _T - timedelta(days=10)
    df = bar_cache.get_bars_cached("AAPL", days=100, source="yfinance", today=earlier_end)
    assert len(fake.calls) == 0, fake.calls           # 子區間被涵蓋 → 0 次 API
    assert _bar_dates(df).max() <= earlier_end        # ★ 不洩漏請求結束日之後
    assert _bar_dates(df).min() >= earlier_end - timedelta(days=100)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
