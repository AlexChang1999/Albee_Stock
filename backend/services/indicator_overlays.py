"""
策略指標疊圖（indicator overlays）
==================================
「策略可視化」的資料源：依 Bot 的策略名 + 參數，算出該策略「看的指標」序列，
讓前端把指標畫在 K 線圖上（主圖疊線）或副圖（0~100 振盪器另開 pane）。

設計重點：
- **集中一處映射**：策略類（backend/strategies/*.py）的介面零修改——
  generate_signal 只回最後一天的訊號，畫圖需要「整條序列」，故在這裡用
  與各策略檔完全相同的公式重算整條（參數預設值也照抄各策略檔，
  測試 tests/test_indicator_overlays.py 守著映射覆蓋所有註冊策略）。
- **顏色回「色名」不回 hex**：前端用 theme 的 NEON 色票映射（cyan/gold/green/red），
  深底主題勿在後端寫死 hex。
- 時間格式 "YYYY-MM-DD"（同 routers/bars.py 的 candle），NaN（暖機期）直接略過該點。

回傳格式：
{
  "overlays": [  # 主圖疊線（與價格同軸）
    {"id": "ma_short", "title": "MA5", "color": "cyan",
     "data": [{"time": "2026-06-01", "value": 231.2}, ...]},
  ],
  "pane": {       # 振盪器副圖（沒有就 None）
    "title": "RSI(14)",
    "series": [{"id": "rsi", "title": "RSI", "color": "cyan", "data": [...]}],
    "levels": [30, 70],   # 水平參考線（超買/超賣/零軸等）
  },
}
"""

import pandas as pd

from backend.strategies.indicators import adx_components


def _points(df: pd.DataFrame, series: pd.Series) -> list[dict]:
    """把一條指標 Series 轉成前端要的 [{time, value}]，NaN 略過。"""
    points = []
    for ts, val in zip(df["timestamp"], series):
        if pd.isna(val):
            continue
        time_str = ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10]
        points.append({"time": time_str, "value": float(val)})
    return points


def _line(df, series, sid: str, title: str, color: str) -> dict:
    return {"id": sid, "title": title, "color": color, "data": _points(df, series)}


def _empty() -> dict:
    """不支援疊圖的策略（composite 等動態組合）回空，前端顯示提示。"""
    return {"overlays": [], "pane": None}


# ---------- 各策略的指標計算（公式照抄對應策略檔，參數預設值一致） ----------

def _ma_crossover(df, p):
    short_w = p.get("short_window", 5)
    long_w = p.get("long_window", 20)
    close = df["close"]
    return {
        "overlays": [
            _line(df, close.rolling(window=short_w).mean(), "ma_short", f"MA{short_w}", "cyan"),
            _line(df, close.rolling(window=long_w).mean(), "ma_long", f"MA{long_w}", "gold"),
        ],
        "pane": None,
    }


def _bollinger(df, p):
    period = p.get("period", 20)
    num_std = p.get("num_std", 2)
    close = df["close"]
    middle = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    return {
        "overlays": [
            _line(df, middle + num_std * std, "bb_upper", "上軌", "gold"),
            _line(df, middle, "bb_middle", f"中軌 MA{period}", "cyan"),
            _line(df, middle - num_std * std, "bb_lower", "下軌", "gold"),
        ],
        "pane": None,
    }


def _donchian(df, p):
    period = p.get("period", 20)
    high = df["high"] if "high" in df.columns else df["close"]
    low = df["low"] if "low" in df.columns else df["close"]
    # 策略比的是「不含今天的前 period 日」高低 → 序列用 shift(1) 對齊同一語義
    return {
        "overlays": [
            _line(df, high.rolling(window=period).max().shift(1), "dc_upper", f"{period}日高", "gold"),
            _line(df, low.rolling(window=period).min().shift(1), "dc_lower", f"{period}日低", "cyan"),
        ],
        "pane": None,
    }


def _macd(df, p):
    fast = p.get("fast", 12)
    slow = p.get("slow", 26)
    signal_period = p.get("signal", 9)
    close = df["close"]
    macd_line = (
        close.ewm(span=fast, adjust=False).mean()
        - close.ewm(span=slow, adjust=False).mean()
    )
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    return {
        "overlays": [],
        "pane": {
            "title": f"MACD({fast},{slow},{signal_period})",
            "series": [
                _line(df, macd_line, "macd", "MACD", "cyan"),
                _line(df, signal_line, "macd_signal", "Signal", "gold"),
            ],
            "levels": [0],
        },
    }


def _rsi(df, p):
    period = p.get("period", 14)
    overbought = p.get("overbought", 70)
    oversold = p.get("oversold", 30)
    delta = df["close"].diff()
    avg_gain = delta.clip(lower=0).rolling(window=period).mean()
    avg_loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    # avg_loss=0（全漲）時 RSI=100；其餘走標準公式
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = (100 - 100 / (1 + rs)).where(avg_loss != 0, 100.0)
    return {
        "overlays": [],
        "pane": {
            "title": f"RSI({period})",
            "series": [_line(df, rsi, "rsi", "RSI", "cyan")],
            "levels": [oversold, overbought],
        },
    }


def _stochastic(df, p):
    k_period = p.get("k_period", 14)
    d_period = p.get("d_period", 3)
    high = df["high"] if "high" in df.columns else df["close"]
    low = df["low"] if "low" in df.columns else df["close"]
    close = df["close"]
    low_min = low.rolling(window=k_period).min()
    high_max = high.rolling(window=k_period).max()
    rng = (high_max - low_min).replace(0, 1e-9)
    k = 100 * (close - low_min) / rng
    d = k.rolling(window=d_period).mean()
    return {
        "overlays": [],
        "pane": {
            "title": f"KD({k_period},{d_period})",
            "series": [
                _line(df, k, "stoch_k", "K", "cyan"),
                _line(df, d, "stoch_d", "D", "gold"),
            ],
            "levels": [20, 80],
        },
    }


def _williams_r(df, p):
    period = p.get("period", 14)
    overbought = p.get("overbought", -20)
    oversold = p.get("oversold", -80)
    close = df["close"]
    # 策略本身用 close 近似高低點（見 strategies/williams_r.py），這裡照抄
    highest = close.rolling(window=period).max()
    lowest = close.rolling(window=period).min()
    rng = (highest - lowest).replace(0, float("nan"))
    percent_r = (highest - close) / rng * -100
    return {
        "overlays": [],
        "pane": {
            "title": f"威廉 %R({period})",
            "series": [_line(df, percent_r, "williams_r", "%R", "cyan")],
            "levels": [oversold, overbought],
        },
    }


def _momentum(df, p):
    period = p.get("period", 10)
    threshold = p.get("threshold", 5)
    close = df["close"]
    roc = close.pct_change(periods=period) * 100
    return {
        "overlays": [],
        "pane": {
            "title": f"動量 ROC({period})",
            "series": [_line(df, roc, "roc", "ROC %", "cyan")],
            "levels": [-threshold, 0, threshold],
        },
    }


def _script_breakout(df, p):
    lookback = p.get("lookback", 20)
    exit_lookback = p.get("exit_lookback", 10)
    close = df["close"]
    # 策略比的是「不含今天的前 N 根收盤」極值 → 序列用 shift(1) 對齊同一語義
    return {
        "overlays": [
            _line(df, close.rolling(window=lookback).max().shift(1),
                  "brk_high", f"前{lookback}根收盤高", "gold"),
            _line(df, close.rolling(window=exit_lookback).min().shift(1),
                  "brk_low", f"前{exit_lookback}根收盤低", "cyan"),
        ],
        "pane": None,
    }


def _adx_trend(df, p):
    period = p.get("period", 14)
    adx_threshold = p.get("adx_threshold", 25)
    adx, di_plus, di_minus = adx_components(df, length=period)
    if adx.empty:
        return _empty()
    return {
        "overlays": [],
        "pane": {
            "title": f"ADX({period})",
            "series": [
                _line(df, adx, "adx", "ADX", "gold"),
                _line(df, di_plus, "di_plus", "+DI", "green"),
                _line(df, di_minus, "di_minus", "−DI", "red"),
            ],
            "levels": [adx_threshold],
        },
    }


# 策略名 → 指標計算函式。composite（動態子策略組合）v1 不支援疊圖、明確回空。
OVERLAY_BUILDERS = {
    "ma_crossover": _ma_crossover,
    "bollinger": _bollinger,
    "donchian": _donchian,
    "macd": _macd,
    "rsi": _rsi,
    "stochastic": _stochastic,
    "williams_r": _williams_r,
    "momentum": _momentum,
    "adx_trend": _adx_trend,
    "composite": lambda df, p: _empty(),
    # 事件驅動突破續抱：畫進場（前 lookback 根收盤高）/出場（前 exit_lookback 根收盤低）參考線
    "script_breakout": _script_breakout,
    # SNR 3.0：zone 是「逐根動態判定的多階段序列」（swing→爆發→回踩→拒絕→確認），
    # 沒有固定指標線可畫，v1 比照 composite 回空（前端顯示提示）。
    "snr_3_0": lambda df, p: _empty(),
}


def compute_overlays(strategy_name: str, params: dict | None, df: pd.DataFrame) -> dict:
    """依策略名算指標疊圖資料。未知策略 / 空資料 / 計算失敗 → 安全回空。"""
    if df is None or df.empty or "timestamp" not in df.columns:
        return _empty()
    builder = OVERLAY_BUILDERS.get(strategy_name)
    if builder is None:
        return _empty()
    try:
        return builder(df, params or {})
    except Exception:
        return _empty()  # 畫不出指標不該擋圖表本體
