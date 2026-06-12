"""
政治專討員 — 貼文判讀 + 風險煞車 bridge（Phase 10 step-05）
============================================================
把 Discord 頻道偵測到的政治貼文（例如川普發文鏡像）判讀成「事件 / 頻率分數」，
餵進**既有風險煞車** `event_risk.assess_event_risk`。

★ 定位：**煞車（降風險、縮部位、不開新倉），不是油門（不據此猜方向重壓）。**
  「貼文 → 漲跌」最易過擬合、無乾淨 point-in-time 對齊資料可誠實回測，所以這層
  明確不宣稱能預測方向，只在「重大負面」時降風險。頻率高 ≠ 加碼（factor 上限 1.0）。

重用既有（勿重造）：
- `llm.get_client` / `llm.complete` / `llm.cloud_blocked`（本機 Ollama，守外送閘）。
- `screener.parse_sentiment`（穩健抓 {label, score, reason}，與既有情緒同格式）。
- `event_risk.assess_event_risk`（既有風險煞車）。

設計：parse / frequency / judge / bridge 都做成純函式（judge 用 monkeypatch 的 LLM 測），
不連網、不連 Discord 也能跑測試。
"""

from datetime import datetime, timedelta

from backend.config import settings
from backend.database import SessionLocal
from backend.models import PoliticalEvent
from backend.services import llm, screener, event_risk

# 摘要截斷長度（不存整篇貼文）
_SUMMARY_LIMIT = 400


def summarize_post(text: str, *, limit: int = _SUMMARY_LIMIT) -> str:
    """把貼文壓成單行摘要（去多餘空白 + 截斷）。純函式。"""
    s = " ".join((text or "").split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


def frequency_features(timestamps: list, now: datetime) -> dict:
    """
    從一串發文時間戳算頻率特徵（觀測佐證，不放大部位）。純函式。

    :param timestamps: 該作者的歷史發文時間（datetime 清單，可含本則）。
    :param now: 基準時間（通常是本則貼文時間）。
    :return: {"posts_last_24h": int, "posts_last_1h": int}
    """
    h24 = now - timedelta(hours=24)
    h1 = now - timedelta(hours=1)
    last_24h = sum(1 for t in timestamps if t is not None and h24 <= t <= now)
    last_1h = sum(1 for t in timestamps if t is not None and h1 <= t <= now)
    return {"posts_last_24h": last_24h, "posts_last_1h": last_1h}


def judge_post(client, text: str) -> dict:
    """
    請本機 LLM 判讀貼文對股市的「風險方向」，回 {label, score, reason}（與情緒同格式）。

    定位是煞車：問的是「這則貼文對美股是偏空（風險）還是中性」，不要求預測漲幅。
    連不上 / 出錯 / 空白 → 中性（best-effort，離線不阻斷）。
    """
    if not (text or "").strip():
        return {"label": "neutral", "score": 0, "reason": "（空白貼文）"}

    sys = "你是金融市場政治風險分析器。只回 JSON，不要多餘文字。"
    user = (
        "以下是一則政治人物的貼文。請判斷它對美股整體是否帶來『下行風險 / 負面情緒』。"
        "你的工作是『煞車』——只評估風險方向，不要預測漲幅、不要喊進場。\n\n"
        f"貼文：\n{summarize_post(text)}\n\n"
        '只回 JSON：{"label":"bullish|bearish|neutral","score":-100到100的整數,"reason":"一句話"}'
        "（score 越負代表對市場風險越高）"
    )
    try:
        raw = llm.complete(
            client,
            [{"role": "system", "content": sys}, {"role": "user", "content": user}],
            max_tokens=200,
            temperature=0.2,
        )
        return screener.parse_sentiment(raw)
    except Exception:
        return {"label": "neutral", "score": 0, "reason": "（判讀失敗）"}


def judge_post_best_effort(text: str) -> dict:
    """
    建 client + 守外送閘 + 判讀，一步到位（給 Discord runner 用）。

    LLM 沒設定 / 指向雲端卻沒開外送閘 → 回中性、不判讀（資料不外洩、離線不阻斷）。
    """
    client = llm.get_client()
    if client is None or llm.cloud_blocked():
        return {"label": "neutral", "score": 0, "reason": "（未判讀：LLM 未設定或外送閘關閉）"}
    return judge_post(client, text)


def event_to_sentiment(event) -> dict:
    """把一筆 PoliticalEvent（或同欄位 dict）轉成 {label, score, reason} 情緒格式。純函式。"""
    if event is None:
        return None
    if isinstance(event, dict):
        label, score, reason = event.get("label"), event.get("score"), event.get("reason")
    else:
        label, score, reason = event.label, event.score, event.reason
    return {
        "label": label or "neutral",
        "score": int(score) if isinstance(score, (int, float)) else 0,
        "reason": reason or "",
    }


def latest_event_sentiment(db, *, max_age_hours: float | None = None, now: datetime | None = None) -> dict | None:
    """
    取「夠新」的最近一筆政治事件、轉成情緒 dict；沒有 / 太舊 → None（best-effort 不煞車）。

    :param max_age_hours: 事件超過幾小時就視為過期不採用；None 用 settings 預設。
    """
    max_age_hours = max_age_hours if max_age_hours is not None else settings.POLITICAL_EVENT_MAX_AGE_HOURS
    now = now or datetime.now()
    row = (
        db.query(PoliticalEvent)
        .order_by(PoliticalEvent.posted_at.desc(), PoliticalEvent.id.desc())
        .first()
    )
    if row is None:
        return None
    if row.posted_at and max_age_hours and max_age_hours > 0:
        if row.posted_at < now - timedelta(hours=max_age_hours):
            return None  # 太舊：政治情緒退場，不再煞車
    return event_to_sentiment(row)


def political_size_factor(db, *, enabled: bool | None = None, now: datetime | None = None) -> dict:
    """
    ★ bridge：把最近的政治事件接進既有風險煞車，回 {brake, size_factor, reason}。

    這是 step-05 與引擎室的唯一接點，且**預設關閉**（settings.POLITICAL_ENABLED）。
    - 未啟用 → 直接放行（size_factor=1.0），完全不影響現行下單路徑（向後相容）。
    - 啟用 → 取最近夠新的政治情緒，交給 event_risk.assess_event_risk 決定縮多少 /
      要不要不開新倉。沒有政治資料 → assess_event_risk(None) 也是 best-effort 不煞車。

    **只縮部位 / 不開新倉，不猜方向**——所有風險語意都由既有 event_risk 統一決定。
    """
    enabled = enabled if enabled is not None else settings.POLITICAL_ENABLED
    if not enabled:
        return {"brake": False, "size_factor": 1.0, "reason": "政治風險閘未啟用（預設關）"}

    sentiment = latest_event_sentiment(db, now=now)
    return event_risk.assess_event_risk(sentiment)


def record_event(db, *, source: str, author: str, text: str, posted_at: datetime,
                 verdict: dict, freq: dict | None = None) -> PoliticalEvent:
    """
    把一筆判讀完的政治貼文落表（給 Discord runner 用）。

    :param verdict: judge_post(_best_effort) 的結果 {label, score, reason}。
    :param freq: frequency_features 的結果（可選）。
    """
    freq = freq or {}
    row = PoliticalEvent(
        source=source or "",
        author=author or "",
        content_summary=summarize_post(text),
        label=(verdict or {}).get("label", "neutral"),
        score=float((verdict or {}).get("score", 0) or 0),
        reason=(verdict or {}).get("reason", ""),
        posted_at=posted_at or datetime.now(),
        fetched_at=datetime.now(),
        posts_last_24h=freq.get("posts_last_24h"),
        posts_last_1h=freq.get("posts_last_1h"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def event_exists(db, *, author: str, posted_at: datetime) -> bool:
    """
    回補防重：同作者 + 同發文時間已落表 → 跳過，不重寫。

    表沒存 Discord message_id，但 Discord 訊息時間戳精確到微秒，
    同作者同時刻幾乎不可能撞，拿 (author, posted_at) 當天然唯一鍵即可，免遷移加欄位。
    """
    return (
        db.query(PoliticalEvent)
        .filter(
            PoliticalEvent.author == (author or ""),
            PoliticalEvent.posted_at == posted_at,
        )
        .first()
        is not None
    )


def get_session():
    """給 runner 取一個 DB session（包一層方便測試 monkeypatch）。"""
    return SessionLocal()
