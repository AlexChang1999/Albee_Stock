"""
批次抓取測試（效率升級：批次多檔 K 線 / 報價 + 快取批次版 + 限流器）
=====================================================================
驗證三件事（全部 monkeypatch、不連網）：
1. alpaca_client.get_bars_multi 拆包後每檔與單檔版 get_bars 逐欄一致（契約守門）。
2. bar_cache.get_bars_cached_multi 只對「快取缺口」批次補抓；全命中 0 次 API；
   批次失敗自動退單檔舊路徑（回測=實盤一致性的傳輸層批次化，不可改變結果）。
3. _RateLimiter token bucket：額度內零延遲、超量 sleep、per_minute=0 不限流。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_batch_fetch.py -v
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

from backend.config import settings
from backend.services import bar_cache, market_data, yfinance_client
from backend.services import alpaca_client as alpaca_mod
from backend.services.alpaca_client import AlpacaClient


# ============================================================
# 測試工具：假資料 / 假 client / 假時鐘
# ============================================================
TODAY = date(2026, 6, 1)  # 固定「今天」，缺口邏輯有確定性（沿用 bar_cache 的 today 注入縫）


def _fake_bars(days: int, end: date = TODAY) -> pd.DataFrame:
    """產一段日 K（end 往回 days 天、每日一根），格式照資料契約。"""
    ts = pd.date_range(start=end - timedelta(days=days), end=end, freq="D")
    n = len(ts)
    return pd.DataFrame({
        "timestamp": ts,
        "open": [float(i) for i in range(n)],
        "high": [float(i) + 1 for i in range(n)],
        "low": [float(i) - 0.5 for i in range(n)],
        "close": [float(i) + 0.5 for i in range(n)],
        "volume": [100 + i for i in range(n)],
    })


class _FakeBarsResp:
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df


class _FakeDataClient:
    """假的 Alpaca 資料 client：回 MultiIndex (symbol, timestamp) 的 df，模擬 SDK 形狀。"""

    def __init__(self, symbols: list[str], days: int = 30) -> None:
        frames = []
        for sym in symbols:
            one = _fake_bars(days)
            one["symbol"] = sym
            frames.append(one)
        df = pd.concat(frames, ignore_index=True)
        self._df = df.set_index(["symbol", "timestamp"])
        self.calls = 0

    def get_stock_bars(self, request):
        self.calls += 1
        syms = request.symbol_or_symbols
        if isinstance(syms, str):
            syms = [syms]
        sub = self._df[self._df.index.get_level_values("symbol").isin(syms)]
        return _FakeBarsResp(sub)


class _FakeTime:
    """假時鐘：sleep 推進 monotonic，限流測試不用真等。"""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, sec: float) -> None:
        self.sleeps.append(sec)
        self.now += sec


def _client_with_fake_data(symbols: list[str]) -> tuple[AlpacaClient, _FakeDataClient]:
    client = AlpacaClient()
    fake = _FakeDataClient(symbols)
    client._data = fake  # 繞過延遲初始化，不碰真金鑰
    return client, fake


# ============================================================
# 1. alpaca_client.get_bars_multi
# ============================================================
def test_multi_matches_single_per_symbol():
    """批次版拆包後，每檔 df 應與單檔版 get_bars 逐欄完全一致（契約守門）。"""
    client, _ = _client_with_fake_data(["AAPL", "MSFT"])
    single = client.get_bars("AAPL", days=30)
    multi = client.get_bars_multi(["AAPL", "MSFT"], days=30)
    assert set(multi.keys()) == {"AAPL", "MSFT"}
    pd.testing.assert_frame_equal(single, multi["AAPL"])


def test_multi_is_one_request():
    """3 檔批次抓只打 1 次 API（這就是效率來源）。"""
    client, fake = _client_with_fake_data(["AAPL", "MSFT", "NVDA"])
    client.get_bars_multi(["AAPL", "MSFT", "NVDA"], days=30)
    assert fake.calls == 1


def test_multi_pads_missing_symbol_with_empty_df():
    """查無資料的檔 key 仍在、值是空 df（呼叫端不用接 KeyError）。"""
    client, _ = _client_with_fake_data(["AAPL"])  # 假資料只有 AAPL
    multi = client.get_bars_multi(["AAPL", "ZZZZ"], days=30)
    assert not multi["AAPL"].empty
    assert multi["ZZZZ"].empty


def test_multi_empty_list_no_api_call():
    """空清單直接回空 dict、不打 API。"""
    client, fake = _client_with_fake_data(["AAPL"])
    assert client.get_bars_multi([], days=30) == {}
    assert fake.calls == 0


# ============================================================
# 2. market_data / yfinance 分派
# ============================================================
def test_market_data_multi_rejects_unknown_source():
    try:
        market_data.get_bars_multi(["AAPL"], source="nasa")
        raise AssertionError("不支援的 source 應丟 ValueError")
    except ValueError:
        pass


def test_yfinance_multi_single_symbol_uses_single_path(monkeypatch):
    """單檔走單檔路徑（yf.download 單檔回非 MultiIndex 形狀的坑，繞開）。"""
    sentinel = _fake_bars(5)
    monkeypatch.setattr(yfinance_client, "get_bars", lambda s, days=60: sentinel)
    monkeypatch.setattr(
        yfinance_client.yf, "download",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("單檔不該呼叫 yf.download")),
    )
    out = yfinance_client.get_bars_multi(["aapl"], days=5)
    assert list(out.keys()) == ["AAPL"]
    assert out["AAPL"] is sentinel


# ============================================================
# 3. bar_cache.get_bars_cached_multi
# ============================================================
def _patch_cache_env(monkeypatch, tmp_path, calls: dict):
    """快取目錄指到 tmp、market_data 兩個抓取函式換成假資料 + 計數。"""
    monkeypatch.setattr(settings, "BAR_CACHE_DIR", str(tmp_path))

    def fake_single(symbol, days=60, source="alpaca"):
        calls["single"] += 1
        return _fake_bars(days)

    def fake_multi(symbols, days=60, source="alpaca"):
        calls["multi"] += 1
        calls["multi_symbols"].append(sorted(symbols))
        return {s.upper(): _fake_bars(days) for s in symbols}

    monkeypatch.setattr(market_data, "get_bars", fake_single)
    monkeypatch.setattr(market_data, "get_bars_multi", fake_multi)
    return calls


def _fresh_calls() -> dict:
    return {"single": 0, "multi": 0, "multi_symbols": []}


def test_cached_multi_full_hit_zero_api(monkeypatch, tmp_path):
    """請求區間已被快取涵蓋 → 批次版 0 次外部 API（DoD：第二次同請求零請求）。"""
    calls = _patch_cache_env(monkeypatch, tmp_path, _fresh_calls())
    # 先用單檔路徑建好兩檔快取
    bar_cache.get_bars_cached("AAPL", days=30, today=TODAY)
    bar_cache.get_bars_cached("MSFT", days=30, today=TODAY)
    calls["single"], calls["multi"] = 0, 0

    out = bar_cache.get_bars_cached_multi(["AAPL", "MSFT"], days=30, today=TODAY)
    assert calls["single"] == 0 and calls["multi"] == 0  # 全命中
    for sym in ("AAPL", "MSFT"):
        assert not out[sym].empty
        dates = pd.to_datetime(out[sym]["timestamp"]).dt.date
        assert dates.min() >= TODAY - timedelta(days=30) and dates.max() <= TODAY


def test_cached_multi_mixed_buckets(monkeypatch, tmp_path):
    """混桶：全命中 / 無快取 / 尾缺口 → 各桶批次抓對的 symbols，最多 2 次 API。"""
    calls = _patch_cache_env(monkeypatch, tmp_path, _fresh_calls())
    # AAPL：涵蓋整段（全命中桶）
    bar_cache.get_bars_cached("AAPL", days=30, today=TODAY)
    # NVDA：較早的 today 建快取 → 對 TODAY 的請求有尾缺口
    bar_cache.get_bars_cached("NVDA", days=30, today=TODAY - timedelta(days=10))
    calls.update(_fresh_calls())

    out = bar_cache.get_bars_cached_multi(["AAPL", "MSFT", "NVDA"], days=30, today=TODAY)

    assert calls["single"] == 0
    assert calls["multi"] == 2  # 一次補「整段」桶（MSFT）、一次補「尾缺口」桶（NVDA）
    assert ["MSFT"] in calls["multi_symbols"]
    assert ["NVDA"] in calls["multi_symbols"]
    for sym in ("AAPL", "MSFT", "NVDA"):
        assert not out[sym].empty, sym
        dates = pd.to_datetime(out[sym]["timestamp"]).dt.date
        assert dates.max() <= TODAY, sym
    # 尾缺口補完應該補到最新
    nvda_dates = pd.to_datetime(out["NVDA"]["timestamp"]).dt.date
    assert nvda_dates.max() == TODAY


def test_cached_multi_batch_failure_falls_back_to_single(monkeypatch, tmp_path):
    """批次抓取整批失敗 → 退單檔舊路徑，結果照樣拿得到（網路抖動不全滅）。"""
    calls = _patch_cache_env(monkeypatch, tmp_path, _fresh_calls())

    def broken_multi(symbols, days=60, source="alpaca"):
        raise RuntimeError("批次掛了")

    monkeypatch.setattr(market_data, "get_bars_multi", broken_multi)
    out = bar_cache.get_bars_cached_multi(["AAPL", "MSFT"], days=30, today=TODAY)
    assert calls["single"] == 2  # 逐檔 fallback
    assert not out["AAPL"].empty and not out["MSFT"].empty


def test_cached_multi_matches_single_path(monkeypatch, tmp_path):
    """一致性守門：批次版結果應與逐檔跑單檔版完全一致（傳輸層批次化不可改變資料）。"""
    calls = _patch_cache_env(monkeypatch, tmp_path, _fresh_calls())
    multi_out = bar_cache.get_bars_cached_multi(["AAPL", "MSFT"], days=30, today=TODAY)
    # 換一個乾淨快取目錄跑單檔版（同一套假資料，結果應相同）
    single_dir = tmp_path / "single"
    monkeypatch.setattr(settings, "BAR_CACHE_DIR", str(single_dir))
    for sym in ("AAPL", "MSFT"):
        single = bar_cache.get_bars_cached(sym, days=30, today=TODAY)
        pd.testing.assert_frame_equal(single, multi_out[sym])


# ============================================================
# 4. 限流器
# ============================================================
def test_rate_limiter_token_bucket(monkeypatch):
    """額度內零延遲；超量 sleep 等補充；per_minute=0 不限流。"""
    fake = _FakeTime()
    monkeypatch.setattr(alpaca_mod, "time", fake)

    limiter = alpaca_mod._RateLimiter(3)
    for _ in range(3):
        limiter.acquire()
    assert fake.sleeps == []  # 額度內不等

    limiter.acquire()  # 第 4 次：超量 → sleep 到 token 補充
    assert len(fake.sleeps) == 1 and fake.sleeps[0] > 0

    unlimited = alpaca_mod._RateLimiter(0)
    for _ in range(50):
        unlimited.acquire()
    assert len(fake.sleeps) == 1  # 不限流模式沒有新增 sleep


def test_rate_limiter_clock_backwards_no_hang(monkeypatch):
    """時鐘倒退（測試假時鐘/系統校時）不可倒扣 token——否則會 sleep 好幾小時卡死。"""
    fake = _FakeTime()
    fake.now = 1000.0
    monkeypatch.setattr(alpaca_mod, "time", fake)
    limiter = alpaca_mod._RateLimiter(200)  # _last 記在 t=1000
    fake.now = 0.0  # 時鐘倒退 1000 秒
    limiter.acquire()
    assert fake.sleeps == []  # 倒退視為 0 經過：不倒扣、不 sleep


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
