"""
策略進化反饋迴圈（strategy_feedback.py）
==========================================
當 Paper Bot 被汰弱（bot_review._cull_bot）或 tracking 連續違規降級（tracking._demote_bot）後，
自動分析失敗原因，由 LLM 提出新參數候選，寫入 StrategyKnowledge（status=candidate）。

新候選仍須走「人在迴路」流程（validate → promote → deploy），不會直接上線。

主函式 generate_candidate_from_paper(bot_id, db) 的觸發條件：
  1. 該 Bot 有 ≥ FEEDBACK_MIN_ROUND_TRIPS（預設 5）筆完整買賣回合
  2. 近期實跑均值 < OOS 期望值 × FEEDBACK_MIN_RATIO（預設 0.6）→ 顯著偏差才觸發
  3. LLM 可用（Ollama 有在跑）

優雅降級：任一條件不滿足或 LLM 失敗，回傳 {"triggered": False, "reason": "..."} 不往上拋。
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import Bot, DecisionLog, TradeLog, StrategyKnowledge
from backend.services import llm as _llm
from backend.services.performance import compute_round_trip_returns

logger = logging.getLogger(__name__)


def _recent_oos_expectancy(db: Session, strategy_key: str) -> float | None:
    """查該策略在 StrategyKnowledge 中最佳的 OOS expectancy_pct（%）。"""
    rows = (
        db.query(StrategyKnowledge)
        .filter(
            StrategyKnowledge.strategy_key == strategy_key,
            StrategyKnowledge.status.in_(["validated", "curated"]),
            StrategyKnowledge.oos_metrics.isnot(None),
        )
        .all()
    )
    best = None
    for r in rows:
        metrics = r.oos_metrics or {}
        ev = metrics.get("expectancy_pct") or metrics.get("oos_expected_value")
        if ev is not None:
            best = max(best, float(ev)) if best is not None else float(ev)
    return best


def _recent_paper_ev(bot_id: int, db: Session) -> tuple[float | None, int]:
    """
    計算該 Bot 近期 FEEDBACK_MIN_ROUND_TRIPS 回合的平均報酬率（%）。
    回傳 (平均報酬率 或 None, 回合數)。
    """
    trades = (
        db.query(TradeLog)
        .filter(TradeLog.bot_id == bot_id)
        .order_by(TradeLog.created_at.asc())
        .all()
    )
    trade_dicts = [{"side": t.side, "qty": t.qty, "price": t.price,
                    "created_at": t.created_at} for t in trades]
    rts = compute_round_trip_returns(trade_dicts)
    if not rts:
        return None, 0
    # 取最近 N 回合
    recent = rts[-settings.FEEDBACK_MIN_ROUND_TRIPS:]
    avg_ev = sum(r["return_pct"] for r in recent) / len(recent)
    return avg_ev, len(rts)


def _gather_failure_context(bot_id: int, db: Session) -> list[dict]:
    """收集最近 FEEDBACK_THESIS_LIMIT 筆止損/賣出決策的 thesis_breach + indicators。"""
    logs = (
        db.query(DecisionLog)
        .filter(
            DecisionLog.bot_id == bot_id,
            DecisionLog.action == "sold",
        )
        .order_by(DecisionLog.created_at.desc())
        .limit(settings.FEEDBACK_THESIS_LIMIT)
        .all()
    )
    return [
        {
            "exit_kind": log.exit_kind,
            "thesis_breach": log.thesis_breach,
            "reason": log.reason,
            "indicators": log.indicators,
            "market_snapshot": log.market_snapshot,
        }
        for log in logs
    ]


def _build_feedback_prompt(bot: Bot, current_params: dict,
                            paper_ev: float, oos_ev: float,
                            failure_cases: list[dict]) -> str:
    """組繁體中文 LLM prompt，請 AI 提出改善策略參數的建議。"""
    cases_str = "\n".join(
        f"  [{i+1}] exit_kind={c['exit_kind']}，原因：{c['thesis_breach'] or c['reason']}"
        + (f"，指標：{json.dumps(c['indicators'], ensure_ascii=False)}" if c.get("indicators") else "")
        for i, c in enumerate(failure_cases[:8])
    )

    return f"""你是美股量化交易策略改進顧問。

【Bot 基本資料】
- 名稱：{bot.name}
- 策略：{bot.strategy}（標的：{bot.symbol}）
- 目前參數：{json.dumps(current_params, ensure_ascii=False)}

【績效比對】
- 回測 OOS 期望報酬率：{oos_ev:.2f}%
- Paper Trading 近期實跑平均報酬率：{paper_ev:.2f}%（顯著低於 OOS）

【近期失敗案例摘錄】
{cases_str or "（無失敗案例資料）"}

請用繁體中文完成以下任務：

1. 分析失敗模式：是什麼原因導致實跑遠低於回測 OOS？（2-3 句）

2. 提出改善後的策略參數（JSON 格式，與目前參數結構一致，只調整你有把握的欄位）：
```json
{{改善後的完整參數 JSON}}
```

3. 說明參數調整的理由（2-3 句）。

注意：不要調整止損/止盈百分比（那是風控層）；專注在策略訊號本身的技術參數。"""


def generate_candidate_from_paper(bot_id: int, db: Session) -> dict:
    """
    從 Paper Bot 實跑結果生成新策略候選。

    Bot 被汰弱或降級後由 bot_review._cull_bot / tracking._demote_bot 呼叫。
    失敗時優雅回傳 {triggered: False, reason: ...}，不往上拋例外。

    :param bot_id: 被停掉的 Bot ID。
    :param db: SQLAlchemy Session。
    :return: {"triggered": bool, "reason": str, "new_knowledge_id": int（僅 triggered=True 時）}
    """
    try:
        return _generate_candidate_inner(bot_id, db)
    except Exception as e:
        logger.warning("strategy_feedback 生成候選失敗（bot_id=%s）：%s", bot_id, e)
        return {"triggered": False, "reason": f"例外：{e}"}


def _generate_candidate_inner(bot_id: int, db: Session) -> dict:
    """實際執行邏輯（由 generate_candidate_from_paper 包裹 try/except）。"""
    # 1. 確認 LLM 可用
    if _llm.cloud_blocked():
        return {"triggered": False, "reason": "LLM 外送閘關閉（LLM_ALLOW_CLOUD=false）"}
    client = _llm.get_client()
    if client is None:
        return {"triggered": False, "reason": "LLM 未設定（LLM_BASE_URL/LLM_MODEL 空）"}

    # 2. 取得 Bot
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if bot is None:
        return {"triggered": False, "reason": f"Bot#{bot_id} 不存在"}

    # 3. 計算近期實跑績效
    paper_ev, total_rts = _recent_paper_ev(bot_id, db)
    if paper_ev is None or total_rts < settings.FEEDBACK_MIN_ROUND_TRIPS:
        return {
            "triggered": False,
            "reason": f"回合數不足（需 ≥ {settings.FEEDBACK_MIN_ROUND_TRIPS}，實有 {total_rts}）",
        }

    # 4. 查 OOS 基準
    oos_ev = _recent_oos_expectancy(db, bot.strategy)
    if oos_ev is None:
        return {"triggered": False, "reason": f"找不到策略 {bot.strategy} 的 OOS 期望值基準"}

    # 5. 判斷是否有顯著偏差（實跑 < OOS × ratio 才觸發）
    threshold = oos_ev * settings.FEEDBACK_MIN_RATIO
    if paper_ev >= threshold:
        return {
            "triggered": False,
            "reason": (
                f"實跑 {paper_ev:.2f}% ≥ 門檻 {threshold:.2f}%（OOS {oos_ev:.2f}% × {settings.FEEDBACK_MIN_RATIO}），"
                "未達觸發條件"
            ),
        }

    # 6. 收集失敗案例
    failure_cases = _gather_failure_context(bot_id, db)

    # 7. 呼叫 LLM
    prompt = _build_feedback_prompt(
        bot=bot,
        current_params=bot.params or {},
        paper_ev=paper_ev,
        oos_ev=oos_ev,
        failure_cases=failure_cases,
    )
    try:
        llm_response = _llm.complete(
            client,
            [{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.5,
        )
    except Exception as e:
        return {"triggered": False, "reason": f"LLM 呼叫失敗：{_llm.friendly_err(e)}"}

    # 8. 嘗試從 LLM 回覆解析新參數 JSON
    new_params = dict(bot.params or {})  # 預設沿用原參數
    try:
        import re
        json_match = re.search(r"```(?:json)?\s*(\{[\s\S]+?\})\s*```", llm_response)
        if json_match:
            new_params = json.loads(json_match.group(1))
    except Exception:
        pass  # 解析失敗就沿用原參數，不阻塞

    # 9. 查找對應的原始 StrategyKnowledge（parent_id）
    parent = (
        db.query(StrategyKnowledge)
        .filter(
            StrategyKnowledge.strategy_key == bot.strategy,
            StrategyKnowledge.status.in_(["validated", "curated"]),
        )
        .order_by(StrategyKnowledge.created_at.desc())
        .first()
    )

    # 10. 建立新 candidate
    new_knowledge = StrategyKnowledge(
        name=f"{bot.strategy} 改進版（來自 {bot.name} 實跑回饋）",
        strategy_key=bot.strategy,
        params=new_params,
        status="candidate",
        origin="paper_feedback",
        parent_id=parent.id if parent else None,
        evolution_note=llm_response,
        theory=f"由 Paper Bot {bot.name}（{bot.symbol}）實跑失效後，AI 自動分析提案。\n"
               f"實跑近期均值 {paper_ev:.2f}%，低於 OOS 基準 {oos_ev:.2f}%。",
    )
    db.add(new_knowledge)
    db.commit()
    db.refresh(new_knowledge)

    logger.info(
        "strategy_feedback：為 Bot#%s（%s/%s）建立新候選 knowledge#%s",
        bot_id, bot.strategy, bot.symbol, new_knowledge.id,
    )

    return {
        "triggered": True,
        "new_knowledge_id": new_knowledge.id,
        "reason": (
            f"實跑均值 {paper_ev:.2f}% < OOS {oos_ev:.2f}% × {settings.FEEDBACK_MIN_RATIO} = "
            f"{threshold:.2f}%，觸發 AI 提案"
        ),
    }
