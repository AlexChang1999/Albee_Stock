"""
常駐機會探勘（Phase 10 step-02）
=================================
把既有海選（screener）變成「盤中週期自動跑」，並把排名候選**持久化**進 opportunity 表，
名額滿時也不漏掉好策略。職責很窄：**只收集 + 排名 + 持久化 + 去抖提醒**，
**不**自動建 Bot、**不**自動上真錢（那是 step-06 人工核准的事）。

誠實守則（Phase 6 step-04）：候選的 EV / 勝率一律存**樣本外（OOS）**，提醒門檻也比對 OOS。

設計：
- screener_results_to_rows / upsert_opportunities 是純函式，好單元測試（不碰網路）。
- run_opportunity_scan 是排程實際呼叫的入口：先過「盤中」閘（重用 alpaca 的開市判斷），
  收盤就跳過、不空轉回測；只對「新發現且超過提醒門檻」的候選 notify 一次，發完翻 seen 去抖。
"""

from datetime import datetime

from backend.database import SessionLocal
from backend.models import Opportunity
from backend.services import screener, notifier
from backend.services.alpaca_client import alpaca_client
from backend.services.automation_config import get_config


def screener_results_to_rows(recommendations: list[dict]) -> list[dict]:
    """
    把 screener.screen_watchlist() 的 recommendations 轉成 opportunity 列欄位。

    純函式：只做欄位挑選 + 依 OOS EV 由高到低排序，不碰 DB / 網路。
    OOS 指標取自每筆的 metrics（screener 已存樣本外值）；缺值以 None 帶過。
    """
    rows = []
    for rec in recommendations or []:
        metrics = rec.get("metrics") or {}
        rows.append({
            "symbol": rec.get("symbol"),
            "strategy_key": rec.get("strategy_key"),
            "params": rec.get("params") or {},
            "oos_expected_value": metrics.get("oos_expected_value"),
            "oos_win_rate_pct": metrics.get("oos_win_rate_pct"),
            "sentiment": rec.get("sentiment"),
        })
    # 依 OOS EV 由高到低（None 視為最低，排最後）
    rows.sort(key=lambda r: (r["oos_expected_value"] is None, -(r["oos_expected_value"] or 0)))
    return rows


def upsert_opportunities(db, rows: list[dict]) -> dict:
    """
    把候選列 upsert 進 opportunity 表：同 (symbol, strategy_key) 視為同一個機會。

    - 已存在 → 更新 OOS 指標 / 參數 / 情緒 / scanned_at，**保留既有 status**
      （避免把已提醒過 seen 的候選又打回 new、重複洗提醒）。
    - 不存在 → 新增一列，status="new"（待 run_opportunity_scan 判斷是否提醒）。

    冪等：同一批 rows 連跑兩次，不會重複堆積（第二次全走更新）。
    :return: {"inserted": 新增數, "updated": 更新數}
    """
    inserted = updated = 0
    for row in rows:
        symbol = row.get("symbol")
        strategy_key = row.get("strategy_key")
        if not symbol or not strategy_key:
            continue  # 殘缺列略過
        existing = (
            db.query(Opportunity)
            .filter(Opportunity.symbol == symbol, Opportunity.strategy_key == strategy_key)
            .first()
        )
        if existing is None:
            db.add(Opportunity(
                symbol=symbol,
                strategy_key=strategy_key,
                params=row.get("params") or {},
                oos_expected_value=row.get("oos_expected_value"),
                oos_win_rate_pct=row.get("oos_win_rate_pct"),
                sentiment=row.get("sentiment"),
                scanned_at=datetime.now(),
                status="new",
            ))
            inserted += 1
        else:
            existing.params = row.get("params") or {}
            existing.oos_expected_value = row.get("oos_expected_value")
            existing.oos_win_rate_pct = row.get("oos_win_rate_pct")
            existing.sentiment = row.get("sentiment")
            existing.scanned_at = datetime.now()
            # status 不動（保留 seen/deployed/expired 的流轉結果）
            updated += 1
    db.commit()
    return {"inserted": inserted, "updated": updated}


def _market_open_best_effort() -> bool:
    """
    是否盤中？查不到開市狀態（離線 / 無金鑰）時 best-effort 回 True——
    不因「查不到」而漏收；只有「明確收盤（False）」才跳過。
    """
    try:
        return bool(alpaca_client.is_market_open())
    except Exception:
        return True


def run_opportunity_scan() -> None:
    """
    排程週期入口：盤中跑一輪海選、把候選 upsert 進機會清單，新候選超門檻則提醒一次。

    - 收盤（明確 is_market_open()==False）直接 return，不空轉昂貴回測。
    - 提醒門檻一律比對 OOS EV（automation_config.ev_threshold）；發過就翻 seen 去抖。
    - best-effort：任一步出錯不讓排程崩（log 由上層 APScheduler 處理）。
    """
    if not _market_open_best_effort():
        return  # 收盤跳過

    db = SessionLocal()
    try:
        result = screener.screen_watchlist()
        rows = screener_results_to_rows(result.get("recommendations", []))
        upsert_opportunities(db, rows)

        # 新發現且超過提醒門檻（OOS EV）的候選 → 提醒一次後翻 seen（去抖，不重複洗頻）
        threshold = get_config(db).ev_threshold
        fresh = (
            db.query(Opportunity)
            .filter(
                Opportunity.status == "new",
                Opportunity.oos_expected_value.isnot(None),
                Opportunity.oos_expected_value >= threshold,
            )
            .order_by(Opportunity.oos_expected_value.desc())
            .all()
        )
        if fresh:
            lines = "\n".join(
                f"・{o.symbol} {o.strategy_key} OOS EV={o.oos_expected_value}"
                for o in fresh[:10]
            )
            notifier.notify(f"🔎 探勘到 {len(fresh)} 個新機會（OOS EV ≥ {threshold}）：\n{lines}")
            for o in fresh:
                o.status = "seen"
            db.commit()
    finally:
        db.close()
