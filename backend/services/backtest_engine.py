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
from backend.services.exit_policies import ExitPolicy, FixedPctPolicy, get_exit_policy
from backend.strategies import get_strategy, Signal

logger = logging.getLogger(__name__)

# Alpaca 免費版歷史資料可靠範圍上限（天）。超過這個長度（≈5 年）想回測，
# Alpaca 免費版抓不到，自動改走 yfinance（可回溯 20–50 年）。2000→2026 ≈ 9500 天。
ALPACA_MAX_DAYS = 1825


def _resolve_source(source: str, days: int, timeframe: str = "1Day") -> str:
    """
    長區間自動選資料源：用 alpaca 但 days 超過免費版可靠範圍時，自動改 yfinance。
    顯式想用 yfinance 的呼叫端不受影響；顯式 alpaca 但超長則覆寫並落 log（誠實告知）。

    日內框架一律用 alpaca：yfinance 的分鐘級歷史太短（1m 只有 7 天、5m~30m 只有
    60 天）且無 2h/4h，alpaca 分鐘 K 反而可回溯到 2016——切換邏輯與日 K 相反。
    """
    if timeframe != "1Day":
        if source != "alpaca":
            logger.info("日內框架 %s 僅 alpaca 有足夠歷史，資料源自動改用 alpaca", timeframe)
        return "alpaca"
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
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
    trailing_stop_pct: float | None = None,
    allow_short: bool = False,
    exit_policy: ExitPolicy | None = None,
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
    :param stop_loss_pct / take_profit_pct / trailing_stop_pct:
        風控出場模擬（0.10 = 10%；None = 關，行為與舊版完全相同）。
        補上「回測=實盤」原則在出場端的缺口：實盤 Bot 有 risk_manager 的
        停損/停利/追蹤止損盤中出場，但舊回測只認策略訊號，兩邊 EV 會分岔。
        日 K 粒度的誠實近似（檢查順序與 risk_manager.check_exit 一致：停損→追蹤→停利）：
        - 觸價用當根 high/low 判斷（無該欄退回 close），觸發即以「觸價價位」成交、
          不等次根（實盤風控本來就是盤中市價出場，不是隔日）。
        - 跳空穿越停損/追蹤 → 只能成交在更差的開盤價（保守，不美化）；
          跳空開高過停利 → 成交在開盤價（如實反映較好的成交）。
        - 追蹤止損的最高價 peak 用「進場成交價起、逐根 high」更新；
          當根先用「前面 bar 為止的 peak」檢查、檢查完才併入當根 high（不偷看未來）。
        - 同一根內多重觸發只取一種（依上述順序），與實盤單次檢查一次只出一種一致。
    :param allow_short: 做空開關（預設 False＝行為與舊版完全相同：SELL 只平多）。
        True 時：SELL 且空手 → 開空（side="short"）、BUY 且持空 → 回補（side="cover"）；
        position 用「負股數」表示空單，equity = cash + position*price 公式自動正確。
        持多時 SELL 仍只平多（不直接翻倉——平倉後下一次反向訊號才進場，兩段式）。
        空單風控鏡像：停損=價格上漲 x%、停利=價格下跌 x%、追蹤用持倉期間「最低價」
        （空單風控走 % 參數語意；exit_policy 的 ExitPlan 目前只涵蓋多單）。
        ⚠️ 無保證金模型（價格大漲時空單 equity 可為負、報酬可 < -100%，如實呈現）；
        **僅供回測評估，實盤 Bot 只做多**。
    :param exit_policy: 可插拔出場政策（M4）。進場時 on_entry 拿 ExitPlan、
        逐 bar on_bar 更新（動態政策），觸價語意同上（stop→追蹤→target）。
        三個 pct 參數其實就是 FixedPctPolicy 的轉接（內部統一走政策路徑）；
        兩者同時給會拋錯（避免兩套出場規則疊加的曖昧）。
        有 stop 的每筆交易會記 r_multiple（= 損益 / 初始風險 R），彙總成 avg_r_multiple。
    """
    # --- 出場規則統一走 ExitPolicy 路徑：pct 參數轉接成 FixedPctPolicy（行為與舊版全等）---
    pcts_given = any(x is not None for x in (stop_loss_pct, take_profit_pct, trailing_stop_pct))
    if exit_policy is not None and pcts_given:
        raise ValueError("exit_policy 與 stop_loss_pct 等 % 參數不可同時使用（出場規則只能有一套）")
    if exit_policy is None and pcts_given:
        exit_policy = FixedPctPolicy(
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            trailing_stop_pct=trailing_stop_pct,
        )
    prices = df["close"].to_numpy(dtype=float)
    # 成交價來源：隔日成交用「次根開盤價」；無 open 欄則退回次根收盤價
    # （與向量化策略「缺 high/low 用 close 代替」的退化規則同精神）。
    fill_src = df["open"].to_numpy(dtype=float) if "open" in df.columns else prices
    # 風控觸價判斷用的日內高低（無該欄退回 close，退化成「只在收盤價穿越時觸發」）
    highs = df["high"].to_numpy(dtype=float) if "high" in df.columns else prices
    lows = df["low"].to_numpy(dtype=float) if "low" in df.columns else prices
    risk_on = exit_policy is not None
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
    peak_price = 0.0     # 多單持倉期間最高價（追蹤止損用；空手時無意義）
    trough_price = 0.0   # 空單持倉期間最低價（空單追蹤止損用；與 peak_price 分開存，避免雙語意）
    risk_exit_counts = {"stop_loss": 0, "take_profit": 0, "trailing_stop": 0}
    plan = None          # 目前持倉的出場計畫（ExitPlan；空手時 None）
    r_risk = 0.0         # 初始風險 R = entry − stop（每股；plan 無 stop 時 0 = 不算 r_multiple）

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
                peak_price = eff  # 追蹤止損的最高價從進場成交價起算
                if risk_on:
                    # 進場當下算出場計畫（只看到第 i 根為止的資料）；R = entry − stop
                    plan = exit_policy.on_entry(df, i, eff)
                    r_risk = (eff - plan.stop_price) if plan.stop_price else 0.0
                trades.append(
                    {"date": date, "side": "buy", "price": round(eff, 2),
                     "qty": round(qty, 4), "reason": p_reason}
                )
            elif side == "sell":  # 平多：全出
                eff = raw_fill * (1 - slippage_rate)        # 滑價：賣在較差(較低)價
                gross = position * eff
                commission = gross * commission_rate
                proceeds = gross - commission
                profit = proceeds - position * entry_price   # entry_price 已含買入成本
                total_cost += commission + position * (raw_fill - eff)
                cash += proceeds
                trade = {"date": date, "side": "sell", "price": round(eff, 2),
                         "qty": round(position, 4), "reason": p_reason,
                         "profit": round(profit, 2), "exit_reason": "signal"}
                if r_risk > 0:
                    # r_multiple = 損益 / 初始風險金額（qty × R）：+2R = 賺到 2 倍所冒風險
                    trade["r_multiple"] = round(profit / (position * r_risk), 3)
                trades.append(trade)
                position = 0.0
                entry_price = 0.0
                peak_price = 0.0
                plan = None
                r_risk = 0.0
            elif side == "short":  # 開空：賣出借券，position 記負股數
                eff = raw_fill * (1 - slippage_rate)        # 滑價：開空＝賣出，滑到更低價（不利）
                qty = cash / eff                             # 全 equity notional 開空（空手時 equity==cash）
                gross = qty * eff
                commission = gross * commission_rate
                total_cost += commission + qty * (raw_fill - eff)
                cash += gross - commission                   # 收到賣券現金（扣手續費）
                position = -qty
                entry_price = eff
                trough_price = eff  # 空單追蹤止損的最低價從進場成交價起算
                trades.append(
                    {"date": date, "side": "short", "price": round(eff, 2),
                     "qty": round(qty, 4), "reason": p_reason}
                )
            else:  # cover：回補平空
                eff = raw_fill * (1 + slippage_rate)        # 滑價：回補＝買入，滑到更高價（不利）
                qty = -position
                gross = qty * eff
                commission = gross * commission_rate
                # 鏡像多單慣例：開倉手續費已從現金扣、平倉手續費計入 profit
                profit = qty * (entry_price - eff) - commission
                total_cost += commission + qty * (eff - raw_fill)
                cash -= gross + commission
                trades.append(
                    {"date": date, "side": "cover", "price": round(eff, 2),
                     "qty": round(qty, 4), "reason": p_reason,
                     "profit": round(profit, 2), "exit_reason": "signal"}
                )
                position = 0.0
                entry_price = 0.0
                trough_price = 0.0
            pending = None

        # --- 1.5 風控出場模擬（opt-in；順序同實盤 risk_manager：停損→追蹤→停利）---
        if risk_on and position > 0 and plan is not None:
            o = float(fill_src[i])
            hi = float(highs[i])
            lo = float(lows[i])
            # 動態政策（如 vwap）逐 bar 更新計畫；靜態政策 on_bar 預設回原 plan（零開銷語意）
            plan = exit_policy.on_bar(df, i, plan, {"entry_price": entry_price, "peak_price": peak_price})
            sl_level = plan.stop_price
            trail_level = peak_price * (1 - plan.trailing_pct) if plan.trailing_pct else None
            tp_level = plan.target_price

            exit_raw, exit_kind = None, None
            if sl_level is not None and (o <= sl_level or lo <= sl_level):
                # 跳空開低穿過停損 → 只能成交在更差的開盤價（min 同時涵蓋兩種情況）
                exit_raw, exit_kind = min(o, sl_level), "stop_loss"
            elif trail_level is not None and (o <= trail_level or lo <= trail_level):
                exit_raw, exit_kind = min(o, trail_level), "trailing_stop"
            elif tp_level is not None and (o >= tp_level or hi >= tp_level):
                # 跳空開高過停利 → 成交在較好的開盤價（如實反映）
                exit_raw, exit_kind = max(o, tp_level), "take_profit"

            if exit_raw is not None:
                eff = exit_raw * (1 - slippage_rate)
                gross = position * eff
                commission = gross * commission_rate
                proceeds = gross - commission
                profit = proceeds - position * entry_price
                total_cost += commission + position * (exit_raw - eff)
                cash += proceeds
                risk_exit_counts[exit_kind] += 1
                trade = {"date": date, "side": "sell", "price": round(eff, 2),
                         "qty": round(position, 4),
                         "reason": f"風控出場：{exit_kind} 觸價 {exit_raw:.2f}",
                         "profit": round(profit, 2), "exit_reason": exit_kind}
                if r_risk > 0:
                    trade["r_multiple"] = round(profit / (position * r_risk), 3)
                trades.append(trade)
                position = 0.0
                entry_price = 0.0
                peak_price = 0.0
                plan = None
                r_risk = 0.0
            else:
                # 檢查完才把當根 high 併入 peak（當根檢查只用「前面 bar 為止」的 peak，不偷看）
                peak_price = max(peak_price, hi)

        # --- 1.6 空單風控出場（多單邏輯的完整鏡像：停損=價漲、停利=價跌、追蹤用最低價）---
        elif risk_on and position < 0:
            o = float(fill_src[i])
            hi = float(highs[i])
            lo = float(lows[i])
            sl_level = entry_price * (1 + stop_loss_pct) if stop_loss_pct else None
            trail_level = trough_price * (1 + trailing_stop_pct) if trailing_stop_pct else None
            tp_level = entry_price * (1 - take_profit_pct) if take_profit_pct else None

            exit_raw, exit_kind = None, None
            if sl_level is not None and (o >= sl_level or hi >= sl_level):
                # 跳空開高穿過停損 → 只能回補在更差的開盤價（max 同時涵蓋兩種情況）
                exit_raw, exit_kind = max(o, sl_level), "stop_loss"
            elif trail_level is not None and (o >= trail_level or hi >= trail_level):
                exit_raw, exit_kind = max(o, trail_level), "trailing_stop"
            elif tp_level is not None and (o <= tp_level or lo <= tp_level):
                # 跳空開低過停利 → 回補在較好的開盤價（如實反映）
                exit_raw, exit_kind = min(o, tp_level), "take_profit"

            if exit_raw is not None:
                eff = exit_raw * (1 + slippage_rate)         # 回補＝買入，滑到更高價（不利）
                qty = -position
                gross = qty * eff
                commission = gross * commission_rate
                profit = qty * (entry_price - eff) - commission
                total_cost += commission + qty * (eff - exit_raw)
                cash -= gross + commission
                risk_exit_counts[exit_kind] += 1
                trades.append(
                    {"date": date, "side": "cover", "price": round(eff, 2),
                     "qty": round(qty, 4),
                     "reason": f"風控出場：{exit_kind} 觸價 {exit_raw:.2f}",
                     "profit": round(profit, 2), "exit_reason": exit_kind}
                )
                position = 0.0
                entry_price = 0.0
                trough_price = 0.0
            else:
                # 檢查完才把當根 low 併入 trough（當根檢查只用「前面 bar 為止」的 trough，不偷看）
                trough_price = min(trough_price, lo)

        # --- 2. 記錄當根收盤後的總資產（連同真實日期，供報表用真年月）---
        equity_curve.append(cash + position * price)
        equity_dates.append(date)

        # --- 3. 依當根 close 的訊號，決定「下一根」要不要換手（隔日成交）---
        signal = signals[i]
        reason = reasons[i] if reasons is not None else ""
        if signal == Signal.BUY:
            if position == 0 and cash > 0:
                pending = ("buy", reason)
            elif allow_short and position < 0:
                pending = ("cover", reason)          # 持空遇 BUY → 回補平空
        elif signal == Signal.SELL:
            if position > 0:
                pending = ("sell", reason)           # 平多優先（不直接翻倉）
            elif allow_short and position == 0 and cash > 0:
                pending = ("short", reason)          # 空手遇 SELL → 開空
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

    # 勝率：看每次「平倉」（賣出平多 / 回補平空）是賺還賠。
    # 用「帶 profit 的筆」篩選（sell 與 cover 都帶 profit）——純多回測結果與舊版逐位元組相同。
    closes = [t for t in trades if "profit" in t]
    wins = [t for t in closes if t.get("profit", 0) > 0]
    win_rate = (len(wins) / len(closes) * 100) if closes else 0.0

    # --- 期望值（EV）相關指標 ---
    # 每筆「平倉」就是一次完整買賣（round trip），都帶 profit。
    n_round_trips = len(closes)
    profits = [t.get("profit", 0.0) for t in closes]
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

    # 平均 R multiple（M4）：只彙總「進場時有 stop（有定義 R）」的交易；
    # 沒用出場政策或政策無 stop 時整體回 None（誠實缺值，不填 0 假裝有）。
    r_multiples = [t["r_multiple"] for t in closes if "r_multiple" in t]
    avg_r_multiple = (sum(r_multiples) / len(r_multiples)) if r_multiples else None

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
        "avg_r_multiple": round(avg_r_multiple, 3) if avg_r_multiple is not None else None,
        "total_cost": round(total_cost, 2),  # 本次回測累計摩擦成本（手續費 + 滑價）
        # 風控出場觸發統計（沒開風控模擬時恆為 0）
        "num_stop_loss": risk_exit_counts["stop_loss"],
        "num_take_profit": risk_exit_counts["take_profit"],
        "num_trailing_stop": risk_exit_counts["trailing_stop"],
        "trades": trades,
        "equity_curve": [round(e, 2) for e in equity_curve],
        "equity_dates": equity_dates,  # 與 equity_curve 等長；報表用真實日期取代假 2000
    }


def _run_on_df(
    strategy, df: pd.DataFrame, initial_cash: float,
    commission_bps: float = 0.0, slippage_bps: float = 0.0,
    features: pd.DataFrame | None = None,
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
    trailing_stop_pct: float | None = None,
    allow_short: bool = False,
    exit_policy: ExitPolicy | None = None,
    entry_filters: list | None = None,
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
    # 進場趨勢過濾（M5，選用）：BUY 逐一過過濾器，被否決改記 HOLD + 理由。
    # 只動「訊號層」；None（預設）= 行為與現況完全相同。哪個 filter 上線由 M6 OOS 判定。
    if entry_filters:
        from backend.services.trend_filters import apply_entry_filters
        signals, reasons = apply_entry_filters(signals, reasons, sig_df, entry_filters)
    # 成交模擬只吃 price-only 的 df（features 不進成交層）
    return _simulate_from_signals(
        signals, df, initial_cash, reasons=reasons,
        commission_bps=commission_bps, slippage_bps=slippage_bps,
        stop_loss_pct=stop_loss_pct, take_profit_pct=take_profit_pct,
        trailing_stop_pct=trailing_stop_pct,
        allow_short=allow_short, exit_policy=exit_policy,
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
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
    trailing_stop_pct: float | None = None,
    timeframe: str = "1Day",
    allow_short: bool = False,
    exit_policy_key: str | None = None,
    exit_policy_params: dict | None = None,
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
    :param stop_loss_pct / take_profit_pct / trailing_stop_pct:
        風控出場模擬（同 Bot 風控欄位語意，0.10=10%；None=關）。
        帶 Bot 的實際風控參數重跑回測，能看到「策略訊號 + 風控出場」合體後的
        誠實 EV（含停損/停利/追蹤觸發統計 num_stop_loss 等）。
    :param timeframe: K 線時間框架（"1Min"~"1Day"，預設日 K —— 既有呼叫行為不變）。
        「訊號於次根 bar 開盤成交」的誠實語意在任何框架下都成立（日 K = 隔日開盤、
        5 分 K = 下一根 5 分 bar 開盤），_simulate_from_signals 零改動。
    :param allow_short: 做空開關（預設 False＝SELL 只平多，行為不變）。
        True 時 SELL 空手開空、BUY 持空回補——**僅供回測評估，實盤 Bot 只做多**。
    :param exit_policy_key / exit_policy_params: 可插拔出場政策（M4）。
        key 見 exit_policies.EXIT_POLICY_REGISTRY（fixed_pct/atr/swing/vwap）；
        僅日內政策（vwap）配日 K 會誠實拋錯。與 stop_loss_pct 等 % 參數互斥。
    """
    # 出場政策：先建實例並驗證框架相容（vwap 只准日內），錯就在這裡誠實炸，不進回測
    exit_policy = None
    if exit_policy_key:
        exit_policy = get_exit_policy(exit_policy_key, exit_policy_params)
        if exit_policy.intraday_only and timeframe == "1Day":
            raise ValueError(f"出場政策 {exit_policy_key} 僅支援日內框架（收到 timeframe=1Day）")
    # 成本預設讀全系統 config，呼叫端可顯式覆寫（含 0 = 關成本對照用）
    if commission_bps is None:
        commission_bps = settings.BACKTEST_COMMISSION_BPS
    if slippage_bps is None:
        slippage_bps = settings.BACKTEST_SLIPPAGE_BPS

    # 長區間自動選資料源：Alpaca 免費版抓不到 2000 年那麼久，超過門檻自動改 yfinance。
    # 日內框架則反過來一律 alpaca（yfinance 分鐘級歷史太短）。
    source = _resolve_source(source, days, timeframe)

    # 走本機快取（Phase 11 step-04）：缺區間才補抓、其餘命中快取，多年回測不每次重打 API。
    # get_bars_cached 包在 market_data.get_bars 外層、簽章相容、嚴格 ⊆ 請求區間（不洩漏未來）。
    df = bar_cache.get_bars_cached(symbol, days=days, source=source, timeframe=timeframe)
    if df.empty:
        raise ValueError(f"抓不到 {symbol} 的歷史資料")

    strategy = get_strategy(strategy_name, params or {})
    result = _run_on_df(
        strategy, df, initial_cash,
        commission_bps=commission_bps, slippage_bps=slippage_bps,
        features=features,
        stop_loss_pct=stop_loss_pct, take_profit_pct=take_profit_pct,
        trailing_stop_pct=trailing_stop_pct,
        allow_short=allow_short, exit_policy=exit_policy,
    )

    # 補上這次回測的基本資訊
    result["symbol"] = symbol
    result["strategy"] = strategy_name
    result["days"] = days
    result["timeframe"] = timeframe
    result["data_points"] = len(df)
    # 附上 quantstats 風險調整後指標（Sharpe/Sortino/Calmar/年化波動/CAGR）。
    # 只在「單筆回測」算（optimizer 海選走 _run_on_df，不經這裡，故不拖慢掃描）。
    # timeframe 透傳給年化基數（日 K=252、分鐘 K 依 bar 數放大，用錯全錯）。
    result["extended"] = extended_metrics(result.get("equity_curve"), timeframe=timeframe)
    return result
