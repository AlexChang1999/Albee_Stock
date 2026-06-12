"""
延伸績效分析（quantstats 封裝）── 導入 quantstats
====================================================
回測引擎（backtest_engine）已算出總報酬、最大回撤、EV 等「自家指標」。
這個模組再補上量化界常看的「風險調整後報酬」指標，以及一鍵 HTML 績效報表（tear sheet）：

- Sharpe   ：每承受 1 單位波動，換到多少超額報酬（越高越好）
- Sortino  ：類似 Sharpe，但只罰「下跌」波動（上漲不算風險）
- Calmar   ：年化報酬 / 最大回撤（看「賺得多但回撤小」）
- 年化波動 ：報酬的標準差年化（越低越穩）
- CAGR     ：年化複合報酬率
- VaR 95%  ：歷史模擬法——最差 5% 交易日的「門檻」單日虧損（正值 = 虧損 %）
- CVaR 95% ：跌破 VaR 防線後，尾部那些日子的「平均」虧損（永遠 >= VaR）

設計重點：
- **純函式、可離線測**：輸入是回測引擎產的 equity_curve（每日淨值 list），不連線。
- **防爆**：quantstats 在某些 pandas 版本/極短序列可能丟例外；全部用 _safe 包起來，
  失敗回 None，絕不讓「算個附加指標」拖垮整個回測 API。
- **不進 optimizer 的數十組迴圈**：只給「單筆回測」與「事後產報表」用，避免拖慢海選。
"""

import pandas as pd

try:
    import quantstats as qs
    _QS_OK = True
except Exception:  # pragma: no cover - 套件未裝時優雅降級
    qs = None
    _QS_OK = False

# 一年的交易日數（年化用的標準慣例）
TRADING_DAYS = 252


def _safe(fn):
    """跑一個會回 float 的計算；任何例外或 nan/inf 都回 None（不讓附加指標擋住主流程）。"""
    try:
        val = float(fn())
    except Exception:
        return None
    if val != val or val in (float("inf"), float("-inf")):  # NaN / Inf
        return None
    return val


def returns_from_equity(equity_curve) -> pd.Series:
    """
    把「每日淨值序列」轉成「每日報酬率序列」，並配上合成的營業日時間索引。

    為什麼要時間索引？quantstats 算年化（Sharpe/CAGR…）需要知道資料頻率，
    沒有 DatetimeIndex 它無法判斷。用固定起點的 bdate_range，結果可重現、可測試。
    """
    if not equity_curve or len(equity_curve) < 2:
        return pd.Series(dtype=float)
    s = pd.Series([float(x) for x in equity_curve], dtype=float)
    rets = s.pct_change().dropna()
    # 固定起點的營業日索引（純為頻率資訊，實際日期不影響比率計算）
    rets.index = pd.bdate_range(start="2000-01-03", periods=len(rets))
    return rets


def var_cvar(returns: pd.Series, confidence: float = 0.95) -> tuple:
    """
    歷史模擬法算 VaR 與 CVaR（Expected Shortfall）。

    - VaR  ：日報酬分布的左尾 (1-confidence) 分位數取負號——「最差 5% 的日子，
             至少虧這麼多」的門檻。
    - CVaR ：跌破 VaR 門檻後，尾部那些日子的平均虧損——「一旦破線，平均虧多慘」。

    不依賴 quantstats（純 pandas 分位數），quantstats 沒裝也算得出來。
    單位：每日虧損 %（正值）；全正報酬的曲線可能算出負值（= 最差日仍在賺），照實回報。

    :param returns: 每日報酬率序列（returns_from_equity 的輸出）
    :param confidence: 信心水準，預設 0.95
    :return: (var_pct, cvar_pct)；樣本 < 20 筆時尾部沒統計意義，回 (None, None)
    """
    if returns is None or len(returns) < 20:
        return (None, None)
    q = returns.quantile(1 - confidence)
    var = _safe(lambda: -q * 100)
    tail = returns[returns <= q]
    # 尾部切片理論上至少含分位數那筆；防呆：空了就退回 VaR
    cvar = _safe(lambda: -tail.mean() * 100) if len(tail) else var
    rnd = lambda v: round(v, 2) if v is not None else None
    return (rnd(var), rnd(cvar))


def extended_metrics(equity_curve) -> dict:
    """
    從 equity_curve 算一組風險調整後指標。任何單項失敗回 None，不影響其他項。
    回傳 key 都是 JSON-friendly 的純量，可直接塞進回測結果一起回前端。
    """
    rets = returns_from_equity(equity_curve)
    # VaR/CVaR 自算、不靠 quantstats，所以放在 _QS_OK 閘之前（沒裝 qs 也要有值）
    var95, cvar95 = var_cvar(rets)
    if rets.empty or not _QS_OK:
        return {
            "sharpe": None, "sortino": None, "calmar": None,
            "volatility_ann_pct": None, "cagr_pct": None,
            "var_95_pct": var95, "cvar_95_pct": cvar95,
        }

    def _round(v, n=2):
        return round(v, n) if v is not None else None

    return {
        "sharpe": _round(_safe(lambda: qs.stats.sharpe(rets))),
        "sortino": _round(_safe(lambda: qs.stats.sortino(rets))),
        "calmar": _round(_safe(lambda: qs.stats.calmar(rets))),
        "volatility_ann_pct": _round(_safe(lambda: qs.stats.volatility(rets) * 100)),
        "cagr_pct": _round(_safe(lambda: qs.stats.cagr(rets) * 100)),
        "var_95_pct": var95,
        "cvar_95_pct": cvar95,
    }


def tearsheet_html(equity_curve, out_path: str, title: str = "Albee Stock 績效報表") -> str:
    """
    產一份 quantstats 的 HTML tear sheet（含資金曲線、回撤、月報酬表等）寫到 out_path。
    benchmark=None：不下載 SPY 對照（避免連網、保持離線可用）。

    :raises RuntimeError: quantstats 未裝或資料不足無法產報表時。
    """
    if not _QS_OK:
        raise RuntimeError("quantstats 未安裝，無法產生績效報表")
    rets = returns_from_equity(equity_curve)
    if rets.empty:
        raise RuntimeError("資料不足（至少需要 2 筆淨值）無法產生報表")
    qs.reports.html(rets, benchmark=None, output=out_path, title=title)
    return out_path
