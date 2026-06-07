"""
meta-labeling 二級過濾（Meta-Labeling）── Phase 7 step-05
========================================================
出自 López de Prado《Advances in Financial Machine Learning》。在「策略給了進場訊號」之後，
再加一個**二級判斷**：這個訊號值不值得實際下注？信心多高？

- 一級模型（primary）：決定**方向**（買/賣）← 策略 + step-03 選擇器，追求不漏機會。
- 二級模型（secondary/meta）：決定**要不要執行**，輸出「成功機率/信心 p」，追求過濾爛訊號。
  p 可直接餵給 step-04 凱利當 W，把資金集中在高品質訊號上。

起步用**規則式 meta**（本檔）：拿 step-01 特徵 + step-02 狀態當條件，零過擬合、可解釋。
學習式 meta（訓練分類器輸出 p）是進階選配，且**必經 step-07 的 purged CV** 證明 OOS 有加分才上。

重用：step-01 compute_features 的特徵、step-02 classify_regime 的狀態。
"""

from backend.config import settings
from backend.services.regime import (
    REGIME_TRENDING,
    REGIME_RANGING,
    REGIME_HIGH_VOLUME_STALL,
    REGIME_HIGH_VOLATILITY,
    REGIME_UNKNOWN,
)
from backend.strategies.base import Signal


# 各狀態的「進場基礎信心」（規則式、可解釋）：
# - 趨勢盤：順勢進場品質最好 → 高信心。
# - 盤整盤：可做但邊際 → 中信心。
# - 爆量滯漲 / 高波動 / 未知：量價背離、混亂、資料不足 → 不該追，信心 0（否決）。
_REGIME_BASE_CONFIDENCE = {
    REGIME_TRENDING: 0.7,
    REGIME_RANGING: 0.5,
    REGIME_HIGH_VOLUME_STALL: 0.0,
    REGIME_HIGH_VOLATILITY: 0.0,
    REGIME_UNKNOWN: 0.0,
}


def meta_confidence(features: dict, regime: str) -> float:
    """
    規則式二級信心 p（0~1，越高代表這個進場越值得信）。

    以「狀態基礎信心」為主，再用特徵微調（趨勢越強、近期不過熱 → 略加分）。
    純函式、可解釋；輸出供 should_take 判定與 step-04 凱利當 W。
    """
    conf = _REGIME_BASE_CONFIDENCE.get(regime, 0.0)
    if conf <= 0:
        return 0.0

    # 趨勢強度加成：ADX 越高（趨勢越扎實）→ 最多 +0.15
    trend = features.get("trend_strength")
    if isinstance(trend, (int, float)):
        conf += min(0.15, max(0.0, (trend - settings.REGIME_ADX_TREND) / 100.0))

    # 過熱扣分：近 5 日漲幅過大（追高風險）→ 最多 −0.15
    ret5 = features.get("return_5d")
    if isinstance(ret5, (int, float)) and ret5 > settings.REGIME_FLAT_RETURN:
        conf -= min(0.15, (ret5 - settings.REGIME_FLAT_RETURN))

    return max(0.0, min(1.0, conf))


def should_take(signal: str, features: dict, regime: str) -> tuple[bool, float]:
    """
    二級判定：這個一級訊號該不該真的執行？回 (該執行?, 信心)。

    - 只過濾**進場（BUY）**；SELL / HOLD 原樣放行（出場與觀望不受二級門檻影響，
      回 (原訊號是否為動作, 0.0)）。
    - BUY：信心 >= META_MIN_CONFIDENCE 才放行；否則否決（縮回不下注）。
    - META_LABEL_ENABLED=False → 完全退回一級訊號（向後相容），BUY 一律放行、信心給 1.0。

    :return: (take, confidence)。take=False 代表二級否決，呼叫端應觀望。
    """
    if signal != Signal.BUY:
        return signal in (Signal.SELL,), 0.0

    if not settings.META_LABEL_ENABLED:
        return True, 1.0

    conf = meta_confidence(features, regime)
    return conf >= settings.META_MIN_CONFIDENCE, conf
