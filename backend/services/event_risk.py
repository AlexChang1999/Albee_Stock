"""
事件驅動風險閘（Event-Driven Risk Brake）── Phase 7 step-06
==========================================================
把「重大新聞 / 負面情緒」納入決策——但定位是**煞車（降風險），不是油門（猜方向）**。

殘酷現實：我們只有日線、本機 Llama，抓不到盤中分秒、也無可靠方向預測力。市場毫秒級消化
排程事件，retail 用日線永遠慢一步。所以這層**明確不宣稱能預測漲跌**，只做一件事：
重大負面情緒/事件期間 → **不開新倉 / 縮小部位**。

與既有情緒閘的分工（避免重造）：
- bearish / 分數低於 SENTIMENT_MIN_SCORE → 由 automation.apply_sentiment / screener.is_vetoed_by_sentiment
  **直接否決**（這層不重複那段）。
- 「不到否決、但偏謹慎」的中間帶（分數低於 CAUTION 但未達否決）→ 本層**縮部位**（非全砍）。

best-effort：情緒為 None（LLM 連不上 / 被外送閘擋下）→ 不煞車、不阻斷（size_factor=1.0）。

重用：screener.parse_sentiment / sentiment_score / is_vetoed_by_sentiment（情緒管線已存在）。
"""

from backend.config import settings
from backend.services import screener


def assess_event_risk(
    sentiment,
    *,
    enabled: bool | None = None,
    veto_score: float | None = None,
    caution_score: float | None = None,
    size_factor: float | None = None,
) -> dict:
    """
    依當下情緒回「要不要降風險、部位縮多少」（純函式，不猜方向）。

    :param sentiment: parse_sentiment 的格式 dict 或 None。
    :param enabled: 總開關；None 用 settings.EVENT_RISK_ENABLED。
    :param veto_score: 否決門檻；None 用 settings.SENTIMENT_MIN_SCORE。
    :param caution_score: 謹慎帶門檻；None 用 settings.EVENT_RISK_CAUTION_SCORE。
    :param size_factor: 謹慎帶的部位縮放係數；None 用 settings.EVENT_RISK_SIZE_FACTOR。
    :return: {"brake": bool, "size_factor": float(0~1), "reason": str}
             brake=True 代表「不開新倉」（size_factor=0）；
             size_factor<1 代表「縮部位」；=1 代表照常。
    """
    enabled = enabled if enabled is not None else settings.EVENT_RISK_ENABLED
    veto_score = veto_score if veto_score is not None else settings.SENTIMENT_MIN_SCORE
    caution_score = caution_score if caution_score is not None else settings.EVENT_RISK_CAUTION_SCORE
    size_factor = size_factor if size_factor is not None else settings.EVENT_RISK_SIZE_FACTOR

    if not enabled:
        return {"brake": False, "size_factor": 1.0, "reason": "事件風險閘未啟用"}

    # best-effort：沒情緒資料 → 不煞車（離線不阻斷）
    if not isinstance(sentiment, dict):
        return {"brake": False, "size_factor": 1.0, "reason": "無情緒資料，照常（best-effort）"}

    # 重大負面 → 不開新倉（與既有情緒否決一致，這裡轉成風險語意）
    if screener.is_vetoed_by_sentiment(sentiment, min_score=veto_score):
        return {"brake": True, "size_factor": 0.0,
                "reason": "重大負面情緒/事件：不開新倉（降風險，不猜方向）"}

    # 謹慎帶：偏弱但未達否決 → 縮部位
    score = screener.sentiment_score(sentiment)
    if score < caution_score:
        return {"brake": False, "size_factor": max(0.0, min(1.0, size_factor)),
                "reason": f"情緒偏弱（{score} < {caution_score}）：縮部位至 {size_factor:.0%}"}

    return {"brake": False, "size_factor": 1.0, "reason": "情緒中性/正向：照常"}
