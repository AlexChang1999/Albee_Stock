"""
AI 每日交易事後檢討服務（trade_review.py）
==========================================
每天美股收盤後（UTC 20:00 = ET 16:00）自動觸發，讀取當日所有 Bot 的決策與成交紀錄，
交由本機 LLM 分析虧損模式，並把分析結果寫進 explorations/ + 推播摘要通知。

主流程 run_daily_review(date, db)：
  1. 從 DecisionLog 抓當日決策（action in bought/sold）
  2. 從 TradeLog 抓當日成交，用 compute_round_trip_returns() 算 round-trip P&L
  3. 彙整 exit_kind 分佈、top-5 thesis_breach、止損時的指標快照
  4. 組 LLM prompt → 呼叫 llm.complete()
  5. 把 AI 分析寫到 explorations/review-YYYY-MM-DD.md
  6. 呼叫 notifier.notify() 推播摘要首段
  7. 回傳結構化摘要

LLM 不可用（Ollama 未啟動 / 連線失敗）時：
  → 仍回傳統計彙整，llm_used=False，不阻塞排程。

只分析不下單、不改策略、不影響運行中的 Bot。
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date as _date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from backend.models import Bot, DecisionLog, TradeLog
from backend.services import llm as _llm
from backend.services.notifier import notify
from backend.services.performance import compute_round_trip_returns


# explorations 目錄：沿用 settings.EXPLORATIONS_DIR，預設 {根}/explorations/
def _explorations_dir() -> Path:
    from backend.config import settings
    d = settings.EXPLORATIONS_DIR if settings.EXPLORATIONS_DIR else None
    if d:
        p = Path(d)
    else:
        p = Path(__file__).parents[2] / "explorations"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write_review_file(date_str: str, content: str) -> str:
    """把分析寫到 explorations/review-YYYY-MM-DD.md，回傳相對路徑。"""
    filename = f"review-{date_str}.md"
    path = _explorations_dir() / filename
    path.write_text(content, encoding="utf-8")
    return filename


def _build_bot_summary(bot_id: int, bot_name: str, strategy: str, symbol: str,
                        decisions: list, trades: list) -> dict:
    """彙整單一 Bot 的當日摘要。"""
    # 計算 round-trip P&L
    trade_dicts = [{"side": t.side, "qty": t.qty, "price": t.price,
                    "created_at": t.created_at} for t in trades]
    rts = compute_round_trip_returns(trade_dicts)
    total_pnl = sum(r["profit"] for r in rts)

    # exit_kind 分佈
    exit_kinds: dict[str, int] = defaultdict(int)
    thesis_breaches: list[str] = []
    stop_loss_indicators: list[dict] = []

    for d in decisions:
        if d.action == "sold":
            if d.exit_kind:
                exit_kinds[d.exit_kind] += 1
            if d.thesis_breach:
                thesis_breaches.append(d.thesis_breach)
            if d.exit_kind == "stop_loss" and d.indicators:
                stop_loss_indicators.append(d.indicators)

    return {
        "bot_id": bot_id,
        "bot_name": bot_name,
        "strategy": strategy,
        "symbol": symbol,
        "round_trips": len(rts),
        "pnl": round(total_pnl, 2),
        "exit_kinds": dict(exit_kinds),
        "thesis_breaches": thesis_breaches[:5],         # top-5 顯示
        "stop_loss_indicators": stop_loss_indicators[:3],  # top-3 指標快照
        "decisions_count": len(decisions),
    }


def _build_llm_prompt(date_str: str, bot_summaries: list[dict]) -> str:
    """組成繁體中文 LLM 分析 prompt。"""
    lines = [
        f"你是美股交易策略事後分析師。以下是 {date_str} 的 Paper Trading 決策摘要。",
        "",
        "【Bot 列表】",
    ]
    total_pnl = 0.0
    for s in bot_summaries:
        lines.append(
            f"- {s['bot_name']}（{s['strategy']} / {s['symbol']}）："
            f"{s['round_trips']} 回合，P&L ${s['pnl']:.0f}"
        )
        total_pnl += s["pnl"]
    lines += ["", f"【今日合計 P&L】：${total_pnl:.0f}", ""]

    # 出場分類彙整
    all_exit_kinds: dict[str, int] = defaultdict(int)
    for s in bot_summaries:
        for k, v in s["exit_kinds"].items():
            all_exit_kinds[k] += v
    if all_exit_kinds:
        lines.append("【出場分類彙整】")
        for kind, cnt in sorted(all_exit_kinds.items(), key=lambda x: -x[1]):
            label = {
                "stop_loss": "固定止損",
                "take_profit": "止盈",
                "trailing": "追蹤止損",
                "signal_reversal": "策略訊號反轉",
                "broker_settled": "券商端保護單成交",
            }.get(kind, kind)
            lines.append(f"  {label}：{cnt} 次")
        lines.append("")

    # 失效假設（thesis_breach）
    all_thesis = []
    for s in bot_summaries:
        all_thesis.extend(s["thesis_breaches"])
    if all_thesis:
        lines.append("【買入假設失效摘錄（top-5）】")
        for tb in all_thesis[:5]:
            lines.append(f"  - {tb}")
        lines.append("")

    # 代表性止損指標快照
    all_indicators = []
    for s in bot_summaries:
        all_indicators.extend(s["stop_loss_indicators"])
    if all_indicators:
        lines.append("【止損時指標快照（代表性樣本）】")
        for ind in all_indicators[:3]:
            lines.append(f"  {json.dumps(ind, ensure_ascii=False)}")
        lines.append("")

    lines += [
        "請用繁體中文分析以下三點（每點 2-4 句）：",
        "1. 哪類決策導致今日虧損？有無系統性模式？",
        "2. 是什麼市場條件讓策略失效？",
        "3. 針對今日失效的 Bot，有無明顯的參數改進方向（例如調整止損寬度、均線週期等）？",
    ]
    return "\n".join(lines)


def run_daily_review(date_str: str, db: Session) -> dict:
    """
    執行 AI 每日交易事後檢討。

    :param date_str: 要分析的日期，格式 YYYY-MM-DD。
    :param db: SQLAlchemy Session。
    :return: 摘要 dict（date, bots_reviewed, file_written, llm_used, summary_snippet）。
    """
    # 解析日期範圍（全天）
    try:
        target_dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return {"error": f"日期格式錯誤：{date_str}，應為 YYYY-MM-DD"}

    day_start = target_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = target_dt.replace(hour=23, minute=59, second=59, microsecond=999999)

    # 抓當日 DecisionLog（bought 和 sold）
    all_decisions = (
        db.query(DecisionLog)
        .filter(
            DecisionLog.created_at >= day_start,
            DecisionLog.created_at <= day_end,
            DecisionLog.action.in_(["bought", "sold"]),
        )
        .order_by(DecisionLog.bot_id, DecisionLog.created_at.asc())
        .all()
    )

    if not all_decisions:
        return {
            "date": date_str,
            "bots_reviewed": 0,
            "file_written": None,
            "llm_used": False,
            "summary_snippet": f"{date_str} 無交易決策紀錄（可能非交易日，或 Bot 未啟動）",
        }

    # 按 bot_id 分組
    by_bot: dict[int, list] = defaultdict(list)
    for d in all_decisions:
        by_bot[d.bot_id].append(d)

    # 抓當日 TradeLog
    all_trades = (
        db.query(TradeLog)
        .filter(
            TradeLog.created_at >= day_start,
            TradeLog.created_at <= day_end,
        )
        .order_by(TradeLog.bot_id, TradeLog.created_at.asc())
        .all()
    )
    trades_by_bot: dict[int, list] = defaultdict(list)
    for t in all_trades:
        trades_by_bot[t.bot_id].append(t)

    # 查 Bot 基本資料
    bot_ids = list(by_bot.keys())
    bots = {b.id: b for b in db.query(Bot).filter(Bot.id.in_(bot_ids)).all()}

    # 建立每個 Bot 的摘要
    bot_summaries = []
    for bot_id, decisions in by_bot.items():
        b = bots.get(bot_id)
        summary = _build_bot_summary(
            bot_id=bot_id,
            bot_name=b.name if b else f"Bot#{bot_id}",
            strategy=b.strategy if b else "unknown",
            symbol=b.symbol if b else "unknown",
            decisions=decisions,
            trades=trades_by_bot[bot_id],
        )
        bot_summaries.append(summary)

    # 嘗試 LLM 分析
    llm_analysis = ""
    llm_used = False
    if not _llm.cloud_blocked():
        client = _llm.get_client()
        if client:
            try:
                prompt = _build_llm_prompt(date_str, bot_summaries)
                llm_analysis = _llm.complete(
                    client,
                    [{"role": "user", "content": prompt}],
                    max_tokens=1200,
                    temperature=0.6,
                )
                llm_used = True
            except Exception as e:
                llm_analysis = f"（LLM 分析失敗：{_llm.friendly_err(e)}）"

    # 組成 Markdown 報告
    total_pnl = sum(s["pnl"] for s in bot_summaries)
    md_lines = [
        f"# 每日交易檢討：{date_str}",
        "",
        f"**合計 P&L**：${total_pnl:.0f}　**Bot 數**：{len(bot_summaries)}",
        "",
        "## Bot 摘要",
        "",
    ]
    for s in bot_summaries:
        md_lines.append(
            f"### {s['bot_name']}（{s['strategy']} / {s['symbol']}）"
        )
        md_lines.append(f"- 回合數：{s['round_trips']}，P&L：${s['pnl']:.0f}")
        if s["exit_kinds"]:
            kinds_str = "、".join(f"{k}×{v}" for k, v in s["exit_kinds"].items())
            md_lines.append(f"- 出場類型：{kinds_str}")
        if s["thesis_breaches"]:
            md_lines.append("- 失效假設：")
            for tb in s["thesis_breaches"]:
                md_lines.append(f"  - {tb}")
        md_lines.append("")

    if llm_analysis:
        md_lines += ["## AI 分析", "", llm_analysis, ""]
    else:
        md_lines += ["## AI 分析", "", "（LLM 未啟動或不可用，跳過分析）", ""]

    md_lines.append(f"*產生時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    report_content = "\n".join(md_lines)

    # 寫到 explorations/
    file_written = _write_review_file(date_str, report_content)

    # 通知摘要
    summary_snippet = (
        f"📊 [{date_str}] 交易檢討：{len(bot_summaries)} 個 Bot，合計 P&L ${total_pnl:.0f}\n"
        + (llm_analysis[:200] + "…" if len(llm_analysis) > 200 else llm_analysis)
        if llm_analysis else
        f"📊 [{date_str}] 交易檢討：{len(bot_summaries)} 個 Bot，合計 P&L ${total_pnl:.0f}（無 LLM 分析）"
    )
    try:
        notify(summary_snippet)
    except Exception:
        pass  # 推播失敗不阻塞

    return {
        "date": date_str,
        "bots_reviewed": len(bot_summaries),
        "file_written": file_written,
        "llm_used": llm_used,
        "summary_snippet": summary_snippet[:300],
        "bot_summaries": bot_summaries,
    }


def run_daily_review_scheduled() -> dict:
    """
    排程入口：自動取昨天日期，建立並關閉自己的 DB session。
    APScheduler / catchup 呼叫此版本。
    """
    from backend.database import SessionLocal

    yesterday = (_date.today() - timedelta(days=1)).isoformat()
    db = SessionLocal()
    try:
        return run_daily_review(yesterday, db)
    finally:
        db.close()
