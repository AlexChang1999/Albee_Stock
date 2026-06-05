"""
全自動回測掃描器（Auto-Backtest Optimizer）── Phase 5
=====================================================
一個按鈕，程式自己決定回測方式：把「8 種策略 × 各自的參數網格」全部跑一遍，
依期望值 EV 由高到低排名，挑出最佳組合。使用者不用懂參數，只要選股票按下去。

設計重點（為什麼這樣寫）：
- **資料只抓一次**：run_backtest() 每呼叫一次就連線抓一次 K 線，掃描幾十組會很慢、
  又狂打資料源。這裡先用 market_data.get_bars() 抓「一份」歷史資料，之後所有組合
  都在這同一份 df 上跑（呼叫 backtest_engine._run_on_df），快又省流量。
- **挑策略看 EV**：排名鍵用 expected_value（每筆交易的平均賺賠金額），與專案其他地方
  「依 EV 排序」一致。完全沒交易的組合 EV=0，自然會被有正期望的組合擠到後面。
- **參數網格刻意精簡**：每個策略 2~3 個值就好，總組合數控制在數十組，回測秒級完成，
  也避免存進 DB 的紀錄爆量。想更精細，之後再加值即可（鬆耦合）。
"""

from itertools import product

from backend.services import market_data
from backend.services.backtest_engine import _run_on_df
from backend.strategies import get_strategy


# ---------- 參數網格（每個策略要掃哪些參數組合） ----------
# 格式：策略代號 -> { 參數名: [要嘗試的值, ...] }
# itertools.product 會把同一策略各參數的值「全互相搭配」展開成多組。
# 值刻意取少而關鍵，讓總組合數維持在數十組（快、且歷史紀錄不爆量）。
PARAM_GRIDS = {
    "ma_crossover": {
        "short_window": [5, 10, 20],
        "long_window": [30, 60, 120],
    },
    "rsi": {
        "period": [9, 14],
        "oversold": [25, 30],
        "overbought": [70, 75],
    },
    "macd": {
        "fast": [8, 12],
        "slow": [21, 26],
        "signal": [9],
    },
    "bollinger": {
        "period": [14, 20],
        "num_std": [2, 2.5],
    },
    "donchian": {
        "period": [10, 20, 30],
    },
    "stochastic": {
        "k_period": [9, 14, 21],
        "d_period": [3],
    },
    "momentum": {
        "period": [10, 20],
        "threshold": [3, 5],
    },
    "williams_r": {
        "period": [10, 14, 21],
    },
    "adx_trend": {
        "period": [14, 20],
        "adx_threshold": [20, 25],
    },
}


def _iter_param_combos(grid: dict):
    """
    把一個策略的參數網格展開成一組組 dict。
    例如 {"a":[1,2], "b":[9]} -> {"a":1,"b":9}, {"a":2,"b":9}。
    """
    keys = list(grid.keys())
    for values in product(*(grid[k] for k in keys)):
        yield dict(zip(keys, values))


def _is_valid_combo(strategy_key: str, params: dict) -> bool:
    """
    過濾掉邏輯上不合理的參數組合（例如短均線 >= 長均線、快線 >= 慢線）。
    這類組合跑出來沒意義，先剔除省時間。
    """
    if strategy_key == "ma_crossover":
        return params["short_window"] < params["long_window"]
    if strategy_key == "macd":
        return params["fast"] < params["slow"]
    return True


def run_auto_backtest(
    symbol: str,
    days: int = 365,
    initial_cash: float = 10000.0,
    source: str = "alpaca",
) -> dict:
    """
    對某檔股票做「全自動掃描」：跑遍所有策略 × 參數組合，依 EV 排名。

    :param symbol: 股票代號（會轉大寫）
    :param days: 回測往前抓幾天的資料
    :param initial_cash: 每組回測的初始資金（統一，才能公平比較）
    :param source: 資料源，"alpaca"（預設）或 "yfinance"
    :return: dict，含最佳組合 best、完整排行榜 leaderboard、掃描統計等。
             （這裡只算、不存 DB；存檔交給 router，職責分離。）
    """
    symbol = symbol.upper()

    # 1) 資料只抓一次，之後所有組合共用（關鍵效能設計）
    df = market_data.get_bars(symbol, days=days, source=source)
    if df.empty:
        raise ValueError(f"抓不到 {symbol} 的歷史資料")
    data_points = len(df)

    # 2) 逐策略、逐參數組合在同一份 df 上跑回測
    results = []
    for strategy_key, grid in PARAM_GRIDS.items():
        for params in _iter_param_combos(grid):
            if not _is_valid_combo(strategy_key, params):
                continue
            strategy = get_strategy(strategy_key, params)
            metrics = _run_on_df(strategy, df, initial_cash)
            # 補上識別資訊（_run_on_df 只回績效，不含這次是哪個策略）
            metrics["symbol"] = symbol
            metrics["strategy"] = strategy_key
            metrics["days"] = days
            metrics["data_points"] = data_points
            results.append({"strategy_key": strategy_key, "params": params, "metrics": metrics})

    # 3) 依期望值 EV 由高到低排名（與專案其他「挑策略看 EV」一致）；
    #    EV 相同時用「策略總報酬」當第二排序鍵，讓賺比較多的排前面。
    def _rank_key(r):
        m = r["metrics"]
        ev = m.get("expected_value")
        ev = ev if isinstance(ev, (int, float)) else float("-inf")
        ret = m.get("total_return_pct") or 0.0
        return (ev, ret)

    results.sort(key=_rank_key, reverse=True)

    best = results[0] if results else None
    return {
        "symbol": symbol,
        "days": days,
        "initial_cash": initial_cash,
        "data_points": data_points,
        "combos_tested": len(results),
        "strategies_tested": len(PARAM_GRIDS),
        "best": best,            # 冠軍組合（含完整 metrics）
        "leaderboard": results,  # 全部組合，已依 EV 排好
    }
