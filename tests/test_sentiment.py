"""
AI 情緒入決策測試（Phase 6 step-07）
======================================
驗證第二層 LLM 的情緒分數「真正影響部署」，但守住「EV 為主、情緒為輔」：
- is_vetoed_by_sentiment：bearish / 分數過低否決；neutral / None 不否決。
- apply_sentiment：enabled 過濾否決者並以情緒做次要加權；disabled 原樣回傳（向後相容）；
  情緒不會把 OOS EV 更高的標的擠到更低 EV 標的後面（EV 仍為主）。
- plan_deployments：串接情緒閘後，bearish 標的不進部署。
- screen_watchlist：兩檔 EV 相同時，情緒較正者排前面。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_sentiment.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services import screener
from backend.services.screener import is_vetoed_by_sentiment, sentiment_score
from backend.services.automation import apply_sentiment, plan_deployments


def _sent(label, score):
    return {"label": label, "score": score, "reason": ""}


def _rec(symbol, ev, wr, sentiment):
    return {
        "symbol": symbol, "strategy_key": "rsi", "params": {"period": 14},
        "metrics": {"oos_expected_value": ev, "oos_win_rate_pct": wr},
        "sentiment": sentiment,
    }


# ---------- is_vetoed_by_sentiment ----------
def test_veto_rules():
    assert is_vetoed_by_sentiment(_sent("bearish", 50), min_score=-20) is True   # bearish 直接否決
    assert is_vetoed_by_sentiment(_sent("neutral", -50), min_score=-20) is True  # 分數過低否決
    assert is_vetoed_by_sentiment(_sent("bullish", 80), min_score=-20) is False  # 偏多不否決
    assert is_vetoed_by_sentiment(_sent("neutral", 0), min_score=-20) is False   # 中性不否決
    assert is_vetoed_by_sentiment(None, min_score=-20) is False                  # 沒跑情緒 → 不否決
    assert sentiment_score(None) == 0 and sentiment_score(_sent("bullish", 30)) == 30


# ---------- apply_sentiment ----------
def test_apply_sentiment_disabled_passthrough():
    """關閉情緒閘 → 原樣回傳（向後相容，純 EV 行為）。"""
    recs = [_rec("AAPL", 200, 60, _sent("bearish", -90))]
    out = apply_sentiment(recs, min_score=-20, enabled=False)
    assert out == recs, out


def test_apply_sentiment_vetoes_and_keeps_ev_primary():
    """bearish / 過低被剔除；保留者 EV 為主排序（情緒不翻盤）。"""
    recs = [
        _rec("AAPL", 200, 60, _sent("neutral", -15)),  # 高 EV、情緒略負（未過門檻，保留）
        _rec("MSFT", 100, 60, _sent("bullish", 90)),   # 低 EV、情緒很正
        _rec("TSLA", 300, 60, _sent("bearish", -95)),  # bearish → 否決
        _rec("NVDA", 150, 60, _sent("neutral", -50)),  # 分數過低 → 否決
    ]
    out = apply_sentiment(recs, min_score=-20, enabled=True)
    symbols = [r["symbol"] for r in out]
    assert symbols == ["AAPL", "MSFT"], symbols  # 兩檔被否決；AAPL(EV200) 仍排在 MSFT(EV100) 前


def test_apply_sentiment_secondary_weight_on_tie():
    """EV 相同時，情緒較正者排前面（次要加權生效）。"""
    recs = [
        _rec("AAPL", 100, 60, _sent("neutral", 10)),
        _rec("MSFT", 100, 60, _sent("bullish", 90)),
    ]
    out = apply_sentiment(recs, min_score=-20, enabled=True)
    assert [r["symbol"] for r in out] == ["MSFT", "AAPL"], out


# ---------- plan_deployments 串接 ----------
def test_plan_deployments_with_sentiment_gating():
    """串接情緒閘：bearish 標的不進部署，EV 較高的中性標的入選。"""
    recs = [
        _rec("TSLA", 300, 60, _sent("bearish", -95)),  # EV 最高但 bearish → 否決
        _rec("AAPL", 200, 60, _sent("neutral", 0)),    # 入選
    ]
    planned = plan_deployments(
        recs, ev_threshold=150, winrate_threshold=55,
        max_bots=5, existing_symbols=set(), active_count=0,
        sentiment_min_score=-20, sentiment_enabled=True,
    )
    assert [r["symbol"] for r in planned] == ["AAPL"], planned


def test_plan_deployments_sentiment_disabled_is_backward_compatible():
    """情緒閘關閉 → 退回純 EV（bearish 也能入選，向後相容）。"""
    recs = [_rec("TSLA", 300, 60, _sent("bearish", -95))]
    planned = plan_deployments(
        recs, ev_threshold=150, winrate_threshold=55,
        max_bots=5, existing_symbols=set(), active_count=0,
        sentiment_min_score=-20, sentiment_enabled=False,
    )
    assert [r["symbol"] for r in planned] == ["TSLA"], planned


# ---------- screen_watchlist 排序 ----------
def test_screen_watchlist_sorts_by_ev_then_sentiment(monkeypatch):
    """兩檔 OOS EV 相同 → 情緒分數較高者排前面。"""
    monkeypatch.setattr(screener, "_layer1_volume",
                        lambda symbols, days, source: [
                            {"symbol": "AAPL", "volume_ratio": 3.0},
                            {"symbol": "TSLA", "volume_ratio": 2.8},
                        ])
    monkeypatch.setattr(screener, "_layer2_sentiment",
                        lambda picks: [
                            {**picks[0], "sentiment": _sent("neutral", 10)},   # AAPL 情緒 10
                            {**picks[1], "sentiment": _sent("bullish", 90)},   # TSLA 情緒 90
                        ])
    monkeypatch.setattr(screener, "run_auto_backtest",
                        lambda symbol, days, initial_cash, source: {"best": {
                            "strategy_key": "rsi", "params": {"period": 14},
                            "metrics": {"oos_expected_value": 50.0, "oos_win_rate_pct": 60},
                        }})
    out = screener.screen_watchlist()
    syms = [r["symbol"] for r in out["recommendations"]]
    assert syms == ["TSLA", "AAPL"], syms  # EV 相同 → 情緒高的 TSLA 在前
    print("✅ 情緒入決策測試全通過")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
