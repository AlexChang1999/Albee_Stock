"""
Bot 管理 API
============
跟「Bot」有關的所有路由都集中在這裡：
建立、列出、編輯、刪除、查績效，以及手動執行/啟動/停止排程。

這裡用 FastAPI 的 APIRouter（路由器）。可以把它想成「一疊路由的小包裹」，
最後在 main.py 用 app.include_router() 一次掛上去。

prefix="/bots" 代表這個檔案裡的路由路徑前面都會自動加上 /bots，
所以下面寫 "" 其實就是 /bots，"/{bot_id}" 就是 /bots/{bot_id}。
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import Bot, TradeLog, DecisionLog
from backend.bots.bot_manager import bot_manager, run_bot_once
from backend.routers.bars import _to_candles
from backend.services import market_data
from backend.services.indicator_overlays import compute_overlays
from backend.services.performance import compute_bot_stats
from backend.services.alpaca_client import alpaca_client

# tags=["Bots"] 只是讓 /docs 文件頁把這組 API 歸在「Bots」分類下，比較好找。
router = APIRouter(prefix="/bots", tags=["Bots"])


# ---------- 請求資料格式（Pydantic） ----------
class BotCreate(BaseModel):
    """建立或編輯 Bot 時要傳的資料。"""
    name: str
    strategy: str = "ma_crossover"
    symbol: str
    params: dict = {}
    trade_amount: float = 1000.0

    # ----- 風控欄位（Phase 4）-----
    # 三個百分比皆可不填（None = 不啟用該機制），用小數表示（0.10 = 10%）。
    take_profit_pct: float | None = None     # 固定止盈
    stop_loss_pct: float | None = None       # 固定止損
    trailing_stop_pct: float | None = None   # 追蹤止損
    check_interval_sec: int = 60             # 監測頻率（秒）


class RiskUpdate(BaseModel):
    """
    只更新風控水位線用（給圖表「拖曳水位線」即時連動後端）。

    三個欄位都「選填」：沒帶的欄位不動、帶了才改（用 exclude_unset 判斷）。
    這樣前端拖哪條線就只送那一個百分比，不必把整個 Bot 重送一次。
    """
    take_profit_pct: float | None = None
    stop_loss_pct: float | None = None
    trailing_stop_pct: float | None = None


# ---------- 內部小工具 ----------
def _avg_entry_price(symbol: str) -> float | None:
    """
    查某檔股票目前持倉的「進場均價」（給前端圖表畫進場線/止損線用）。

    刻意做成 best-effort：沒持倉、離線、或 Alpaca 出錯都回 None，
    絕不讓 /bots 清單因為一檔查價失敗就整個壞掉。
    """
    try:
        pos = alpaca_client.get_position(symbol)
        if pos is None:
            return None
        return float(pos.avg_entry_price)
    except Exception:
        return None


def _bot_stats(db: Session, bot_id: int) -> dict:
    """查出某個 Bot 的交易紀錄（由舊到新），算出績效指標。"""
    rows = (
        db.query(TradeLog)
        .filter(TradeLog.bot_id == bot_id)
        .order_by(TradeLog.created_at.asc())
        .all()
    )
    trades = [{"side": r.side, "qty": r.qty, "price": r.price} for r in rows]
    return compute_bot_stats(trades)


def _get_bot_or_404(db: Session, bot_id: int) -> Bot:
    """共用：查出 Bot，找不到就回 404，避免每個路由重複寫。"""
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="找不到這個 Bot")
    return bot


# ---------- 路由 ----------
@router.post("")
def create_bot(payload: BotCreate, db: Session = Depends(get_db)):
    """建立一個新的 Bot。"""
    bot = Bot(
        name=payload.name,
        strategy=payload.strategy,
        symbol=payload.symbol.upper(),
        params=payload.params,
        trade_amount=payload.trade_amount,
        take_profit_pct=payload.take_profit_pct,
        stop_loss_pct=payload.stop_loss_pct,
        trailing_stop_pct=payload.trailing_stop_pct,
        check_interval_sec=payload.check_interval_sec,
    )
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return {"id": bot.id, "name": bot.name, "symbol": bot.symbol}


@router.put("/{bot_id}")
def update_bot(bot_id: int, payload: BotCreate, db: Session = Depends(get_db)):
    """編輯一個既有的 Bot。"""
    bot = _get_bot_or_404(db, bot_id)
    bot.name = payload.name
    bot.strategy = payload.strategy
    bot.symbol = payload.symbol.upper()
    bot.params = payload.params
    bot.trade_amount = payload.trade_amount
    bot.take_profit_pct = payload.take_profit_pct
    bot.stop_loss_pct = payload.stop_loss_pct
    bot.trailing_stop_pct = payload.trailing_stop_pct
    bot.check_interval_sec = payload.check_interval_sec
    db.commit()
    db.refresh(bot)
    return {"id": bot.id, "name": bot.name, "symbol": bot.symbol}


@router.put("/{bot_id}/risk")
def update_bot_risk(bot_id: int, payload: RiskUpdate, db: Session = Depends(get_db)):
    """
    只更新風控百分比（止盈/止損/追蹤止損），給圖表「拖曳水位線」用。

    只改「有帶進來」的欄位（exclude_unset）；百分比若有值須落在 0~1（0% < x < 100%），
    防止拖過頭把止損設成負數或大於 1 的離譜值。帶 null 代表關閉該機制。
    """
    bot = _get_bot_or_404(db, bot_id)
    changes = payload.model_dump(exclude_unset=True)

    for field, value in changes.items():
        if value is not None and not (0 < value < 1):
            raise HTTPException(
                status_code=400,
                detail=f"{field} 必須介於 0 與 1 之間（例：0.05 = 5%），收到 {value}",
            )
        setattr(bot, field, value)

    db.commit()
    db.refresh(bot)
    return {
        "id": bot.id,
        "take_profit_pct": bot.take_profit_pct,
        "stop_loss_pct": bot.stop_loss_pct,
        "trailing_stop_pct": bot.trailing_stop_pct,
    }


@router.delete("/{bot_id}")
def delete_bot(bot_id: int, db: Session = Depends(get_db)):
    """刪除一個 Bot（會先停掉它的排程）。"""
    bot = _get_bot_or_404(db, bot_id)
    bot_manager.stop_bot(bot_id)  # 先停掉定時排程，避免刪了還在跑
    db.delete(bot)
    db.commit()
    return {"message": f"已刪除 Bot：{bot.name}"}


@router.get("")
def list_bots(db: Session = Depends(get_db)):
    """列出所有 Bot（含各自的績效指標）。"""
    bots = db.query(Bot).all()
    return [
        {
            "id": b.id,
            "name": b.name,
            "strategy": b.strategy,
            "symbol": b.symbol,
            "params": b.params,
            "trade_amount": b.trade_amount,
            "take_profit_pct": b.take_profit_pct,
            "stop_loss_pct": b.stop_loss_pct,
            "trailing_stop_pct": b.trailing_stop_pct,
            "check_interval_sec": b.check_interval_sec,
            "is_active": b.is_active,
            # 監聽狀態：持倉最高價（None=空手）、最後一次檢查時間（給前端顯示排程是否在動）
            "peak_price": b.peak_price,
            # 進場均價（來自 Alpaca 持倉，空手/離線為 None）：給前端圖表畫進場線/止損線用
            "avg_entry_price": _avg_entry_price(b.symbol),
            "last_checked_at": b.last_checked_at.isoformat() if b.last_checked_at else None,
            # 績效指標：依該 Bot 的真實交易紀錄計算（沒交易時各項為 0）
            "stats": _bot_stats(db, b.id),
        }
        for b in bots
    ]


@router.get("/{bot_id}/stats")
def get_bot_stats(bot_id: int, db: Session = Depends(get_db)):
    """單獨取得某個 Bot 的績效指標。"""
    _get_bot_or_404(db, bot_id)
    return _bot_stats(db, bot_id)


@router.post("/{bot_id}/run")
def run_bot_now(bot_id: int, db: Session = Depends(get_db)):
    """手動讓某個 Bot 立刻跑一次策略（測試用，休市時間也能跑）。"""
    bot = _get_bot_or_404(db, bot_id)
    # 手動執行多半是為了測試，略過開市檢查，休市時段也能驗證流程。
    # Phase 6 step-06：傳 bot.id（run_bot_once 內部會用 id 重查最新值）。
    run_bot_once(bot.id, ignore_market_hours=True)
    return {"message": f"Bot {bot.name} 已執行一次"}


@router.get("/decisions/recent")
def get_recent_decisions(limit: int = 30, db: Session = Depends(get_db)):
    """
    取得「跨所有 Bot」的最近決策紀錄，依時間倒序、預設 30 筆。

    給 Dashboard 的「決策即時流」開頁播種用（之後靠 WebSocket 即時追加）。
    注意：這條路由必須宣告在 /{bot_id}/decisions 之前，否則 "decisions"
    會被當成 bot_id 吃掉而 422。
    """
    rows = (
        db.query(DecisionLog, Bot.name)
        .outerjoin(Bot, Bot.id == DecisionLog.bot_id)
        .order_by(DecisionLog.created_at.desc(), DecisionLog.id.desc())
        .limit(max(1, min(limit, 200)))  # 夾在 1~200，防一次撈爆
        .all()
    )
    return [
        {
            "id": r.id,
            "bot_id": r.bot_id,
            "bot_name": bot_name or f"Bot #{r.bot_id}",
            "symbol": r.symbol,
            "signal": r.signal,
            "reason": r.reason,
            "price": r.price,
            "action": r.action,
            "exit_kind": r.exit_kind,          # 賣出細分（止損/停利/追蹤/反轉/券商）
            "thesis_breach": r.thesis_breach,  # 賣出時哪個買入假設失效（給即時流呈現）
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r, bot_name in rows
    ]


@router.get("/{bot_id}/decisions")
def get_bot_decisions(bot_id: int, limit: int = 50, db: Session = Depends(get_db)):
    """
    取得某個 Bot 最近的決策審計紀錄（Phase 6 step-08），依時間倒序、預設 50 筆。

    這條軌跡回答「為何在某時點買 / 賣 / 不動」——含「沒成交但有決策」的時點
    （觀望 / 續抱 / 休市跳過 / 購買力不足 / 熔斷），是自動跑真錢時的事後查驗依據。
    """
    _get_bot_or_404(db, bot_id)
    rows = (
        db.query(DecisionLog)
        .filter(DecisionLog.bot_id == bot_id)
        .order_by(DecisionLog.created_at.desc(), DecisionLog.id.desc())
        .limit(max(1, min(limit, 500)))  # 夾在 1~500，防一次撈爆
        .all()
    )
    return [
        {
            "id": r.id,
            "symbol": r.symbol,
            "signal": r.signal,
            "reason": r.reason,
            "price": r.price,
            "volume": r.volume,          # 決策當下那根 K 的成交量（量）
            "qty": r.qty,                # 實際下單股數（觀望/跳過為 None）
            "indicators": r.indicators,  # 該策略當下指標快照（dict 或 None）
            "action": r.action,
            # ----- 結構化交易日誌擴充欄位 -----
            "strategy": r.strategy,              # 觸發策略代號（自適應記實際挑中的）
            "total_amount": r.total_amount,      # 成交總額 = 價 × 股數
            "target_price": r.target_price,      # 預期獲利點
            "stop_price": r.stop_price,          # 預計停損點
            "market_snapshot": r.market_snapshot,  # 均線位置 + 量能快照（dict 或 None）
            "position_after": r.position_after,    # 交易後庫存（dict 或 None）
            "exit_kind": r.exit_kind,            # 賣出細分（止損/停利/追蹤/反轉/券商）
            "thesis_breach": r.thesis_breach,    # 賣出時哪個買入假設失效
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/{bot_id}/chart-data")
def get_bot_chart_data(bot_id: int, days: int = 120, db: Session = Depends(get_db)):
    """
    一次回傳「策略視角圖表」所需的全部資料（Stage 4 策略可視化）：

    - candles：日 K 線（與 /bars 同格式，走統一資料路徑 market_data + DATA_SOURCE）
    - overlays / pane：該 Bot 策略「看的指標」序列（主圖疊線 / 振盪器副圖）
    - markers：真實成交點（TradeLog ▲▼）+ 決策觀望點（DecisionLog，前端可開關）

    candles 與指標用**同一份 df** 計算，保證時間軸對齊。
    """
    bot = _get_bot_or_404(db, bot_id)
    try:
        df = market_data.get_bars(bot.symbol, days=days, source=settings.DATA_SOURCE)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"取得 K 線失敗：{e}")

    indicator = compute_overlays(bot.strategy, bot.params or {}, df)

    # 成交標記：該 Bot 的所有真實成交（時間取日期字串，對齊日 K 的 time 格式）
    markers = []
    trades = (
        db.query(TradeLog)
        .filter(TradeLog.bot_id == bot_id)
        .order_by(TradeLog.created_at.asc())
        .all()
    )
    for t in trades:
        if not t.created_at:
            continue
        markers.append({
            "time": t.created_at.strftime("%Y-%m-%d"),
            "kind": "trade",
            "side": t.side,
            "price": t.price,
            "text": f"{'買' if t.side == 'buy' else '賣'} {t.qty} 股 @ ${t.price:.2f}" if t.price else "",
        })

    # 決策觀望點（沒成交但有決策的時點；前端預設關、可開關顯示）
    decisions = (
        db.query(DecisionLog)
        .filter(DecisionLog.bot_id == bot_id, DecisionLog.action == "hold")
        .order_by(DecisionLog.created_at.desc())
        .limit(200)
        .all()
    )
    for d in decisions:
        if not d.created_at:
            continue
        markers.append({
            "time": d.created_at.strftime("%Y-%m-%d"),
            "kind": "decision",
            "action": d.action,
            "reason": d.reason or "",
        })

    return {
        "symbol": bot.symbol,
        "strategy": bot.strategy,
        "candles": _to_candles(df),
        "overlays": indicator["overlays"],
        "pane": indicator["pane"],
        "markers": markers,
    }


@router.post("/{bot_id}/start")
def start_bot(bot_id: int, interval: int | None = None, db: Session = Depends(get_db)):
    """
    啟動 Bot 的定時執行。

    沒帶 interval 時用 Bot 自己設定的 check_interval_sec（預設 60 秒）；
    帶了 interval（查詢參數）則臨時覆寫，方便測試不同頻率。
    """
    bot = _get_bot_or_404(db, bot_id)
    bot.is_active = True
    db.commit()
    seconds = interval if interval is not None else (bot.check_interval_sec or 60)
    bot_manager.start_bot(bot, interval_seconds=seconds)
    return {"message": f"Bot {bot.name} 已啟動（每 {seconds} 秒檢查一次）"}


@router.post("/{bot_id}/stop")
def stop_bot(bot_id: int, db: Session = Depends(get_db)):
    """停止 Bot 的定時執行。"""
    bot = _get_bot_or_404(db, bot_id)
    bot.is_active = False
    db.commit()
    bot_manager.stop_bot(bot_id)
    return {"message": f"Bot {bot.name} 已停止"}


@router.get("/daily-digest")
def daily_digest(date: str | None = None, db: Session = Depends(get_db)):
    """
    每日交易摘要（快速查詢「昨天到底發生什麼」）。

    讀取 DecisionLog + TradeLog，按 Bot 分組計算 round-trip P&L 與出場分析。
    date 格式 YYYY-MM-DD，省略 = 昨天。不觸發 LLM（純資料查詢）。
    需要 AI 分析版本請用 POST /review/daily。
    """
    from datetime import date as _date, timedelta, datetime as _dt
    from collections import defaultdict
    from backend.services.performance import compute_round_trip_returns

    target_str = date or (_date.today() - timedelta(days=1)).isoformat()
    try:
        target_dt = _dt.strptime(target_str, "%Y-%m-%d")
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"日期格式錯誤：{target_str}，應為 YYYY-MM-DD")

    day_start = target_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = target_dt.replace(hour=23, minute=59, second=59, microsecond=999999)

    # 抓當日所有決策
    all_decisions = (
        db.query(DecisionLog)
        .filter(
            DecisionLog.created_at >= day_start,
            DecisionLog.created_at <= day_end,
        )
        .order_by(DecisionLog.bot_id, DecisionLog.created_at.asc())
        .all()
    )

    # 抓當日成交
    all_trades = (
        db.query(TradeLog)
        .filter(
            TradeLog.created_at >= day_start,
            TradeLog.created_at <= day_end,
        )
        .order_by(TradeLog.bot_id, TradeLog.created_at.asc())
        .all()
    )

    # 按 bot_id 分組
    by_bot_dec: dict = defaultdict(list)
    for d in all_decisions:
        by_bot_dec[d.bot_id].append(d)

    by_bot_trade: dict = defaultdict(list)
    for t in all_trades:
        by_bot_trade[t.bot_id].append(t)

    all_bot_ids = set(by_bot_dec.keys()) | set(by_bot_trade.keys())
    bots_map = {b.id: b for b in db.query(Bot).filter(Bot.id.in_(all_bot_ids)).all()} if all_bot_ids else {}

    result_bots = []
    total_pnl = 0.0
    for bot_id in sorted(all_bot_ids):
        b = bots_map.get(bot_id)
        decisions = by_bot_dec[bot_id]
        trades = by_bot_trade[bot_id]

        trade_dicts = [{"side": t.side, "qty": t.qty, "price": t.price,
                        "created_at": t.created_at} for t in trades]
        rts = compute_round_trip_returns(trade_dicts)
        pnl = sum(r["profit"] for r in rts)
        total_pnl += pnl

        exit_kinds: dict = defaultdict(int)
        thesis_breaches = []
        for d in decisions:
            if d.action == "sold":
                if d.exit_kind:
                    exit_kinds[d.exit_kind] += 1
                if d.thesis_breach:
                    thesis_breaches.append({
                        "breach": d.thesis_breach,
                        "price": d.price,
                        "time": d.created_at.isoformat() if d.created_at else None,
                    })

        result_bots.append({
            "bot_id": bot_id,
            "bot_name": b.name if b else f"Bot#{bot_id}",
            "strategy": b.strategy if b else "unknown",
            "symbol": b.symbol if b else "unknown",
            "decisions_count": len(decisions),
            "round_trips": len(rts),
            "pnl": round(pnl, 2),
            "exit_kinds": dict(exit_kinds),
            "thesis_breaches": thesis_breaches,
        })

    return {
        "date": target_str,
        "total_pnl": round(total_pnl, 2),
        "bots_count": len(result_bots),
        "bots": result_bots,
    }
