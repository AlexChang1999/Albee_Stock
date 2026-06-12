"""
探勘橋 — raw find → LLM 產候選（Phase 12 step-02）
====================================================
把「人讀收件匣 → 人打 /knowledge/propose」自動化：每日定時取收件匣（raw_strategy_finds,
status=new）的素材，交給本機 Ollama 判讀「這篇在講哪種**既有**策略？建議什麼參數？」：
- 有提案 → 走 strategy_generator 同合約建 StrategyKnowledge candidate，find 標 built。
- 不相關 / 解析失敗 → find 標 discarded（原因落 triage_note，決策可回查）。

明確界線（防 slop / 防漂移）：
- LLM 只准從**既有策略清單**（STRATEGY_REGISTRY）挑、只准提參數；
  **不**自動生成新策略程式碼（新策略模組仍走人工 strategy-builder skill）。
- composite（組合策略）沒有可草擬的參數 schema，一律不接受（同 routers/knowledge.py 體例）。
- 素材只進本機 LLM prompt，不外送雲端（走 llm.py 同一道 LLM_ALLOW_CLOUD 外送閘）。
- candidate 只是「假設」：之後仍要過 OOS 閘（step-03 / evolution.validate_candidate）
  + 人工晉升 curated 才算數。本檔不回測、不部署、不下單。
- 一輪最多 DISCOVERY_BATCH_SIZE 筆（防 LLM 跑整夜）；Ollama 連不上 → 整批跳過、
  不標記任何 find，下一輪再來（不誤殺素材）。

設計：triage_find / build_triage_prompt 是純函式（好測）；run_discovery_batch 才碰 DB/LLM。
"""

import json
import logging

from backend.config import settings
from backend.database import SessionLocal
from backend.models import RawStrategyFind
from backend.models.strategy_knowledge import StrategyKnowledge
from backend.services import llm
from backend.strategies import STRATEGY_REGISTRY

logger = logging.getLogger(__name__)

# LLM 回覆上限：一筆素材只需要一個小 JSON 物件，給太多 token 只會引來廢話
_MAX_TOKENS = 512

# 信心下限：LLM 自評信心低於此值的提案不採用（寧可 discard 也不灌水 candidate 區）
_MIN_CONFIDENCE = 0.5


def build_triage_prompt(find) -> list[dict]:
    """
    組 triage 用的對話 prompt（純函式）。

    合約：只准從既有策略鍵挑一個 + 提參數；素材與任何既有策略無關、或需要寫新程式碼
    才能實現 → 要求回 null。回覆格式鎖死成單一 JSON 物件，方便 triage_find 解析。
    """
    # 既有策略清單（同 GET /strategies 的單一來源），composite 沒參數 schema 不給挑
    keys = [k for k in STRATEGY_REGISTRY.keys() if k != "composite"]
    sys_text = (
        "你是量化策略素材分類器。判斷一篇文章摘要在描述哪種「既有策略」並建議參數。"
        "只回一個 JSON 物件，不要任何多餘文字："
        '{"strategy_key": "策略鍵", "params": {"參數名": 數值}, '
        '"confidence": 0~1 的數字, "reason": "一句話理由"}。'
        f"strategy_key 只能從這個清單挑：{keys}。"
        "若文章與清單中任何策略無關、或需要撰寫新程式碼才能實現，直接回 null。"
    )
    user_text = (
        f"標題：{find.title}\n"
        f"摘要：{find.summary}\n\n"
        "這篇在講哪種既有策略？建議什麼參數？沒把握就回 null。"
    )
    return [
        {"role": "system", "content": sys_text},
        {"role": "user", "content": user_text},
    ]


def triage_find(find, llm_reply: str) -> dict | None:
    """
    解析 LLM 回覆成提案 dict（純函式）。

    :return: {"strategy_key", "params", "confidence", "reason"}；
             解析失敗 / 不相關（null）/ 非法策略鍵 / 信心不足 → None（呼叫端標 discarded）。
    """
    raw = (llm_reply or "").strip()
    if not raw:
        return None
    # 容忍模型在 JSON 前後夾雜文字：取第一個 '{' 到最後一個 '}' 之間解析
    # （同 strategy_generator._parse_param_list 精神）。先處理明確回 null 的情況。
    if raw.lower().startswith("null"):
        return None
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except Exception:
        return None
    if not isinstance(data, dict):
        return None

    key = data.get("strategy_key")
    params = data.get("params")
    # 只准既有策略 + 參數 dict；composite 一律擋（沒有可草擬的參數 schema）
    if key not in STRATEGY_REGISTRY or key == "composite":
        return None
    if not isinstance(params, dict) or not params:
        return None
    # 參數值只收數字（LLM 想塞程式碼字串 / 巢狀結構 = 違反「只提參數」合約，直接拒絕）
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in params.values()):
        return None

    try:
        confidence = float(data.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence < _MIN_CONFIDENCE:
        return None

    return {
        "strategy_key": key,
        "params": params,
        "confidence": confidence,
        "reason": str(data.get("reason") or "")[:300],
    }


def run_discovery_batch(db=None) -> dict:
    """
    跑一輪探勘橋：取 status=new 的素材至多 DISCOVERY_BATCH_SIZE 筆，逐筆 LLM triage。

    - DISCOVERY_ENABLED=false → 直接 return（排程掛載處也有閘，這裡是雙保險）。
    - LLM 沒設定 / 連不上 → 整批跳過、**不標記任何 find**，下一輪再來。
    - 有提案 → 建 StrategyKnowledge(status=candidate)，find 標 built + 回填 knowledge_id。
    - 無提案 → find 標 discarded，原因落 triage_note。
    - 冪等：只取 status=new，重跑不會二次 triage 已處理的素材。

    :param db: 測試可注入 session；None = 自建（排程入口用）。
    :return: {"processed", "built", "discarded", "skipped"} 統計。
    """
    stats = {"processed": 0, "built": 0, "discarded": 0, "skipped": 0}
    if not settings.DISCOVERY_ENABLED:
        return stats

    # 外送閘 + 客戶端檢查：非本機且未允許外送、或沒設 LLM → 整批跳過（素材不外洩）
    if llm.cloud_blocked():
        logger.warning("探勘橋：LLM 指向雲端且未開外送閘，整批跳過（素材不外送）")
        return stats
    client = llm.get_client()
    if client is None:
        logger.info("探勘橋：LLM 未設定，整批跳過")
        return stats

    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        finds = (
            db.query(RawStrategyFind)
            .filter(RawStrategyFind.status == "new")
            .order_by(RawStrategyFind.id)
            .limit(max(1, settings.DISCOVERY_BATCH_SIZE))
            .all()
        )
        for find in finds:
            try:
                reply = llm.complete(
                    client, build_triage_prompt(find), max_tokens=_MAX_TOKENS
                )
            except Exception as e:
                # 連不上 / 逾時：別標記、別繼續打（多半整批都會失敗），下一輪再來
                logger.warning("探勘橋：LLM 呼叫失敗，本輪中止：%s", llm.friendly_err(e))
                stats["skipped"] += 1
                break

            stats["processed"] += 1
            proposal = triage_find(find, reply)
            if proposal is None:
                find.status = "discarded"
                find.triage_note = "探勘橋：LLM 判定與既有策略無關或回覆無法解析"
                stats["discarded"] += 1
                continue

            # 與 POST /knowledge/propose 同欄位合約建 candidate（scenario = 素材摘要，
            # 之後 OOS 驗證 / 人工策展都看得到出處脈絡）
            k = StrategyKnowledge(
                name=f"{proposal['strategy_key']} 探勘候選（{(find.title or '')[:40]}）",
                strategy_key=proposal["strategy_key"],
                scenario=f"來源：{find.source_url}\n{find.summary}"[:1000],
                params=proposal["params"],
                status="candidate",
            )
            db.add(k)
            db.flush()  # 先拿到 k.id 才能回填 knowledge_id
            find.status = "built"
            find.knowledge_id = k.id
            find.triage_note = (
                f"探勘橋：提案 {proposal['strategy_key']} "
                f"params={proposal['params']} 信心={proposal['confidence']:.2f}"
                f"｜{proposal['reason']}"
            )
            stats["built"] += 1

        db.commit()
    finally:
        if own_session:
            db.close()

    logger.info(
        "探勘橋完成：processed=%s built=%s discarded=%s skipped=%s",
        stats["processed"], stats["built"], stats["discarded"], stats["skipped"],
    )
    return stats
