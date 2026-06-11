"""
延伸績效分析測試（quantstats 封裝）
====================================
驗 analytics.py：從 equity_curve 算 Sharpe/Sortino/Calmar 等、空序列不崩、HTML 報表能產。
純函式、不連線。

執行（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_analytics.py -q
"""

import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from backend.services.analytics import (
    returns_from_equity,
    extended_metrics,
    tearsheet_html,
    var_cvar,
)


# 一條穩定上漲、帶小波動的資金曲線（250 個交易日），結果可重現
def _sample_equity():
    eq = [10000.0]
    # 每天約 +0.1%，每 5 天小回檔，製造波動好讓 Sharpe 等指標有意義
    for i in range(1, 250):
        step = 1.001 if i % 5 else 0.995
        eq.append(eq[-1] * step)
    return eq


def test_returns_from_equity_shape():
    eq = _sample_equity()
    rets = returns_from_equity(eq)
    assert len(rets) == len(eq) - 1  # 報酬比淨值少一筆（首日無前一日）
    assert isinstance(rets.index, pd.DatetimeIndex)  # 有時間索引供年化


def test_extended_metrics_has_numbers():
    m = extended_metrics(_sample_equity())
    # 五個 key 都在，且這條上漲曲線該算得出數字（非 None）
    for key in ("sharpe", "sortino", "calmar", "volatility_ann_pct", "cagr_pct"):
        assert key in m
    assert m["sharpe"] is not None
    assert m["cagr_pct"] is not None
    assert m["volatility_ann_pct"] is not None and m["volatility_ann_pct"] >= 0


def test_extended_metrics_empty_and_short_safe():
    # 空 / 只有一筆 → 全 None，不丟例外
    for bad in ([], [100.0]):
        m = extended_metrics(bad)
        assert all(v is None for v in m.values())


def test_var_cvar_known_quantile():
    # 100 筆報酬：90 筆 +1%、10 筆尾部（-2%~-6% 各兩筆），分位數可手算：
    # 排序後第 5 百分位落在兩個 -4% 之間 → VaR = 4.0；
    # 尾部 (<= -4%) 為 -6,-6,-5,-5,-4,-4，平均 -5% → CVaR = 5.0
    tail = [-0.06, -0.06, -0.05, -0.05, -0.04, -0.04, -0.03, -0.03, -0.02, -0.02]
    rets = pd.Series([0.01] * 90 + tail)
    var, cvar = var_cvar(rets, confidence=0.95)
    assert var == 4.0
    assert cvar == 5.0
    assert cvar >= var  # 破線後平均一定不比門檻輕


def test_var_cvar_short_series_returns_none():
    # 樣本 < 20 筆 → 尾部沒統計意義，回 (None, None)
    assert var_cvar(pd.Series([0.01] * 19)) == (None, None)
    assert var_cvar(pd.Series(dtype=float)) == (None, None)
    assert var_cvar(None) == (None, None)


def test_var_cvar_all_positive_returns_negative_var():
    # 全正報酬：最差日仍在賺 → VaR 為負（誠實回報，不掩飾）
    rets = pd.Series([0.01, 0.02, 0.005] * 10)
    var, cvar = var_cvar(rets)
    assert var is not None and var < 0


def test_extended_metrics_includes_var_cvar_keys():
    m = extended_metrics(_sample_equity())
    assert "var_95_pct" in m and "cvar_95_pct" in m
    # 250 日的波動曲線算得出尾部數字
    assert m["var_95_pct"] is not None
    assert m["cvar_95_pct"] is not None
    assert m["cvar_95_pct"] >= m["var_95_pct"]


def test_tearsheet_html_writes_file(tmp_path):
    out = str(tmp_path / "report.html")
    path = tearsheet_html(_sample_equity(), out, title="測試報表")
    assert os.path.exists(path)
    content = Path(path).read_text(encoding="utf-8")
    assert "<html" in content.lower()  # 確實產出 HTML
