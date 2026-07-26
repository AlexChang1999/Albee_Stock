"""
券商端保護單規劃（維運安全軌 H1）
==================================
「該掛什麼保護單」的決策邏輯，全部做成純函式（不碰網路/DB，好測試）。

背景：止盈/止損原本靠本機每輪輪詢（bot_manager + risk_manager.check_exit），
電腦當機/斷網/重開機期間止損失效、持倉裸奔。改法：進場成交後把止損
「託管」到券商端（Alpaca GTC stop / trailing stop 單），本機斷電也照樣執行。
本機輪詢保留當備援（belt-and-suspenders）。

注意：Alpaca 的 stop / trailing stop 單只支援「整股」（碎股僅限當日市價/限價單），
所以掛保護單的 Bot 進場股數必須取整（見 whole_share_qty）。
"""

import math


def whole_share_qty(trade_amount: float, price: float) -> int:
    """
    券商端 stop 只支援整股 → 進場股數取整（floor）。

    :param trade_amount: 這次想投入的金額（美元）
    :param price: 現價
    :return: 整數股數；金額買不起 1 股（或輸入不合理）回 0，呼叫端應跳過並記審計
    """
    if not trade_amount or not price or trade_amount <= 0 or price <= 0:
        return 0
    return math.floor(trade_amount / price)


def plan_protective_order(
    entry_price: float,
    *,
    stop_loss_pct: float | None,
    trailing_stop_pct: float | None,
) -> dict | None:
    """
    決定進場後要在券商端掛哪種保護賣單。

    優先序：追蹤止損 > 固定止損（與 Bot 風控設定的語意一致——
    trailing 有設就用 Alpaca 原生 trailing stop，券商端自己追盤中最高價，
    比本機 60 秒輪詢的 peak 精準且斷電不失效）。

    v1 邊界：止盈不託管（OCO 複雜度高、止盈晚 60 秒觸發不致命），仍走本機輪詢。

    :param entry_price: 進場價（算 stop 觸發價用）
    :return: {"type": "trailing_stop", "trail_percent": 3.0}
             或 {"type": "stop", "stop_price": 95.0}
             或 None（兩個風控都沒設 → 不掛）
    """
    if not entry_price or entry_price <= 0:
        return None

    if trailing_stop_pct and trailing_stop_pct > 0:
        # Alpaca 的 trail_percent 是「百分比數字」（3.0 = 回檔 3%），
        # 專案內風控欄位是小數（0.03 = 3%），這裡轉換
        return {"type": "trailing_stop", "trail_percent": round(trailing_stop_pct * 100, 2)}

    if stop_loss_pct and stop_loss_pct > 0:
        # Alpaca 要求 $1 以上股票的 stop_price 最多 2 位小數
        return {"type": "stop", "stop_price": round(entry_price * (1 - stop_loss_pct), 2)}

    return None


def protective_order_from_exit_plan(exit_plan: dict | None) -> dict | None:
    """
    M4 可插拔出場政策版的保護單規劃：直接吃持久化的 ExitPlan dict
    （bot.exit_plan），輸出格式與 plan_protective_order 相同
    （order_matches_plan 的自癒對帳直接沿用，零改動）。

    優先序同 plan_protective_order：trailing > stop。
    政策無 stop 也無 trailing（如 ATR 資料不足的誠實空計畫）→ 回 None 不掛。
    """
    if not exit_plan:
        return None

    trailing_pct = exit_plan.get("trailing_pct")
    if trailing_pct and trailing_pct > 0:
        return {"type": "trailing_stop", "trail_percent": round(trailing_pct * 100, 2)}

    stop_price = exit_plan.get("stop_price")
    if stop_price and stop_price > 0:
        # Alpaca 要求 $1 以上股票的 stop_price 最多 2 位小數
        return {"type": "stop", "stop_price": round(stop_price, 2)}

    return None


def order_matches_plan(
    order_type: str,
    stop_price: float | None,
    trail_percent: float | None,
    plan: dict,
    *,
    tol_pct: float = 0.5,
) -> bool:
    """
    reconcile 自癒用：券商端「現在掛著的單」與「應該掛的計畫」是否一致。
    不一致（例如使用者改了 stop_loss_pct）→ 呼叫端撤舊掛新。

    :param order_type: 券商端訂單型別字串（"stop" / "trailing_stop"）
    :param stop_price: 券商端訂單的觸發價（stop 單才有）
    :param trail_percent: 券商端訂單的回檔百分比（trailing 單才有）
    :param plan: plan_protective_order 的輸出
    :param tol_pct: 數值容差（%），預設 0.5%——浮點/四捨五入差異不算漂移
    """
    if not plan or order_type != plan["type"]:
        return False

    def _close(a: float | None, b: float | None) -> bool:
        """兩數在容差內視為相同（None 任一邊都算不同）。"""
        if a is None or b is None or b == 0:
            return False
        return abs(a - b) / abs(b) * 100 <= tol_pct

    if plan["type"] == "stop":
        return _close(stop_price, plan["stop_price"])
    return _close(trail_percent, plan["trail_percent"])
