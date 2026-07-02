"""
技術指標封裝（pandas-ta-classic）── 導入 pandas-ta-classic
==============================================================
集中放「用 pandas-ta-classic 算指標」的薄封裝，讓策略要用時直接 import，
不必每支策略各自處理欄位相容/缺欄防呆。

為什麼包一層？
- 現有 8 支策略多半只吃 close 欄（有的用 rolling 高低點近似）。pandas-ta 的
  ADX/ATR 等需要 high/low/close，但本專案的 K 線（market_data.get_bars）本來就有
  完整 OHLCV，故優先用真高低；萬一缺欄（例如測試傳純 close）就退回用 close 當高低，
  保證不崩。
- 指標庫換版 / 換來源時，只要改這一個檔。
"""

import pandas as pd

import pandas_ta_classic as ta


def _hlc(df: pd.DataFrame):
    """取出 high/low/close 三欄；缺 high/low 就用 close 代替（防呆，不崩）。"""
    close = df["close"]
    high = df["high"] if "high" in df.columns else close
    low = df["low"] if "low" in df.columns else close
    return high, low, close


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """
    平均真實波幅 ATR（Average True Range），回傳與 df 索引對齊的 Series。
    M4 ExitPolicy 用它算「stop = entry − k×ATR」；缺 high/low 時退回 close（防呆）。
    資料不足（不到 length+1 根）時該位置為 NaN——呼叫端要自己判 NaN 誠實跳過。
    """
    high, low, close = _hlc(df)
    out = ta.atr(high=high, low=low, close=close, length=length)
    if out is None:
        return pd.Series(dtype=float)
    return out


def swing_lows(df: pd.DataFrame, left: int = 3, right: int = 3) -> pd.Series:
    """
    偵測「已確認的 swing 低點」，回傳與 df 對齊的布林 Series。
    第 j 根是 swing low ＝ low[j] 是 [j−left, j+right] 視窗內的最低。

    ★防未來函數：確認一個 swing low 需要它右邊再走 right 根——
    站在第 i 根做決策時，只能採用 j ≤ i − right 的點
    （j 更靠近 i 的旗標要用到 i 之後的資料，等於偷看未來）。
    M4 SwingLowPolicy / M5 HH-HL、BOS 過濾器共用這份偵測，勿各自重造。
    """
    _, low, _ = _hlc(df)
    # 嚴格定義：低點必須「嚴格低於」左邊 left 根與右邊 right 根的最低
    # （用 ≤ 的話水平盤每根都等於視窗 min、全被誤判成 swing）。
    left_min = low.rolling(left).min().shift(1)      # 左邊 left 根的最低
    right_min = low.rolling(right).min().shift(-right)  # 右邊 right 根的最低
    # NaN（頭尾不足根數）比較恆 False → 自動排除「右邊還沒確認」的點
    return (low < left_min) & (low < right_min)


def swing_highs(df: pd.DataFrame, left: int = 3, right: int = 3) -> pd.Series:
    """偵測「已確認的 swing 高點」（對稱版，見 swing_lows 的防未來函數說明）。"""
    high, _, _ = _hlc(df)
    left_max = high.rolling(left).max().shift(1)
    right_max = high.rolling(right).max().shift(-right)
    return (high > left_max) & (high > right_max)


def adx_components(df: pd.DataFrame, length: int = 14):
    """
    算 ADX 三要素，回 (adx, di_plus, di_minus) 三條 Series（已對齊 df 索引）。

    - adx       ：趨勢「強度」（不分方向），>25 常視為有明顯趨勢
    - di_plus   ：上升動向強度（+DI）
    - di_minus  ：下降動向強度（−DI）
    di_plus 在上＝偏多、di_minus 在上＝偏空；ADX 夠大才代表這個方向「有力」。
    """
    high, low, close = _hlc(df)
    out = ta.adx(high=high, low=low, close=close, length=length)
    if out is None or out.empty:
        empty = pd.Series(dtype=float)
        return empty, empty, empty
    return out[f"ADX_{length}"], out[f"DMP_{length}"], out[f"DMN_{length}"]
