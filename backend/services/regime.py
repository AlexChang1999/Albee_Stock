"""
市場狀態分類器（Regime Classifier）── Phase 7 step-02
======================================================
把 step-01 的數字特徵，分類成幾種**有名字的市場狀態**。
你說的「不斷的二分法」字面上就是**決策樹**——每次依一個特徵做一刀二分。

路線 A（先做這個）：**規則式決策樹**（人手寫 if-else 閾值）。
- 完全可解釋（你看得懂「為什麼這天被判爆量滯漲」）、零過擬合、好除錯。
- 閾值集中放 config（好調、好測），不寫死。
- 路線 B（學習式 sklearn 分類器）沒有 step-07 驗證框架護體前不要碰。

狀態刻意只分 4 種（別爆炸）：分太細每種狀態的子樣本不足、統計就不可信。
"""

from backend.config import settings


# 狀態常數（對外用字串，給 step-03 的「狀態→策略對照表」當鍵）
REGIME_TRENDING = "trending"                 # 趨勢盤（ADX 強）
REGIME_RANGING = "ranging"                   # 盤整盤（無明顯趨勢，catch-all）
REGIME_HIGH_VOLUME_STALL = "high_volume_stall"  # 爆量滯漲（量大但不漲，量價背離）
REGIME_HIGH_VOLATILITY = "high_volatility"   # 高波動（混亂，優先別追）
REGIME_UNKNOWN = "unknown"                   # 資料不足，無法判斷（保守處理）

ALL_REGIMES = [
    REGIME_TRENDING,
    REGIME_RANGING,
    REGIME_HIGH_VOLUME_STALL,
    REGIME_HIGH_VOLATILITY,
]


def classify_regime(features: dict) -> str:
    """
    依特徵把當下市場分成一個狀態（規則式決策樹，逐層二分）。

    判斷順序（先排除危險、再抓特例、最後分趨勢/盤整）：
      1. 高波動（年化波動 ≥ 門檻）→ high_volatility（最先擋，混亂時別出手）
      2. 爆量滯漲（量比 ≥ 門檻 且 |近5日報酬| ≤ 門檻）→ high_volume_stall
      3. 趨勢強（ADX ≥ 門檻）→ trending
      4. 以上皆非 → ranging（盤整）

    特徵值為 None（資料不足）時，該條規則「不觸發」往下走；
    若連判斷所需的核心特徵全都是 None → unknown（上層應保守處理，不亂下注）。

    :param features: regime_features.compute_features(df) 的輸出
    :return: 狀態字串（見本檔常數）
    """
    vol = features.get("volatility_20d")
    volume = features.get("volume_ratio")
    ret5 = features.get("return_5d")
    trend = features.get("trend_strength")

    # 核心特徵全缺 → 無法判斷
    if vol is None and volume is None and trend is None:
        return REGIME_UNKNOWN

    # 1. 高波動優先（混亂市況，最該先認出來別追）
    if vol is not None and vol >= settings.REGIME_HIGH_VOL_THRESHOLD:
        return REGIME_HIGH_VOLATILITY

    # 2. 爆量滯漲：量能爆衝、但價格幾乎沒動（量價背離）
    if (
        volume is not None
        and ret5 is not None
        and volume >= settings.REGIME_VOLUME_SPIKE
        and abs(ret5) <= settings.REGIME_FLAT_RETURN
    ):
        return REGIME_HIGH_VOLUME_STALL

    # 3. 趨勢盤：ADX 夠強
    if trend is not None and trend >= settings.REGIME_ADX_TREND:
        return REGIME_TRENDING

    # 4. 都不符 → 盤整
    return REGIME_RANGING
