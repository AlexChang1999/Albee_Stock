"""
分數凱利部位（Fractional Kelly Position Sizing）── Phase 7 step-04
================================================================
回答「這檔可投多少量（%）」。用「勝率 + 賠率」把建議部位用數學算出來，
取代每個 Bot 寫死的固定 trade_amount。

凱利公式（單筆下注版）：
    f* = W − (1 − W) / R
      W = 勝率（用 OOS 勝率）
      R = 賠率 = 平均賺 / 平均賠（用 OOS avg_win / avg_loss）
      f* = 建議下注本金比例

實務只取 ¼~½ 個 f*（分數凱利）。全凱利波動極大，且 W/R 是「估計值」，估錯時全凱利會爆倉。
所以三重保守：**用 OOS 的 W/R + 只取分數凱利 + 硬上限夾住**。

重用：回測 metrics 的 win_rate_pct / avg_win / avg_loss（含成本、OOS）正是凱利該吃的誠實輸入。
部位算出來後仍要過 Phase 6 step-05 的 plan_capital（總曝險受購買力與保留比例約束）。
"""

from backend.config import settings


def kelly_fraction(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    *,
    fraction: float | None = None,
    cap: float | None = None,
) -> float:
    """
    算「該下注本金的多少比例」（純函式，0~cap 之間）。

    :param win_rate: 勝率（0~1）。
    :param avg_win: 平均每筆賺多少（正值金額）。
    :param avg_loss: 平均每筆賠多少（正值金額，取賠的幅度）。
    :param fraction: 分數凱利係數（取 f* 的比例）；None 用 settings.KELLY_FRACTION。
    :param cap: 單檔部位上限（占本金比例）；None 用 settings.KELLY_MAX_FRACTION。
    :return: 建議下注比例。沒有正期望（f*<=0）或缺賠率資訊 → 回 0（不下注）。
    """
    fraction = fraction if fraction is not None else settings.KELLY_FRACTION
    cap = cap if cap is not None else settings.KELLY_MAX_FRACTION

    # 沒有賠率原料（賺或賠任一為 0/負）→ 無法算賠率，保守不下注
    if avg_win <= 0 or avg_loss <= 0:
        return 0.0

    w = max(0.0, min(1.0, float(win_rate)))
    r = avg_win / avg_loss  # 賠率
    f_star = w - (1 - w) / r

    # 負期望（含成本後沒賺頭）→ 不下注
    if f_star <= 0:
        return 0.0

    f = f_star * fraction
    return min(f, cap)


def kelly_trade_amount(
    available_cash: float,
    win_rate_pct: float,
    avg_win: float,
    avg_loss: float,
    num_round_trips: int,
    *,
    fraction: float | None = None,
    cap: float | None = None,
    min_round_trips: int | None = None,
) -> float:
    """
    把回測 OOS metrics 換成「這檔該配多少現金」。

    銜接層：吃回測 metrics 的欄位（win_rate_pct 是百分比、avg_win/avg_loss 是金額），
    算出建議部位金額。**樣本太少（回合數不足）時 W/R 不可信 → 回 0（不下注）**。

    :param available_cash: 可動用現金。
    :param win_rate_pct: OOS 勝率（百分比 0~100）。
    :param num_round_trips: OOS 完整買賣回合數（樣本充足度）。
    :return: 建議部位金額（已被 cap 夾住、再被現金量約束）；不下注時回 0。
    """
    min_round_trips = min_round_trips if min_round_trips is not None else settings.KELLY_MIN_ROUND_TRIPS

    # 樣本不足 → W/R 不可信，保守不下注（呼叫端可據此跳過或退回固定小額）
    if num_round_trips < min_round_trips:
        return 0.0

    f = kelly_fraction(
        win_rate_pct / 100.0, avg_win, avg_loss, fraction=fraction, cap=cap
    )
    return max(0.0, float(available_cash)) * f
