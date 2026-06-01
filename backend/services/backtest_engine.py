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
"""

import pandas as pd

from backend.services.alpaca_client import alpaca_client
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
        "num_round_trips": len(sells),
        "win_rate_pct": round(win_rate, 2),
        "trades": trades,
        "equity_curve": [round(e, 2) for e in equity_curve],
    }


def run_backtest(
    strategy_name: str,
    symbol: str,
    params: dict | None = None,
    days: int = 365,
    initial_cash: float = 10000.0,
) -> dict:
    """
    對某檔股票跑回測（會連 Alpaca 抓歷史資料）。
    :param strategy_name: 策略代號，例如 "ma_crossover"
    :param symbol: 股票代號
    :param params: 策略參數
    :param days: 回測往前抓幾天的資料
    :param initial_cash: 初始資金
    """
    df = alpaca_client.get_bars(symbol, days=days)
    if df.empty:
        raise ValueError(f"抓不到 {symbol} 的歷史資料")

    strategy = get_strategy(strategy_name, params or {})
    result = _run_on_df(strategy, df, initial_cash)

    # 補上這次回測的基本資訊
    result["symbol"] = symbol
    result["strategy"] = strategy_name
    result["days"] = days
    result["data_points"] = len(df)
    return result
