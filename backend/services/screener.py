"""
AI 策略探勘 — 漏斗式篩選（改版 Phase 2）
=========================================
盤前海選一籃股票，挑出「值得部署」的策略配置。核心是**漏斗式（funnel）**設計，
為的是不要一次對幾百檔股票跑昂貴的 LLM，把本機算力榨乾：

    第一層（便宜・純 pandas）：量能粗篩
        最新一根成交量 > 近 20 日均量 × 倍數 → 入選「爆量」名單，取量比最高的前 N 檔。

    第二層（昂貴・本機 Ollama）：情緒打分
        只對第一層survivors 的新聞標題，請本機 LLM 給多空情緒分數（best-effort，連不上就跳過）。

    第三層（中等・回測）：EV 海選
        對每檔 survivor 重用 optimizer.run_auto_backtest，挑該檔的最佳策略 + 期望值 EV。

最後組成推薦清單（只留 EV > 門檻的），交給前端渲染成卡片、供「一鍵 Deploy」。

職責分離：本檔只「算」推薦，不存 DB、不建 Bot（建 Bot 由前端按 Deploy 走既有 /bots 流程）。
"""

import json

from backend.config import settings
from backend.services import market_data, fundamentals, llm
from backend.services.optimizer import run_auto_backtest


# ============================================================
# 純函式（不碰網路/LLM，好寫單元測試）
# ============================================================
def volume_ratio(df) -> float | None:
    """
    算「最新一根成交量 ÷ 近 20 日均量」。

    :return: 量比（float）；資料不足或均量為 0 時回 None。
    """
    if df is None or df.empty or "volume" not in df:
        return None
    vols = df["volume"].dropna()
    if len(vols) < 2:
        return None
    # 近 20 日（不含最後一根）的均量；不足 20 根就用現有的
    window = vols.iloc[-21:-1] if len(vols) > 20 else vols.iloc[:-1]
    avg = window.mean()
    if not avg or avg <= 0:
        return None
    return float(vols.iloc[-1] / avg)


def passes_volume_filter(df, ratio_threshold: float) -> bool:
    """最新一根是否「爆量」（量比 >= 門檻）。"""
    ratio = volume_ratio(df)
    return ratio is not None and ratio >= ratio_threshold


def parse_sentiment(raw: str) -> dict:
    """
    從 LLM 回覆裡穩健抓出情緒 JSON：{label, score, reason}。
    抓不到就回中性預設，確保上層永遠拿到一致格式。

    label: "bullish" | "bearish" | "neutral"；score: -100~100。
    """
    default = {"label": "neutral", "score": 0, "reason": ""}
    if not raw:
        return default
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        return default
    try:
        data = json.loads(raw[start : end + 1])
    except Exception:
        return default
    if not isinstance(data, dict):
        return default
    label = str(data.get("label", "neutral")).lower()
    if label not in ("bullish", "bearish", "neutral"):
        label = "neutral"
    try:
        score = int(data.get("score", 0))
    except Exception:
        score = 0
    score = max(-100, min(100, score))
    return {"label": label, "score": score, "reason": str(data.get("reason", ""))[:200]}


def parse_watchlist(raw: str) -> list[str]:
    """把逗號分隔的候選股字串清成大寫去重清單。"""
    seen, out = set(), []
    for sym in (raw or "").split(","):
        s = sym.strip().upper()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def sentiment_score(sentiment) -> int:
    """從一筆情緒（parse_sentiment 的格式 dict 或 None）安全取出分數。

    None（沒跑情緒 / 被外送閘擋下）或格式不符 → 視為中性 0。
    這個值只當「次要排序加權」用，主排序鍵永遠是 OOS EV（EV 為主、情緒為輔）。
    """
    if not isinstance(sentiment, dict):
        return 0
    s = sentiment.get("score")
    return int(s) if isinstance(s, (int, float)) else 0


def is_vetoed_by_sentiment(sentiment, *, min_score: float) -> bool:
    """判斷一筆情緒是否構成「情緒否決」（Phase 6 step-07）。

    規則：label == "bearish" 或 score < min_score → 否決。
    sentiment 為 None（沒跑情緒）→ 視為中性、**不否決**（best-effort，離線不阻斷）。
    """
    if not isinstance(sentiment, dict):
        return False
    if sentiment.get("label") == "bearish":
        return True
    score = sentiment.get("score")
    return isinstance(score, (int, float)) and score < min_score


# ============================================================
# 漏斗各層（會碰網路/LLM，靠 monkeypatch 測）
# ============================================================
def _layer1_volume(symbols: list[str], days: int, source: str) -> list[dict]:
    """第一層：量能粗篩。回傳入選清單（含量比），依量比由高到低排序、取前 N。"""
    picks = []
    for sym in symbols:
        try:
            df = market_data.get_bars(sym, days=days, source=source)
        except Exception:
            continue  # 單檔抓失敗不影響整體
        ratio = volume_ratio(df)
        if ratio is not None and ratio >= settings.SCREENER_VOLUME_RATIO:
            picks.append({"symbol": sym, "volume_ratio": round(ratio, 2)})
    picks.sort(key=lambda x: x["volume_ratio"], reverse=True)
    return picks[: settings.SCREENER_TOP_N]


def _score_one_sentiment(client, symbol: str) -> dict:
    """對單一股票的新聞標題請 LLM 打多空情緒分。連不上/出錯 → 中性。"""
    try:
        news = fundamentals.get_news(symbol).get("news", [])
    except Exception:
        news = []
    headlines = [n.get("title", "") for n in news[:8] if n.get("title")]
    if not headlines:
        return {"label": "neutral", "score": 0, "reason": "（無新聞）"}

    sys = "你是金融新聞情緒分析器。只回 JSON，不要多餘文字。"
    user = (
        f"以下是 {symbol} 的近期新聞標題：\n"
        + "\n".join(f"- {h}" for h in headlines)
        + '\n\n請判斷整體對股價偏多還偏空，只回 JSON：'
        '{"label":"bullish|bearish|neutral","score":-100到100的整數,"reason":"一句話"}'
    )
    try:
        raw = llm.complete(
            client,
            [{"role": "system", "content": sys}, {"role": "user", "content": user}],
            max_tokens=200,
            temperature=0.3,
        )
        return parse_sentiment(raw)
    except Exception:
        return {"label": "neutral", "score": 0, "reason": "（情緒分析失敗）"}


def _layer2_sentiment(picks: list[dict]) -> list[dict]:
    """第二層：對 survivors 做情緒打分。LLM 沒設定/被外送閘擋下 → 整層跳過（score=None）。"""
    client = llm.get_client()
    if client is None or llm.cloud_blocked():
        for p in picks:
            p["sentiment"] = None  # None 代表「沒跑情緒」，前端顯示「未分析」
        return picks
    for p in picks:
        p["sentiment"] = _score_one_sentiment(client, p["symbol"])
    return picks


def screen_watchlist(
    days: int = 365,
    initial_cash: float = 10000.0,
    source: str = settings.DATA_SOURCE,
    min_ev: float = 0.0,
) -> dict:
    """
    跑完整漏斗，回傳推薦清單（只留 EV > min_ev 的，依 EV 由高到低）。

    :return: dict，含 recommendations、各層數量統計（給前端/log 看漏斗收斂情況）。
    """
    watchlist = parse_watchlist(settings.SCREENER_WATCHLIST)

    # 第一層：量能粗篩（短週期抓量即可，省時）
    picks = _layer1_volume(watchlist, days=min(days, 60), source=source)

    # 第二層：情緒打分（best-effort）
    picks = _layer2_sentiment(picks)

    # 第三層：對每檔 survivor 跑 EV 海選，挑最佳策略
    recommendations = []
    for p in picks:
        try:
            scan = run_auto_backtest(
                p["symbol"], days=days, initial_cash=initial_cash, source=source
            )
        except Exception:
            continue
        best = scan.get("best")
        if not best:
            continue
        # ★海選門檻看「樣本外 EV」（防過擬合，Phase 6 step-04），不看整段歷史的樣本內 EV
        ev = (best.get("metrics") or {}).get("oos_expected_value")
        if not isinstance(ev, (int, float)) or ev <= min_ev:
            continue
        recommendations.append({
            "symbol": p["symbol"],
            "volume_ratio": p["volume_ratio"],
            "sentiment": p["sentiment"],
            "strategy_key": best["strategy_key"],
            "params": best["params"],
            "metrics": best["metrics"],
            "suggested_cash": initial_cash,
        })

    # 排序鍵 =（樣本外 EV, 情緒分數）：EV 為主（與挑冠軍同一把尺），情緒當次要加權
    # （Phase 6 step-07）。情緒不會把 OOS EV 更高的標的擠到更低 EV 標的後面（EV 永遠先比）。
    recommendations.sort(
        key=lambda r: (
            r["metrics"].get("oos_expected_value", float("-inf")),
            sentiment_score(r.get("sentiment")),
        ),
        reverse=True,
    )

    return {
        "watchlist_size": len(watchlist),
        "volume_passed": len(picks),
        "recommended": len(recommendations),
        "recommendations": recommendations,
    }
