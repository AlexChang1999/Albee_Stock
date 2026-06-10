"""
macro 層 OOS 加分驗證測試（Phase 11 step-05）
================================================
全合成資料、**不碰外部 API**（不連 FRED / yfinance / Alpaca）。驗三件事：

1. OOS 殺手：構造「in-sample 漂亮、OOS 崩」的假層 → is_layer_worth_it 正確判「不值得上線」。
   （這套框架的本職是「殺掉沒用的層」，不是美化績效——希望它把無效 macro 層判死。）
2. 環境覆蓋策略邏輯：risk-off（VIX 高）時把 BUY 縮回 HOLD；NaN 特徵 → 不煞車（= base 行為）。
3. 端到端：validate_macro_layer 在合成 df + db=None 上跑得出 verdict 結構（優雅降級不崩）。

執行（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_macro_layer.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from backend.services.layer_validation import (
    MacroOverlayStrategy,
    _build_features,
    _macro_risk_off,
    validate_macro_layer,
)
from backend.services.validation import is_layer_worth_it
from backend.strategies.base import BaseStrategy, Signal


class AlwaysBuy(BaseStrategy):
    """測試用：永遠出 BUY（好驗環境覆蓋有沒有把它煞掉）。"""

    def __init__(self):
        super().__init__({})

    def generate_signal(self, df):
        return Signal.BUY, "永遠買"


# ============================================================
# 1) OOS 殺手：假層 in-sample 漂亮、OOS 崩 → 判不值得
# ============================================================
def test_oos_killer_rejects_overfit_layer():
    """candidate 樣本外平均 < baseline → is_layer_worth_it 判 worth=False（該砍）。"""
    # baseline 每 fold OOS EV 都穩定為正；candidate 樣本外崩（負），雖然「故事」漂亮
    baseline_oos = [5.0, 6.0, 4.0, 5.5]
    candidate_oos = [-2.0, -3.0, 1.0, -1.0]  # OOS 崩
    v = is_layer_worth_it(baseline_oos, candidate_oos)
    assert v["worth"] is False, v
    assert v["improvement"] < 0, v
    print(f"✅ OOS 殺手測試通過：假 macro 層被判不值得（Δ={v['improvement']}）")


# ============================================================
# 2) 環境覆蓋策略邏輯
# ============================================================
def test_overlay_brakes_buy_when_risk_off():
    """VIX 高（>30）→ risk-off → BUY 被縮回 HOLD（只煞車、不猜方向）。"""
    df = pd.DataFrame({
        "close": [10, 11],
        "vix_level": [12.0, 35.0],  # 最後一根 VIX=35 → 觸發煞車
    })
    sig, reason = MacroOverlayStrategy(AlwaysBuy()).generate_signal(df)
    assert sig == Signal.HOLD, (sig, reason)
    print("✅ 環境覆蓋煞車測試通過（risk-off 時 BUY→HOLD）")


def test_overlay_passes_when_features_nan():
    """特徵全 NaN（沒 FRED 資料）→ 不煞車 → 放行 base 的 BUY（優雅降級 = baseline 行為）。"""
    df = pd.DataFrame({
        "close": [10, 11],
        "vix_level": [np.nan, np.nan],
        "yield_curve": [np.nan, np.nan],
        "unemployment_trend": [np.nan, np.nan],
        "pressure_ratio": [np.nan, np.nan],
    })
    sig, _ = MacroOverlayStrategy(AlwaysBuy()).generate_signal(df)
    assert sig == Signal.BUY, sig
    print("✅ NaN 特徵不煞車測試通過（candidate 退化成 baseline）")


def test_macro_risk_off_each_threshold():
    """逐一驗四個 a-priori 門檻：各自單獨觸發都算 risk-off；全在安全區則否。"""
    safe = pd.Series({"vix_level": 15.0, "yield_curve": 1.0,
                      "unemployment_trend": -0.1, "pressure_ratio": 0.7})
    assert _macro_risk_off(safe) is False, "安全區不該煞車"
    assert _macro_risk_off(pd.Series({"vix_level": 31.0})) is True       # 恐慌
    assert _macro_risk_off(pd.Series({"yield_curve": -0.2})) is True      # 倒掛
    assert _macro_risk_off(pd.Series({"unemployment_trend": 0.3})) is True  # 失業上升
    assert _macro_risk_off(pd.Series({"pressure_ratio": 0.4})) is True     # 賣壓>買壓
    print("✅ 四門檻測試通過（各自單獨觸發 risk-off）")


# ============================================================
# 3) 端到端：合成 df + db=None 跑得出 verdict 結構（不崩）
# ============================================================
def _synthetic_bars(n: int = 400) -> pd.DataFrame:
    """合成 n 根日 K（有 open/close/volume/timestamp），夠切出多個 walk-forward fold。"""
    rng = np.random.default_rng(42)
    rets = rng.normal(0.0005, 0.02, n)
    close = 100.0 * np.cumprod(1.0 + rets)
    opens = close * (1.0 + rng.normal(0, 0.003, n))
    vol = rng.integers(1_000_000, 5_000_000, n).astype(float)
    ts = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.DataFrame({"timestamp": ts, "open": opens, "close": close,
                         "high": np.maximum(opens, close), "low": np.minimum(opens, close),
                         "volume": vol})


def test_validate_macro_layer_end_to_end_no_db():
    """db=None（沒 FRED）→ macro 欄全 NaN → candidate 退化成 baseline；
    驗回傳結構齊全、不崩，且無加分（improvement≈0、worth 非 True）。"""
    df = _synthetic_bars(400)
    res = validate_macro_layer(df, db=None)
    assert res["layer"] == "step-11 macro-overlay", res
    assert "baseline_oos" in res and "candidate_oos" in res, res
    assert len(res["baseline_oos"]) == len(res["candidate_oos"]), res
    v = res["verdict"]
    assert set(v) >= {"worth", "improvement", "folds"}, v
    # 沒 macro 資料 → 只剩 orderflow（pressure_ratio）可能偶觸發煞車，但整體不應「加分上線」
    assert v["worth"] is not True, v
    print(f"✅ 端到端測試通過：macro 層 verdict={v['worth']}（Δ={v['improvement']}，folds={v['folds']}）")


def test_build_features_columns_and_alignment():
    """_build_features 回傳含全部環境特徵欄、與 df 等長；db=None 時 macro 欄為 NaN、orderflow 算得出。"""
    df = _synthetic_bars(50)
    feats = _build_features(df, db=None)
    assert len(feats) == len(df), (len(feats), len(df))
    # macro 欄全 NaN（沒 db）
    assert feats["vix_level"].isna().all(), feats["vix_level"]
    # orderflow 恆等式：buy + sell == volume（compute_orderflow 鐵則）
    total = feats["buy_vol_proxy"] + feats["sell_vol_proxy"]
    assert np.allclose(total.to_numpy(), df["volume"].to_numpy()), "buy+sell 應等於 volume"
    print("✅ _build_features 欄位/對齊測試通過")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
