"""
回看長度推算（Phase 6 step-01）
================================
依「策略 + 參數」推算「至少要抓幾天的 K 線」才算得準，回測與實盤**共用同一支函式**。

為什麼需要它？
- 舊版實盤寫死 `days=60`。但例如 `long_window=120` 的均線策略，60 天根本算不出長均線，
  策略只會一直回 HOLD，行為跟回測（抓 365 天）完全不同——靜默失準。
- 把「需要幾根 K 棒」交給這支純函式統一推算，實盤就不會再抓太少。

兩個步驟：
1. `min_bars_required`：依策略關鍵參數，算出「至少需要幾根 K 棒」(交易日)。
   數字直接對齊各策略 `generate_signal` 裡那行「資料不足」的門檻，保證一致。
2. `required_lookback_days`：把「需要的 K 棒數」換算成「日曆天數」，並保留緩衝：
   - ×1.6 暖機緩衝：剛好夠算 ≠ 算得穩（EWM / ADX 尤其需要更長暖機才收斂）。
   - 交易日 → 日曆日：一週約 5 個交易日對應 7 個日曆日，故 ×7/5。
   - 再 +5 天吸收國定假日。
"""

import math

# 未知策略時的保守預設「最小 K 棒數」。
# 寧可多抓一點也不要算不出指標（多抓只是多花一點額度，少抓會靜默失準）。
_DEFAULT_MIN_BARS = 60


def min_bars_required(strategy_key: str, params: dict | None = None) -> int:
    """
    依策略與參數，回傳「至少需要幾根 K 棒」才能算出有效訊號（交易日數）。

    這裡的公式刻意對齊各策略 `generate_signal` 開頭的「資料不足」判斷，
    例如 ma_crossover 是 `len(df) < long_window + 1`，這裡就回 `long_window + 1`。
    """
    p = params or {}

    if strategy_key == "ma_crossover":
        return int(p.get("long_window", 20)) + 1
    if strategy_key == "rsi":
        return int(p.get("period", 14)) + 1
    if strategy_key == "macd":
        return int(p.get("slow", 26)) + int(p.get("signal", 9))
    if strategy_key == "bollinger":
        return int(p.get("period", 20))
    if strategy_key == "donchian":
        return int(p.get("period", 20)) + 1
    if strategy_key == "stochastic":
        return int(p.get("k_period", 14)) + int(p.get("d_period", 3))
    if strategy_key == "momentum":
        return int(p.get("period", 10)) + 1
    if strategy_key == "williams_r":
        return int(p.get("period", 14))
    if strategy_key == "adx_trend":
        return int(p.get("period", 14)) * 2
    if strategy_key == "snr_3_0":
        # 對齊 snr_3_0.generate_signal 的「資料不足」門檻：zone 回看 + ATR 暖機 + swing 右側確認
        return (int(p.get("zone_lookback", 80)) + int(p.get("atr_period", 14))
                + int(p.get("swing_window", 3)) + 1)

    # 未知策略：給保守預設，至少不會抓太少而靜默失準
    return _DEFAULT_MIN_BARS


def required_lookback_bars(strategy_key: str, params: dict | None = None) -> int:
    """
    「至少需要幾根 K 棒」含暖機緩衝（不分時間框架——bar 數是框架無關的語意）。

    ×1.6 暖機緩衝：剛好夠算不代表算得穩（rolling/EWM/ADX 需要更長暖機才收斂）。
    """
    return math.ceil(min_bars_required(strategy_key, params) * 1.6)


def required_lookback_days(
    strategy_key: str, params: dict | None = None, timeframe: str = "1Day"
) -> int:
    """
    把「策略需要的最小 K 棒數」換算成「往前抓幾個日曆天」，並保留緩衝。

    回測與實盤共用此函式算回看長度，消滅「實盤 60、回測 365」的硬編碼分岔。
    :param timeframe: K 線時間框架。日內框架一天有多根 bar，同樣的 bar 數
                      換算出來的日曆天少得多（見 timeframes.bars_to_calendar_days）。
                      預設 "1Day" —— 既有呼叫行為不變。
    """
    bars_with_buffer = required_lookback_bars(strategy_key, params)

    if timeframe != "1Day":
        from backend.services.timeframes import bars_to_calendar_days
        return bars_to_calendar_days(bars_with_buffer, timeframe)

    # 交易日 → 日曆日（週末），再 +5 吸收國定假日
    return math.ceil(bars_with_buffer * 7 / 5) + 5
