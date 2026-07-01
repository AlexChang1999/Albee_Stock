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

import logging

import pandas as pd

from backend.config import settings
from backend.services import bar_cache
from backend.services.analytics import extended_metrics
from backend.strategies import get_strategy, Signal

logger = logging.getLogger(__name__)

# Alpaca 免費版歷史資料可靠範圍上限（天）。超過這個長度（≈5 年）想回測，
# Alpaca 免費版抓不到，自動改走 yfinance（可回溯 20–50 年）。2000→2026 ≈ 9500 天。
ALPACA_MAX_DAYS = 1825


def _resolve_source(source: str, days: int) -> str:
    """
    長區間自動選資料源：用 alpaca 但 days 超過免費版可靠範圍時，自動改 yfinance。
    顯式想用 yfinance 的呼叫端不受影響；顯式 alpaca 但超長則覆寫並落 log（誠實告知）。
    """
    if source == "alpaca" and days > ALPACA_MAX_DAYS:
        logger.info(
            "回測區間 %d 天超過 Alpaca 免費版可靠範圍(%d)，自動改用 yfinance 抓長歷史",
            days, ALPACA_MAX_DAYS,
        )
        return "yfinance"
    return source


def _simulate_from_signals(
    signals: list, df: pd.DataFrame, initial_cash: float, reasons: list | None = None,
    commission_bps: float = 0.0, slippage_bps: float = 0.0,
) -> dict:
    """
    吃「每根 K 棒一個訊號」的序列，跑全進全出的資金模擬並算出全套績效。

    這是回測的「共用核心」：事件式引擎（_run_on_df）與向量化引擎
    （services/vectorized_engine）都把各自算好的訊號序列丟進這裡，
    確保「模擬規則 + 績效數學」只有一份、兩條路徑結果保證一致。

    兩個「誠實化」語意（Phase 6 step-02 / step-03），預設關（成本=0），由上層帶 config 值進來：
    - **隔日成交（step-03）**：訊號在第 i 根「收盤」算出，但實盤當下早已收盤，只能用
      「下一根的開盤價」成交。故換手延到第 i+1 根，用 open[i+1]（無 open 欄退回 close[i+1]）。
      最後一根有訊號卻沒有次根 → 不成交（誠實，不無中生有一筆）。
    - **成本（step-02）**：買進成交價 ×(1+slippage)、賣出 ×(1−slippage)，買賣再各扣手續費；
      成本反映進 profit / equity_curve，EV / profit_factor / expectancy 公式不動就自動變誠實。

    :param signals: 長度同 df 的訊號序列，每格是 Signal.BUY / SELL / HOLD
    :param reasons: 對應每根的文字理由（選填，只為交易紀錄好看，不影響數字）
    :param commission_bps: 單邊手續費（basis point，萬分之一）
    :param slippage_bps: 單邊滑價（basis point）
    """
    prices = df["close"].to_numpy(dtype=float)
    # 成交價來源：隔日成交用「次根開盤價」；無 open 欄則退回次根收盤價
    # （與向量化策略「缺 high/low 用 close 代替」的退化規則同精神）。
    fill_src = df["open"].to_numpy(dtype=float) if "open" in df.columns else prices
    has_ts = "timestamp" in df.columns
    ts = df["timestamp"].astype(str).to_numpy() if has_ts else None

    commission_rate = commission_bps / 1e4
    slippage_rate = slippage_bps / 1e4

    cash = initial_cash  # 目前現金
    position = 0.0       # 目前持有股數
    entry_price = 0.0    # 買進「有效成交價」（已含滑價，算單筆盈虧用）
    trades = []          # 交易紀錄
    equity_curve = []    # 每日資產淨值（畫資金曲線用）
    equity_dates = []    # 與 equity_curve 等長的「真實日期」字串（報表用真年月，非假 2000）
    total_cost = 0.0     # 本次回測累計摩擦成本（手續費 + 滑價）
    pending = None       # 前一根 close 算出、待這一根「以成交價」換手的單：(side, reason)

    for i in range(len(prices)):
        price = float(prices[i])      # 當根收盤價，用來估市值
        date = ts[i][:10] if has_ts else str(i)

        # --- 1. 先成交「上一根決定的單」：用這一根的成交價（隔日成交語意）---
        if pending is not None:
            side, p_reason = pending
            raw_fill = float(fill_src[i])
            if side == "buy":
                eff = raw_fill * (1 + slippage_rate)        # 滑價：買在較差(較高)價
                notional = cash / (1 + commission_rate)      # 預留手續費後實際買股的金額
                qty = notional / eff
                commission = notional * commission_rate
                total_cost += commission + qty * (eff - raw_fill)
                position = qty
                cash = 0.0
                entry_price = eff
                trades.append(
                    {"date": date, "side": "buy", "price": round(eff, 2),
                     "qty": round(qty, 4), "reason": p_reason}
                )
            else:  # sell：全出
                eff = raw_fill * (1 - slippage_rate)        # 滑價：賣在較差(較低)價
                gross = position * eff
                commission = gross * commission_rate
                proceeds = gross - commission
                profit = proceeds - position * entry_price   # entry_price 已含買入成本
                total_cost += commission + position * (raw_fill - eff)
                cash += proceeds
                trades.append(
                    {"date": date, "side": "sell", "price": round(eff, 2),
                     "qty": round(position, 4), "reason": p_reason,
                     "profit": round(profit, 2)}
                )
                position = 0.0
                entry_price = 0.0
            pending = None

        # --- 2. 記錄當根收盤後的總資產（連同真實日期，供報表用真年月）---
        equity_curve.append(cash + position * price)
        equity_dates.append(date)

        # --- 3. 依當根 close 的訊號，決定「下一根」要不要換手（隔日成交）---
        signal = signals[i]
        reason = reasons[i] if reasons is not None else ""
        if signal == Signal.BUY and position == 0 and cash > 0:
            pending = ("buy", reason)
        elif signal == Signal.SELL and position > 0:
            pending = ("sell", reason)
        # 迴圈結束後 pending 仍有值 = 最後一根的訊號沒有次根可成交 → 誠實地不成交

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
        "total_cost": round(total_cost, 2),  # 本次回測累計摩擦成本（手續費 + 滑價）
        "trades": trades,
        "equity_curve": [round(e, 2) for e in equity_curve],
        "equity_dates": equity_dates,  # 與 equity_curve 等長；報表用真實日期取代假 2000
    }


def _run_on_df(
    strategy, df: pd.DataFrame, initial_cash: float,
    commission_bps: float = 0.0, slippage_bps: float = 0.0,
    features: pd.DataFrame | None = None,
) -> dict:
    """
    在一份 K 線資料上跑回測（事件式：逐根呼叫策略 generate_signal，純邏輯、不連線）。

    逐日往前走：第 i 根只看「到第 i 根為止」的資料產生訊號（不偷看未來），
    再把整串訊號交給共用核心 _simulate_from_signals 做資金模擬與績效計算
    （含成本模型與隔日成交，見該函式說明）。

    環境特徵（Phase 11 step-04，選用）：
    - features=None（預設）→ 行為與現況**完全相同**（舊策略 / 舊呼叫端零改動）。
    - features 有值 → 與 df 等長、位置對齊的「額外特徵欄」DataFrame，併進「訊號層」的 df，
      讓想用 macro / 買賣壓特徵的策略在 generate_signal 裡讀得到（例如 df["vix_level"]）。
      忽略這些欄的舊策略結果不變（向後相容）。
    - **features 只進訊號層、不進成交層**：成交永遠走 _simulate_from_signals 的次根開盤含成本，
      環境特徵不得碰成交價（Phase 11 鐵則 3，「回測=實盤」核心）。
    """
    # 訊號層用的 df：有 features 才併欄；無則就是原 df（逐位元組相同）
    if features is not None:
        sig_df = pd.concat(
            [df.reset_index(drop=True), features.reset_index(drop=True)], axis=1
        )
    else:
        sig_df = df

    # 逐根訊號交給策略的統一入口 produce_signals：
    # - 向量化策略（BaseStrategy）：預設實作＝逐根 generate_signal（行為與舊版逐位元組相同）。
    # - 事件式策略（ScriptStrategy）：覆寫成 on_bar 驅動，但壓出的訊號序列仍走同一成交核心。
    signals, reasons = strategy.produce_signals(sig_df)
    # 成交模擬只吃 price-only 的 df（features 不進成交層）
    return _simulate_from_signals(
        signals, df, initial_cash, reasons=reasons,
        commission_bps=commission_bps, slippage_bps=slippage_bps,
    )


def run_backtest(
    strategy_name: str,
    symbol: str,
    params: dict | None = None,
    days: int = 365,
    initial_cash: float = 10000.0,
    source: str = "alpaca",
    commission_bps: float | None = None,
    slippage_bps: float | None = None,
    features: pd.DataFrame | None = None,
) -> dict:
    """
    對某檔股票跑回測（會連資料源抓歷史資料，多年區間走本機快取 bar_cache）。
    :param strategy_name: 策略代號，例如 "ma_crossover"
    :param symbol: 股票代號
    :param params: 策略參數
    :param days: 回測往前抓幾天的資料
    :param initial_cash: 初始資金
    :param source: 資料源，"alpaca"（預設）或 "yfinance"
    :param commission_bps: 單邊手續費（bps）；None＝讀 config 預設
    :param slippage_bps: 單邊滑價（bps）；None＝讀 config 預設
    :param features: 選用環境特徵（與抓回的 df 等長），透傳給 _run_on_df 的訊號層；
                     None＝純價量回測（行為不變）。
    """
    # 成本預設讀全系統 config，呼叫端可顯式覆寫（含 0 = 關成本對照用）
    if commission_bps is None:
        commission_bps = settings.BACKTEST_COMMISSION_BPS
    if slippage_bps is None:
        slippage_bps = settings.BACKTEST_SLIPPAGE_BPS

    # 長區間自動選資料源：Alpaca 免費版抓不到 2000 年那麼久，超過門檻自動改 yfinance。
    source = _resolve_source(source, days)

    # 走本機快取（Phase 11 step-04）：缺區間才補抓、其餘命中快取，多年回測不每次重打 API。
    # get_bars_cached 包在 market_data.get_bars 外層、簽章相容、嚴格 ⊆ 請求區間（不洩漏未來）。
    df = bar_cache.get_bars_cached(symbol, days=days, source=source)
    if df.empty:
        raise ValueError(f"抓不到 {symbol} 的歷史資料")

    strategy = get_strategy(strategy_name, params or {})
    result = _run_on_df(
        strategy, df, initial_cash,
        commission_bps=commission_bps, slippage_bps=slippage_bps,
        features=features,
    )

    # 補上這次回測的基本資訊
    result["symbol"] = symbol
    result["strategy"] = strategy_name
    result["days"] = days
    result["data_points"] = len(df)
    # 附上 quantstats 風險調整後指標（Sharpe/Sortino/Calmar/年化波動/CAGR）。
    # 只在「單筆回測」算（optimizer 海選走 _run_on_df，不經這裡，故不拖慢掃描）。
    result["extended"] = extended_metrics(result.get("equity_curve"))
    return result
