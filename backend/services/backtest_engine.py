"""
回測引擎
========
用歷史 K 線資料，模擬策略在過去一段時間的買賣表現。

核心觀念：
- 逐日往前走（walk-forward）：在第 N 天做決策時，只給策略「到第 N 天為止」
  的資料，絕不讓它看到未來（避免「未來函數 / look-ahead bias」這個經典錯誤）。
- 全進全出：收到 buy 訊號就用全部現金買、收到 sell 訊號就全部賣，最單純。

回傳的績效指標：
- total_return_pct ：策略總報酬率(%)
- buy_and_hold_pct ：同期間「單純買進持有」的報酬率(%)（拿來比較）
- max_drawdown_pct ：最大回撤(%)，資產從最高點跌下來的最大幅度（風險指標）
- win_rate_pct     ：勝率(%)，賺錢的賣出次數佔比

期望值（EV）相關 ── Phase 5 新增，挑策略要看這組，不是只看勝率：
- num_wins / num_losses ：賺錢 / 賠錢的完整買賣（round trip）筆數
- loss_rate_pct         ：敗率(%)，與 win_rate_pct 對稱
- avg_win / avg_loss    ：平均每筆賺多少 / 賠多少（金額；avg_loss 取正值表示賠的幅度）
- expected_value        ：★期望值 EV／筆＝每做一筆交易平均賺賠多少「金額」。
                          公式 EV = 勝率×平均賺 − 敗率×平均賠 = 總盈虧 / 交易筆數。
                          EV>0 才有正期望；高勝率但 EV<0（小賺多次、一次大賠）很危險。
- expectancy_pct        ：EV 佔初始資金的百分比（不同資金規模可互相比較）
- profit_factor         ：獲利因子＝總賺 / 總賠（>1 才賺錢；無任何虧損時回 None）
"""

import pandas as pd

from backend.services import market_data
from backend.services.analytics import extended_metrics
from backend.strategies import get_strategy, Signal


def _run_on_df(strategy, df: pd.DataFrame, initial_cash: float) -> dict:
    """
    在一份 K 線資料上跑回測（純邏輯，不連線，方便測試）。
    :param strategy: 策略實例
    :param df: K 線資料（需有 close 欄，時間由舊到新）
    :param initial_cash: 初始資金
    """
    cash = initial_cash # 目前現金
    position = 0.0      # 目前持有股數
    entry_price = 0.0   # 買進時的價格（算單筆盈虧用）
    trades = []         # 交易紀錄
    equity_curve = []   # 每日資產淨值（畫資金曲線用）

    for i in range(len(df)):
        # 只給策略「到今天為止」的資料（避免偷看未來）
        window = df.iloc[: i + 1]
        row = df.iloc[i]
        price = float(row["close"])
        # 日期（若有 timestamp 欄就取，只留日期部分）
        date = str(row["timestamp"])[:10] if "timestamp" in df.columns else str(i)

        signal, reason = strategy.generate_signal(window)

        if signal == Signal.BUY and position == 0 and cash > 0:
            # 全進：用所有現金買入
            qty = cash / price
            position = qty
            cash = 0.0
            entry_price = price
            trades.append(
                {"date": date, "side": "buy", "price": round(price, 2),
                 "qty": round(qty, 4), "reason": reason}
            )
        elif signal == Signal.SELL and position > 0:
            # 全出：賣掉所有持倉
            proceeds = position * price
            profit = (price - entry_price) * position
            cash += proceeds
            trades.append(
                {"date": date, "side": "sell", "price": round(price, 2),
                 "qty": round(position, 4), "reason": reason,
                 "profit": round(profit, 2)}
            )
            position = 0.0
            entry_price = 0.0

        # 今天結束時的總資產 = 現金 + 持股市值
        equity_curve.append(cash + position * price)

    # --- 計算各項績效 ---
    final_equity = equity_curve[-1] if equity_curve else initial_cash
    total_return = (final_equity - initial_cash) / initial_cash * 100

    # 最大回撤：資產從歷史最高點跌下來的最大幅度
    max_dd = 0.0
    peak = equity_curve[0] if equity_curve else initial_cash
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        drawdown = (peak - eq) / peak * 100 if peak > 0 else 0.0
        if drawdown > max_dd:
            max_dd = drawdown

    # 勝率：看每次「賣出」是賺還賠
    sells = [t for t in trades if t["side"] == "sell"]
    wins = [t for t in sells if t.get("profit", 0) > 0]
    win_rate = (len(wins) / len(sells) * 100) if sells else 0.0

    # --- 期望值（EV）相關指標 ---
    # 每筆「賣出」就是一次完整買賣（round trip），都帶 profit。
    n_round_trips = len(sells)
    profits = [t.get("profit", 0.0) for t in sells]
    win_profits = [p for p in profits if p > 0]   # 賺的筆（正值）
    loss_profits = [p for p in profits if p < 0]  # 賠的筆（負值）

    num_wins = len(win_profits)
    num_losses = len(loss_profits)
    loss_rate = (num_losses / n_round_trips * 100) if n_round_trips else 0.0

    total_win = sum(win_profits)         # 總獲利金額（正）
    total_loss = -sum(loss_profits)      # 總虧損金額（取正值表示「賠了多少」）

    # 平均每筆賺 / 賠（avg_loss 取正值）
    avg_win = (total_win / num_wins) if num_wins else 0.0
    avg_loss = (total_loss / num_losses) if num_losses else 0.0

    # ★期望值 EV／筆：每做一筆交易平均賺賠多少金額。
    #   數學上 勝率×平均賺 − 敗率×平均賠 == 總盈虧 / 交易筆數（平手筆計入分母不影響分子）。
    expected_value = (sum(profits) / n_round_trips) if n_round_trips else 0.0
    # EV 佔初始資金的百分比，讓不同本金規模可互相比較
    expectancy = (expected_value / initial_cash * 100) if initial_cash else 0.0
    # 獲利因子：總賺 / 總賠；完全沒虧損（分母 0）時回 None（前端顯示「無虧損」）
    profit_factor = (total_win / total_loss) if total_loss > 0 else None

    # Buy & Hold 對照：第一天買進、最後一天才賣的報酬率
    if len(df) > 0:
        first_price = float(df.iloc[0]["close"])
        last_price = float(df.iloc[-1]["close"])
        bh_return = (last_price - first_price) / first_price * 100
    else:
        bh_return = 0.0

    return {
        "initial_cash": initial_cash,
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return, 2),
        "buy_and_hold_pct": round(bh_return, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "num_trades": len(trades),
        "num_round_trips": n_round_trips,
        "win_rate_pct": round(win_rate, 2),
        # --- 期望值（EV）相關 ---
        "num_wins": num_wins,
        "num_losses": num_losses,
        "loss_rate_pct": round(loss_rate, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expected_value": round(expected_value, 2),
        "expectancy_pct": round(expectancy, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor is not None else None,
        "trades": trades,
        "equity_curve": [round(e, 2) for e in equity_curve],
    }


def run_backtest(
    strategy_name: str,
    symbol: str,
    params: dict | None = None,
    days: int = 365,
    initial_cash: float = 10000.0,
    source: str = "alpaca",
) -> dict:
    """
    對某檔股票跑回測（會連資料源抓歷史資料）。
    :param strategy_name: 策略代號，例如 "ma_crossover"
    :param symbol: 股票代號
    :param params: 策略參數
    :param days: 回測往前抓幾天的資料
    :param initial_cash: 初始資金
    :param source: 資料源，"alpaca"（預設）或 "yfinance"
    """
    df = market_data.get_bars(symbol, days=days, source=source)
    if df.empty:
        raise ValueError(f"抓不到 {symbol} 的歷史資料")

    strategy = get_strategy(strategy_name, params or {})
    result = _run_on_df(strategy, df, initial_cash)

    # 補上這次回測的基本資訊
    result["symbol"] = symbol
    result["strategy"] = strategy_name
    result["days"] = days
    result["data_points"] = len(df)
    # 附上 quantstats 風險調整後指標（Sharpe/Sortino/Calmar/年化波動/CAGR）。
    # 只在「單筆回測」算（optimizer 海選走 _run_on_df，不經這裡，故不拖慢掃描）。
    result["extended"] = extended_metrics(result.get("equity_curve"))
    return result
