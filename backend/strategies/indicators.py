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
