"""
Bot 績效計算
============
根據某個 Bot 的「真實交易紀錄」(TradeLog)，算出它的績效指標，
給前端 Bot 卡片顯示（勝率 / 報酬率 / 交易次數 / 最大回撤）。

跟 backtest_engine 的差別：
- 回測是「用歷史資料模擬假設交易」。
- 這裡是「統計這個 Bot 實際下過的單」的成果。

交易配對邏輯：
- 本系統的 Bot 是「全進全出」：沒持倉才買、有持倉就全部賣。
- 所以紀錄通常是 買→賣→買→賣… 一買一賣為一組「完整買賣」(round trip)。
- 為了穩健（即使有部分成交或異常順序），這裡用「平均成本法」配對：
  買進時累加持倉與成本；賣出時用當下的平均成本算這筆賺賠。

刻意做成「純函式」（吃一個 list、吐一個 dict），不碰資料庫、不連線，
方便寫單元測試。
"""

from __future__ import annotations


def compute_bot_stats(trades: list[dict]) -> dict:
    """
    計算單一 Bot 的績效。

    :param trades: 該 Bot 的交易紀錄，每筆需有 side("buy"/"sell")、qty、price。
                   順序必須「由舊到新」(時間正序)。
    :return: 績效指標字典：
        - num_trades        : 交易筆數（買+賣的總筆數）
        - num_round_trips   : 完整買賣次數（一買一賣算一次）
        - win_rate_pct      : 勝率(%)，賺錢的完整買賣佔比
        - total_profit      : 已實現損益總額($)
        - return_pct        : 報酬率(%) = 已實現損益 / 投入成本
        - max_drawdown_pct  : 最大回撤(%)，已實現資產從高點回落的最大幅度
    """
    # 沒有任何交易：回傳一組「全為 0」的乾淨結果，前端可據此顯示 "-"
    if not trades:
        return {
            "num_trades": 0,
            "num_round_trips": 0,
            "win_rate_pct": 0.0,
            "total_profit": 0.0,
            "return_pct": 0.0,
            "max_drawdown_pct": 0.0,
        }

    position_qty = 0.0      # 目前持有股數
    position_cost = 0.0     # 目前持倉的總成本
    cost_basis_total = 0.0  # 歷來所有買進的總成本（算報酬率的分母）
    max_position_cost = 0.0 # 歷來投入的最大資金（算回撤的基準）
    realized = []           # 每次「賣出平倉」實現的損益

    for t in trades:
        side = t["side"]
        qty = float(t["qty"])
        price = float(t["price"]) if t.get("price") is not None else 0.0

        if side == "buy":
            position_qty += qty
            position_cost += price * qty
            cost_basis_total += price * qty
            if position_cost > max_position_cost:
                max_position_cost = position_cost

        elif side == "sell":
            # 沒有持倉卻出現賣單（資料異常），跳過不計
            if position_qty <= 0:
                continue
            # 最多只能賣掉手上有的股數
            sell_qty = min(qty, position_qty)
            avg_entry = position_cost / position_qty  # 持倉平均成本
            profit = (price - avg_entry) * sell_qty
            realized.append(profit)
            # 平倉後扣掉對應的持倉與成本
            position_cost -= avg_entry * sell_qty
            position_qty -= sell_qty

    num_round_trips = len(realized)
    wins = [p for p in realized if p > 0]
    win_rate = (len(wins) / num_round_trips * 100) if num_round_trips else 0.0
    total_profit = sum(realized)
    return_pct = (total_profit / cost_basis_total * 100) if cost_basis_total > 0 else 0.0

    # --- 最大回撤 ---
    # 以「投入的最大資金」當作起始資產基準，疊加每次平倉的已實現損益，
    # 形成一條已實現資產曲線，再算它從高點回落的最大幅度。
    max_dd = 0.0
    if max_position_cost > 0 and realized:
        equity = max_position_cost
        peak = equity
        for profit in realized:
            equity += profit
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak * 100 if peak > 0 else 0.0
            if drawdown > max_dd:
                max_dd = drawdown

    return {
        "num_trades": len(trades),
        "num_round_trips": num_round_trips,
        "win_rate_pct": round(win_rate, 2),
        "total_profit": round(total_profit, 2),
        "return_pct": round(return_pct, 2),
        "max_drawdown_pct": round(max_dd, 2),
    }


def compute_round_trip_returns(trades: list[dict]) -> list[dict]:
    """
    把交易紀錄配成「完整買賣回合」，回傳每回合的明細（時間正序）。

    維運安全軌 H3（tracking error 對帳）的左半邊資料源：拿每回合的
    **已實現報酬率 %** 去跟回測的 OOS expectancy_pct 比（單位都是 %，
    才能跨「回測全進全出複利 vs Paper 固定 trade_amount」比較）。

    配對邏輯與 compute_bot_stats 同一套「平均成本法」（買進累加持倉成本、
    賣出用平均進場價算損益），邊界行為也一致：沒持倉的賣單跳過、部分成交按比例。

    :param trades: 交易紀錄（時間正序），每筆需有 side("buy"/"sell")、qty、price；
                   可選 created_at（帶進回合的 closed_at，沒有就 None）。
    :return: 每回合一個 dict：
        - profit     : 該回合已實現損益($)
        - entry_cost : 該回合的進場成本($)＝平均進場價 × 賣出股數
        - return_pct : 已實現報酬率(%) = profit / entry_cost × 100
        - closed_at  : 平倉那筆賣單的時間（trades 沒帶就 None）
    """
    position_qty = 0.0
    position_cost = 0.0
    round_trips: list[dict] = []

    for t in trades or []:
        side = t.get("side")
        qty = float(t.get("qty") or 0)
        price = float(t["price"]) if t.get("price") is not None else 0.0

        if side == "buy":
            position_qty += qty
            position_cost += price * qty

        elif side == "sell":
            if position_qty <= 0:
                continue  # 沒持倉卻出現賣單（資料異常），跳過不計
            sell_qty = min(qty, position_qty)
            avg_entry = position_cost / position_qty
            entry_cost = avg_entry * sell_qty
            profit = (price - avg_entry) * sell_qty
            round_trips.append({
                "profit": round(profit, 4),
                "entry_cost": round(entry_cost, 4),
                "return_pct": round(profit / entry_cost * 100, 4) if entry_cost > 0 else 0.0,
                "closed_at": t.get("created_at"),
            })
            position_cost -= entry_cost
            position_qty -= sell_qty

    return round_trips
