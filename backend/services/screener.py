"""
AI 策略海選（漏斗式篩選）── Phase 2
=====================================
盤前/盤中對「一批股票」自動海選出高期望值（EV>0）的策略配置，給前端
「AI 策略探勘中心」渲染成卡片，使用者一鍵部署成 Bot。

為什麼用「漏斗式篩選（Funnel Filtering）」：
  直接拿幾十檔股票 × 多種策略全部跑回測，會把本機算力吃滿、又拖慢盤前。
  所以分層遞減算力消耗：

  第一層（低算力）：用 pandas 算「量能異常」── 最新成交量 / 20 日均量 的「量比」。
                    量比 ≥ multiplier（預設 2.5）才過關。爆量常代表有題材在動，
                    值得進一步分析；安靜的股票直接淘汰，不浪費後面的回測算力。
  第二層（高算力）：只對「過關的少數股票」逐一跑多種策略回測，每檔取 EV 最高那組，
                    留下 EV ≥ min_ev 的當推薦。第一層抓的 K 線會「快取重用」，
                    第二層不再重抓資料源（省 yfinance 呼叫）。
  第三層（最高算力，預設關）：把第二層survivors 的新聞/財報摘要交本機 Ollama 情緒打分。
                    需要 Ollama 在跑、且會明顯變慢，故預設關閉、先留鉤子，未來再接。

設計重點：
- 純 Python 計算，不需要 Alpaca 金鑰（預設 source="yfinance"，免費、離線可跑）。
- 任何單檔股票抓不到資料 / 回測爆錯，都「跳過該檔」而非讓整個海選失敗。
"""

import pandas as pd

from backend.services import market_data
from backend.services.backtest_engine import backtest_on_bars

# 預設海選池：挑流動性高、新手熟悉的美股大型股。
# 想換池子可在 API 傳 ?symbols=AAPL,MSFT,... 覆寫。
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
    "AMD", "NFLX", "AVGO", "COST", "PLTR", "SMCI", "INTC", "QCOM",
]

# 第二層要試的候選策略（用各策略的預設參數）。
# 刻意只挑幾個「方向明確、互補」的策略，控制第二層算力。
CANDIDATE_STRATEGIES = [
    "ma_crossover",  # 順勢：均線交叉
    "rsi",           # 擺盪：超買超賣
    "macd",          # 動能：MACD
    "donchian",      # 突破：唐奇安通道
    "momentum",      # 動量
]


def _volume_ratio(df: pd.DataFrame, ma_window: int = 20) -> float | None:
    """
    算「量比」＝最新成交量 / 近 ma_window 日均量。

    量比 > 1 代表今天比平常熱絡；越大代表爆量越明顯。
    資料不足（不到 ma_window 根）或沒有 volume 欄就回 None（視為無法判斷、淘汰）。
    """
    if "volume" not in df.columns or len(df) < ma_window:
        return None
    vol = df["volume"].astype(float)
    ma = vol.iloc[-ma_window:].mean()
    if ma <= 0:
        return None
    latest = float(vol.iloc[-1])
    return latest / ma


def _best_strategy_for(df: pd.DataFrame, initial_cash: float) -> dict | None:
    """
    對單一檔股票（已抓好的 df），試所有候選策略，回「EV 最高」那組的結果。

    回傳含 strategy_key / params / 關鍵指標的 dict；全部策略都跑不出來時回 None。
    """
    best = None
    for key in CANDIDATE_STRATEGIES:
        try:
            # 用預設參數（params={}），重用已抓的 df，不重抓資料源
            result = backtest_on_bars(key, df, params={}, initial_cash=initial_cash)
        except Exception:
            # 單一策略爆錯（例如資料太短算不出指標）就跳過，不影響其他策略
            continue
        ev = result.get("expected_value", float("-inf"))
        if best is None or ev > best["_ev"]:
            best = {"_ev": ev, "strategy_key": key, "result": result}
    return best


def _metrics_summary(result: dict) -> dict:
    """從完整回測結果挑出卡片要顯示的關鍵指標（不帶肥大的 trades/equity_curve）。"""
    return {
        "expected_value": result.get("expected_value"),
        "expectancy_pct": result.get("expectancy_pct"),
        "win_rate_pct": result.get("win_rate_pct"),
        "total_return_pct": result.get("total_return_pct"),
        "buy_and_hold_pct": result.get("buy_and_hold_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "profit_factor": result.get("profit_factor"),
        "num_round_trips": result.get("num_round_trips"),
    }


def screen(
    symbols: list[str] | None = None,
    days: int = 180,
    volume_multiplier: float = 2.5,
    min_ev: float = 0.0,
    top: int = 10,
    initial_cash: float = 10000.0,
    source: str = "yfinance",
) -> dict:
    """
    跑一輪漏斗式海選。

    :param symbols: 海選池；None 時用 DEFAULT_UNIVERSE
    :param days: 每檔往前抓幾天 K 線
    :param volume_multiplier: 第一層量比門檻（量比 ≥ 此值才過關）
    :param min_ev: 第二層期望值門檻（EV ≥ 此值才進推薦）
    :param top: 最多回傳幾筆推薦（依 EV 由高到低）
    :param initial_cash: 回測初始資金
    :param source: 資料源，"yfinance"（預設、免費）或 "alpaca"
    :return: dict，含海選池大小、各層結果、推薦清單（依 EV 由高到低）
    """
    universe = [s.upper() for s in (symbols or DEFAULT_UNIVERSE)]

    # ---- 第一層：量能篩選（順便把抓到的 df 快取，第二層重用）----
    layer1_passed = []   # 過關的 [{symbol, volume_ratio, df}]
    skipped = []         # 抓不到資料 / 量比算不出來的標的（除錯用）
    for symbol in universe:
        try:
            df = market_data.get_bars(symbol, days=days, source=source)
        except Exception:
            skipped.append(symbol)
            continue
        if df is None or df.empty:
            skipped.append(symbol)
            continue
        ratio = _volume_ratio(df)
        if ratio is None:
            skipped.append(symbol)
            continue
        if ratio >= volume_multiplier:
            layer1_passed.append({"symbol": symbol, "volume_ratio": ratio, "df": df})

    # ---- 第二層：對過關標的跑多策略回測，取 EV 最高、留 EV ≥ min_ev ----
    recommendations = []
    for item in layer1_passed:
        best = _best_strategy_for(item["df"], initial_cash)
        if best is None:
            continue
        result = best["result"]
        ev = result.get("expected_value")
        if ev is None or ev < min_ev:
            continue
        recommendations.append({
            "symbol": item["symbol"],
            "volume_ratio": round(item["volume_ratio"], 2),
            "strategy_key": best["strategy_key"],
            "params": {},  # 目前用各策略預設參數；未來可由 AI 微調
            "days": days,
            "source": source,
            "metrics": _metrics_summary(result),
        })

    # 依期望值 EV 由高到低排，截前 top 筆
    recommendations.sort(
        key=lambda r: r["metrics"].get("expected_value") or float("-inf"),
        reverse=True,
    )
    recommendations = recommendations[:top]

    return {
        "universe_size": len(universe),
        "layer1_passed": [x["symbol"] for x in layer1_passed],
        "skipped": skipped,
        "params": {
            "days": days,
            "volume_multiplier": volume_multiplier,
            "min_ev": min_ev,
            "source": source,
        },
        "recommendations": recommendations,
    }
