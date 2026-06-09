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

from datetime import datetime, timedelta

from backend.config import settings
from backend.database import SessionLocal
from backend.models import Opportunity, FactorSnapshot
from backend.services import screener, notifier, market_data, regime_features, regime
from backend.services.alpaca_client import alpaca_client
from backend.services.automation_config import get_config

# 因子的 7 個鍵（與 regime_features.compute_features / FactorSnapshot 欄位同名）
_FACTOR_KEYS = (
    "volume_ratio",
    "return_5d",
    "return_20d",
    "volatility_20d",
    "trend_strength",
    "atr_pct",
    "range_position",
)


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


def features_to_snapshot_row(symbol: str, features: dict, regime_label: str, as_of: datetime) -> dict:
    """
    把 compute_features 的結果 + regime 標籤組成 FactorSnapshot 的欄位 dict。純函式、好單測。

    只挑 7 個已知因子鍵（缺值帶 None），不重算、不自創公式——因子的真實來源是
    regime_features.compute_features。
    """
    row = {"symbol": symbol, "as_of": as_of, "regime": regime_label}
    for key in _FACTOR_KEYS:
        row[key] = features.get(key)
    return row


def collect_factor_snapshots(db, *, as_of: datetime | None = None) -> int:
    """
    對 watchlist 每檔抓 K 線、算因子、落一筆 FactorSnapshot（Phase 10 step-03）。

    - 走**同一條正規資料路徑** market_data.get_bars(..., source=settings.DATA_SOURCE)，
      無 look-ahead（compute_features 只用截至最後一根的資料）。
    - 因子是觀測佐證、不是交易訊號——這裡只「落表」，不下單、不建 Bot。
    - best-effort：單檔抓失敗不影響其他檔。
    - 落表後依 settings.FACTOR_RETENTION_DAYS 修剪過舊快照（0=不修剪）。
    :return: 這輪寫入的筆數。
    """
    as_of = as_of or datetime.now()
    symbols = screener.parse_watchlist(settings.SCREENER_WATCHLIST)
    written = 0
    for sym in symbols:
        try:
            df = market_data.get_bars(sym, days=60, source=settings.DATA_SOURCE)
        except Exception:
            continue  # 單檔抓失敗略過
        features = regime_features.compute_features(df)
        regime_label = regime.classify_regime(features)
        row = features_to_snapshot_row(sym, features, regime_label, as_of)
        db.add(FactorSnapshot(**row))
        written += 1
    db.commit()
    _prune_factor_snapshots(db, as_of=as_of)
    return written


def _prune_factor_snapshots(db, *, as_of: datetime) -> int:
    """修剪超過保留天數的舊因子快照，避免 DB 無上限膨脹（0=不修剪）。回傳刪除筆數。"""
    days = settings.FACTOR_RETENTION_DAYS
    if not days or days <= 0:
        return 0
    cutoff = as_of - timedelta(days=days)
    deleted = (
        db.query(FactorSnapshot)
        .filter(FactorSnapshot.as_of < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


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

        # 順手把 watchlist 各檔的市場狀態因子落表（蒐集員主管的報表，step-03）。
        # best-effort：因子落表失敗不影響機會清單收集與提醒。
        try:
            collect_factor_snapshots(db)
        except Exception:
            pass

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
