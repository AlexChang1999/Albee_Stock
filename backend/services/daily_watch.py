"""
每日領導股回測紀錄（daily leader backtest）
=============================================
每天對一批「主要領導股」（上市、有歷史 K 線可回測，如 AAPL / NVDA）各跑一輪
全自動掃描（optimizer.run_auto_backtest：所有策略 × 參數網格、**依樣本外 OOS EV 排名**），
把每檔的全場冠軍存成一筆 BacktestRun——日積月累就是「各領導股最佳策略 EV 的時間序列」，
回測歷史頁 / 思考助手都讀得到。

邊界：
- **只落紀錄、不下單、不建 Bot、不晉升**：要上線仍走既有流程（automation / 董事會核准）。
- is_good 一律 False：每日例行紀錄不自動進「好策略」榜，避免灌爆人工策展的榜單。
- 未上市公司（SpaceX 等）沒有 K 線、回不了測——那是 collector 關鍵字監控的事，不在本檔。

排程：bot_manager.schedule_leader_backtest 每日 LEADER_BACKTEST_HOUR 跑；
開機補跑（catchup）也涵蓋本 job，電腦晚開機當天照補。
"""

from backend.config import settings
from backend.database import SessionLocal
from backend.models import BacktestRun
from backend.services.screener import parse_watchlist


def run_leader_backtest(db=None) -> dict:
    """
    跑一輪：對 LEADER_BACKTEST_SYMBOLS 每檔做全自動掃描，存各檔冠軍為 BacktestRun。

    - 單檔失敗（抓不到資料、斷網）不擋其他檔。
    - **全數失敗會拋例外**：讓 catchup/排程不落「成功」紀錄，之後自然重試。
    - LEADER_BACKTEST_ENABLED=false → 直接 return（排程掛載處也有閘，這裡是雙保險）。

    :param db: 測試注入用 session；正式跑留 None（自開自關）。
    """
    if not settings.LEADER_BACKTEST_ENABLED:
        return {"skipped": "LEADER_BACKTEST_ENABLED=false"}

    from backend.services.optimizer import run_auto_backtest  # 延遲 import，避免啟動連鎖載入

    symbols = parse_watchlist(settings.LEADER_BACKTEST_SYMBOLS)
    if not symbols:
        return {"skipped": "LEADER_BACKTEST_SYMBOLS 留空"}

    # 批次「暖快取」：整批領導股的歷史一次補齊（1 次 HTTP），
    # 之後每檔 run_auto_backtest 內的單檔 get_bars_cached 全命中、0 次外部 API。
    from backend.services import bar_cache

    try:
        bar_cache.get_bars_cached_multi(
            symbols, days=settings.LEADER_BACKTEST_DAYS, source=settings.DATA_SOURCE
        )
    except Exception:
        pass  # 暖快取失敗無妨，下面照樣逐檔走單檔路徑

    own_session = db is None
    if own_session:
        db = SessionLocal()
    stored: list[str] = []
    failed: list[str] = []
    try:
        for symbol in symbols:
            try:
                scan = run_auto_backtest(symbol=symbol, days=settings.LEADER_BACKTEST_DAYS)
                champion = scan.get("best")
                if not champion:
                    failed.append(symbol)
                    continue
                db.add(BacktestRun(
                    preset_id=None,  # 例行掃描不綁方案
                    strategy_key=champion["strategy_key"],
                    params=champion["params"],
                    symbol=scan["symbol"],
                    period_days=scan["days"],
                    metrics=champion["metrics"],
                    is_good=False,  # 例行紀錄不自動進「好策略」榜
                ))
                db.commit()
                stored.append(symbol)
            except Exception:
                db.rollback()
                failed.append(symbol)

        if not stored and failed:
            # 全軍覆沒（多半是斷網/金鑰問題）→ 視為本輪失敗，不落成功紀錄、之後重試
            raise RuntimeError(f"領導股回測全數失敗：{failed}")
        return {"stored": stored, "failed": failed}
    finally:
        if own_session:
            db.close()
