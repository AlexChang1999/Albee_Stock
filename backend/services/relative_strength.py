"""
相對強度 RS（Relative Strength）── Phase 16 M7
==============================================
把 `scripts/fund_flow_report.py` 的「報酬 − SPY 報酬」邏輯泛化成可重用服務：
個股（或 ETF）對基準的多窗口相對強度，給股票池瘦身「同 sector 留 RS 最強」用。

定義（簡單、透明、可驗證）：
    rs(n) = 標的近 n 根報酬% − 基準近 n 根報酬%
    composite = 可用窗口 rs 的平均（等權；窗口資料不足就跳過該窗、不硬湊）

純函式：只吃兩份 K 線 DataFrame（欄位含 close），不碰網路/DB。
"""

from __future__ import annotations

import pandas as pd

# 預設多窗口（日 K 語意：1 日 / 1 週 / 1 個月）
DEFAULT_WINDOWS = (1, 5, 20)


def _return_pct(df: pd.DataFrame, lookback_bars: int) -> float | None:
    """近 n 根報酬%（close[-1] / close[-1-n] − 1）。資料不足回 None（誠實缺值）。"""
    if df is None or "close" not in df.columns or len(df) <= lookback_bars:
        return None
    close = df["close"].astype(float)
    base = float(close.iloc[-1 - lookback_bars])
    if base <= 0:
        return None
    return (float(close.iloc[-1]) / base - 1) * 100


def rs_score(symbol_df: pd.DataFrame, benchmark_df: pd.DataFrame,
             lookback_bars: int) -> float | None:
    """單一窗口 RS：標的報酬% − 基準報酬%。任一邊資料不足回 None。"""
    r = _return_pct(symbol_df, lookback_bars)
    b = _return_pct(benchmark_df, lookback_bars)
    if r is None or b is None:
        return None
    return round(r - b, 2)


def rs_scores(symbol_df: pd.DataFrame, benchmark_df: pd.DataFrame,
              windows: tuple[int, ...] = DEFAULT_WINDOWS) -> dict:
    """
    多窗口 RS + 綜合分數。

    :return: {"rs_1": ..., "rs_5": ..., "rs_20": ..., "rs_composite": ...}
             （鍵名依 windows 生成；全部窗口都算不出來時 composite 為 None）
    """
    out: dict = {}
    vals = []
    for n in windows:
        v = rs_score(symbol_df, benchmark_df, n)
        out[f"rs_{n}"] = v
        if v is not None:
            vals.append(v)
    out["rs_composite"] = round(sum(vals) / len(vals), 2) if vals else None
    return out
