"""
Bot 管理器
==========
負責「執行」與「排程」Bot。

一個 Bot 的執行流程（run_bot_once）：
1. 用 bot_id 重查最新的 Bot（Phase 6 step-06：每輪重查，改設定立即生效）
2. 抓該標的的歷史 K 線資料
3. 丟給策略，產生訊號（buy / sell / hold）
4. 依訊號決定動作：
   - buy ：若目前沒持倉 → 先過組合層守門（熔斷 → 購買力）才買進
   - sell：若目前有持倉 → 全部賣出
   - hold：什麼都不做
5. 每個分支都寫一筆決策審計（Phase 6 step-08）；真成交才另記 TradeLog 並發通知

排程的部分用 APScheduler：每個啟用的 Bot 會定時（預設每 60 秒）跑一次。
注意：實際抓資料/下單需要有效的 Alpaca 金鑰才會成功。

Phase 6 設計重點：
- step-06：排程只記 bot.id，run_bot_once 開頭用 id 重查，讀到的永遠是最新風控/參數。
- step-05：空手買進前 best-effort 查購買力，不夠就跳過並記審計。
- step-08：休市 / 觀望 / 續抱 / 跳過 / 成交各分支都留決策紀錄。
- step-09：空手買進前先過組合回撤熔斷，熔斷時只擋進、不擋出。
"""

import math
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from backend.config import settings
from backend.database import SessionLocal
from backend.models import Bot, TradeLog, DecisionLog
from backend.models.decision_log import (
    ACTION_BOUGHT,
    ACTION_SOLD,
    ACTION_HOLD,
    ACTION_SKIPPED_MARKET_CLOSED,
    ACTION_SKIPPED_NO_BUYING_POWER,
    ACTION_SKIPPED_CIRCUIT_BREAKER,
)
from backend.services import market_data
from backend.services.alpaca_client import alpaca_client
from backend.services.bot_activity import emit as emit_activity, safe_float
from backend.services.circuit_breaker import check_breaker
from backend.services.notifier import notify
from backend.services.protective_orders import (
    order_matches_plan,
    plan_protective_order,
    whole_share_qty,
)
from backend.services.decision_context import (
    build_thesis_breach,
    classify_exit_kind,
    compute_market_snapshot,
)
from backend.services.indicator_overlays import compute_overlays
from backend.services.risk_manager import check_exit
from backend.strategies import get_strategy, Signal
from backend.strategies.lookback import required_lookback_days


def _bar_volume(df) -> float | None:
    """決策當下那根 K 的成交量（量）。無 volume 欄 / NaN / 空 df → None。"""
    try:
        if df is None or df.empty or "volume" not in df.columns:
            return None
        v = float(df["volume"].iloc[-1])
        return None if math.isnan(v) else v
    except Exception:
        return None


def _indicator_snapshot(strategy_name: str, params: dict, df) -> dict | None:
    """該策略「看的指標」當下值快照：取 compute_overlays 各序列最後一根。

    與策略圖表同一套公式（services.indicator_overlays），故畫面看到的指標線末端值
    ＝這裡記下的數字。算不出 / 無資料 → None（不擋交易主流程）。
    """
    try:
        ov = compute_overlays(strategy_name, params or {}, df)
    except Exception:
        return None

    def _last(data):
        # compute_overlays 的 _points 已濾掉 NaN，故末筆即最後一個有效值
        return float(data[-1]["value"]) if data else None

    snap: dict = {}
    for s in ov.get("overlays") or []:
        v = _last(s.get("data") or [])
        if v is not None:
            snap[s["id"]] = v
    pane = ov.get("pane")
    if pane:
        for s in pane.get("series") or []:
            v = _last(s.get("data") or [])
            if v is not None:
                snap[s["id"]] = v
    return snap or None


# 追蹤止損要記住「持倉期間出現過的最高價」。
# 改存資料庫欄位 bot.peak_price（取代舊版記憶體 dict）：後端重啟後最高價仍在，
# 追蹤止損不會被重置、保護不中斷。None = 空手或尚未進場。
def _persist_peak(bot: Bot, peak: float | None) -> None:
    """把某 Bot 的「持倉最高價」寫回資料庫（peak=None 代表清除）。

    注意：這裡用 bot.id 重新查一筆最新的來更新，避免 session 過期問題。
    查不到（例如測試用的假物件）就靜默跳過。
    """
    db = SessionLocal()
    try:
        row = db.query(Bot).filter(Bot.id == bot.id).first()
        if row is not None:
            row.peak_price = peak
            db.commit()
    finally:
        db.close()
    # 同步更新手上這顆物件，讓同一輪後續邏輯讀到新值
    bot.peak_price = peak


def _persist_protective_order_id(bot: Bot, order_id: str | None) -> None:
    """把某 Bot 的「券商端保護單 id」寫回資料庫（None 代表清除）。

    與 _persist_peak 同款：用 bot.id 重查最新列更新、查不到靜默跳過，
    並同步更新手上物件讓同一輪後續邏輯讀到新值。
    """
    db = SessionLocal()
    try:
        row = db.query(Bot).filter(Bot.id == bot.id).first()
        if row is not None:
            row.protective_order_id = order_id
            db.commit()
    finally:
        db.close()
    bot.protective_order_id = order_id


# 券商端訂單「還活著（未成交、掛著）」的狀態集合。
# Alpaca 的訂單狀態是字串列舉，這幾種代表單還掛在券商端等觸發。
_OPEN_ORDER_STATUSES = {"new", "accepted", "held", "pending_new", "accepted_for_bidding"}


def _order_status(order) -> str:
    """把 Alpaca 訂單物件的 status（列舉或字串）統一轉成小寫字串。"""
    status = getattr(order, "status", "")
    return str(getattr(status, "value", status)).lower()


def _place_protective_order(bot: Bot, qty: float, entry_price: float) -> None:
    """進場成交後，把止損「託管」到券商端（維運安全軌 H1）。

    依 Bot 風控設定掛 GTC 保護賣單（trailing 優先，否則 stop），
    訂單 id 持久化到 bot.protective_order_id。
    掛失敗**不擋主流程**（本機輪詢仍是備援），但發通知警告 + 交給下一輪自癒補掛。
    """
    if not settings.BROKER_STOP_ENABLED:
        return
    plan = plan_protective_order(
        entry_price,
        stop_loss_pct=bot.stop_loss_pct,
        trailing_stop_pct=bot.trailing_stop_pct,
    )
    if plan is None:
        return  # 沒設止損/追蹤止損 → 不掛（止盈 v1 仍走本機輪詢）
    try:
        if plan["type"] == "trailing_stop":
            order = alpaca_client.submit_trailing_stop_order(
                bot.symbol, qty, trail_percent=plan["trail_percent"]
            )
        else:
            order = alpaca_client.submit_stop_order(
                bot.symbol, qty, stop_price=plan["stop_price"]
            )
        _persist_protective_order_id(bot, str(getattr(order, "id", "")) or None)
    except Exception as e:
        # 保護單沒掛上 ≠ 交易失敗：本機輪詢照常守著，下一輪 _ensure 會再補掛
        notify(f"⚠️ [{bot.name}] 券商端保護單掛單失敗（{e}），暫由本機輪詢守備，下一輪自動補掛。")


def _ensure_protective_order(bot: Bot, position) -> None:
    """每輪自癒（reconcile）：有持倉 + 有風控設定 → 券商端保護單必須活著且參數正確。

    涵蓋：後端重啟（DB 記得 id）、保護單被手動撤掉、掛單曾失敗、
    使用者改了止損百分比（撤舊掛新）。整段 best-effort：任何查詢失敗不阻斷主流程
    （本機輪詢備援仍在）。
    """
    if not settings.BROKER_STOP_ENABLED:
        return
    try:
        entry_price = float(position.avg_entry_price)
        plan = plan_protective_order(
            entry_price,
            stop_loss_pct=bot.stop_loss_pct,
            trailing_stop_pct=bot.trailing_stop_pct,
        )
        if plan is None:
            # 風控設定被拿掉 → 不需要保護單；還掛著就撤
            if bot.protective_order_id:
                alpaca_client.cancel_order(bot.protective_order_id)
                _persist_protective_order_id(bot, None)
            return

        if bot.protective_order_id:
            order = alpaca_client.get_order(bot.protective_order_id)
            if (
                order is not None
                and _order_status(order) in _OPEN_ORDER_STATUSES
                and order_matches_plan(
                    str(getattr(getattr(order, "order_type", None), "value", getattr(order, "order_type", ""))).lower(),
                    float(order.stop_price) if getattr(order, "stop_price", None) else None,
                    float(order.trail_percent) if getattr(order, "trail_percent", None) else None,
                    plan,
                )
            ):
                return  # 單活著且符合計畫 → 不動
            # 單不見了 / 參數漂移 → 撤舊（best-effort）再補掛
            alpaca_client.cancel_order(bot.protective_order_id)
            _persist_protective_order_id(bot, None)

        # 補掛：股數用「目前實際持倉」取整（保護單只支援整股；舊碎股倉位的零頭不掛）
        qty = int(float(position.qty))
        if qty > 0:
            _place_protective_order(bot, qty, entry_price)
    except Exception:
        pass  # 自癒失敗不阻斷：本機輪詢照常守備，下一輪再試


def _cancel_protective_order(bot: Bot) -> bool:
    """本機要出場（風控/策略賣出）前，先撤掉券商端保護單。

    券商端掛著 sell stop 時股數被保留，不先撤、本機市價賣單會被 Alpaca 拒絕。
    :return: True = 已撤掉（或本來就沒掛），可以繼續本機賣出；
             False = 撤不掉（多半是券商端剛好已成交）→ 呼叫端放棄本機賣出，
             下一輪由 _settle_broker_exit 回填帳。
    """
    if not bot.protective_order_id:
        return True
    if alpaca_client.cancel_order(bot.protective_order_id):
        _persist_protective_order_id(bot, None)
        return True
    return False


def _settle_broker_exit(bot: Bot) -> bool:
    """券商端保護單成交的「回填帳」：空手但 DB 記著保護單 id → 查單補記錄。

    券商端止損觸發時本機不在場，TradeLog / DecisionLog 都沒記——
    不回填的話績效統計（round-trip 配對）與 tracking error 對帳的資料源就是錯的。
    :return: True = 這輪確認券商端已出場並補完帳。
    """
    order_id = bot.protective_order_id
    if not order_id:
        return False
    try:
        order = alpaca_client.get_order(order_id)
        if order is not None and _order_status(order) == "filled":
            qty = float(getattr(order, "filled_qty", 0) or 0)
            price = float(getattr(order, "filled_avg_price", 0) or 0)
            reason = "券商端止損/追蹤止損觸發（託管單成交，本機回填）"
            _record_and_notify(bot, "sell", qty, price, order, reason)
            exit_kind = classify_exit_kind(reason)
            thesis = build_thesis_breach(_recent_buy_log(bot.id), price, exit_kind)
            _record_decision(bot, Signal.SELL, reason, price, ACTION_SOLD, qty=qty,
                             exit_kind=exit_kind, thesis_breach=thesis,
                             total_amount=qty * price, position_after=_position_after(bot))
            _persist_peak(bot, None)
            _persist_protective_order_id(bot, None)
            return True
        # 沒成交卻空手（撤單/過期/人工平倉）：保護單已無意義，撤掉 + 清 id
        alpaca_client.cancel_order(order_id)
        _persist_protective_order_id(bot, None)
    except Exception:
        pass  # 查不到先不動，下一輪再試（best-effort）
    return False


def _mark_checked(bot: Bot) -> None:
    """記錄這個 Bot「最後一次成功跑完檢查」的時間，給前端顯示排程是否在動。"""
    now = datetime.now()
    db = SessionLocal()
    try:
        row = db.query(Bot).filter(Bot.id == bot.id).first()
        if row is not None:
            row.last_checked_at = now
            db.commit()
    finally:
        db.close()
    bot.last_checked_at = now


def _record_decision(
    bot, signal: str, reason: str, price, action: str,
    volume=None, qty=None, indicators=None,
    *, strategy=None, market_snapshot=None, position_after=None,
    total_amount=None, target_price=None, stop_price=None,
    exit_kind=None, thesis_breach=None,
) -> None:
    """寫一筆決策審計（Phase 6 step-08；Phase 15 加 量/股數/指標快照；結構化交易日誌擴充）。

    連「沒成交但有決策」的時點都記（觀望 / 續抱 / 休市 / 購買力不足 / 熔斷），
    讓自動跑真錢的系統可事後查驗每個決定，也是「讀教訓」的素材。寫入失敗不可影響
    交易主流程，故吞例外。
    - volume：決策當下那根 K 的成交量（量）；風控出場/休市等無 df 的時點為 None。
    - qty：實際下單股數（買/賣才有；觀望/跳過為 None）。
    - indicators：該策略當下指標快照（dict）；無資料時 None。
    結構化日誌欄位（keyword-only，全可省；見 models/decision_log.py 欄位註解）：
    - strategy：觸發策略代號（不傳則用 bot.strategy；自適應模式由呼叫端傳實際挑中的）。
    - market_snapshot：均線位置 + 量能快照（compute_market_snapshot）。
    - position_after：交易後庫存（best-effort）。total_amount：成交總額。
    - target_price / stop_price：買進算出的停利 / 停損價（風控出場填觸發的那條）。
    - exit_kind：賣出細分（EXIT_KIND_*）。thesis_breach：賣出時哪個買入假設失效。
    """
    strategy = strategy or getattr(bot, "strategy", None)
    # 這裡是所有決策分支的單一漏斗 → 順手發即時事件給前端可視化（fire-and-forget）。
    # 即時流只帶最有呈現價值的出場脈絡（exit_kind / thesis_breach）；完整快照存 DB。
    emit_activity(
        bot, "decision", reason,
        decision={
            "signal": signal,
            "action": action,
            "reason": reason,
            "price": safe_float(price),
            "volume": safe_float(volume),
            "qty": safe_float(qty),
            "indicators": indicators,
            "exit_kind": exit_kind,
            "thesis_breach": thesis_breach,
        },
    )
    db = SessionLocal()
    try:
        db.add(DecisionLog(
            bot_id=bot.id,
            symbol=bot.symbol,
            signal=signal,
            reason=reason,
            price=price,
            volume=volume,
            qty=qty,
            indicators=indicators,
            action=action,
            strategy=strategy,
            market_snapshot=market_snapshot,
            position_after=position_after,
            total_amount=total_amount,
            target_price=target_price,
            stop_price=stop_price,
            exit_kind=exit_kind,
            thesis_breach=thesis_breach,
        ))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _available_buying_power() -> float | None:
    """best-effort 查帳戶可用購買力。離線 / 無金鑰 / 出錯 → None（呼叫端放行，不阻斷）。"""
    try:
        acct = alpaca_client.get_account()
        return float(acct.buying_power)
    except Exception:
        return None


def _position_after(bot) -> dict | None:
    """交易後庫存狀態（best-effort）：{shares: 交易後持股, buying_power: 剩餘購買力}。

    查不到帳戶/持倉（離線、無金鑰、出錯）回 None，不阻斷交易主流程。
    註：剛成交時券商端可能尚未即時結算，數字為當下查得的近似值（夠用於事後回顧）。
    """
    try:
        pos = alpaca_client.get_position(bot.symbol)
        shares = float(pos.qty) if pos is not None else 0.0
    except Exception:
        shares = None
    bp = _available_buying_power()
    if shares is None and bp is None:
        return None
    return {"shares": shares, "buying_power": bp}


def _recent_buy_log(bot_id: int) -> dict | None:
    """撈該 Bot 最近一筆『買進』的決策紀錄，給賣出回填「哪個買入假設失效」用。

    回精簡 dict（price / target_price / stop_price / created_at），在 session 內就取完值，
    避免關閉後 detached 取值問題。查無對應買進紀錄 / 出錯 → None。
    """
    db = SessionLocal()
    try:
        row = (
            db.query(DecisionLog)
            .filter(DecisionLog.bot_id == bot_id, DecisionLog.action == ACTION_BOUGHT)
            .order_by(DecisionLog.created_at.desc(), DecisionLog.id.desc())
            .first()
        )
        if row is None:
            return None
        return {
            "price": row.price,
            "target_price": row.target_price,
            "stop_price": row.stop_price,
            "created_at": row.created_at,
        }
    except Exception:
        return None
    finally:
        db.close()


def run_bot_once(bot_id: int, ignore_market_hours: bool = False) -> None:
    """
    執行單一 Bot 一次完整循環。

    Phase 6 step-06：參數改收 bot_id（整數）而非 ORM 物件。函式開頭用 id 重查最新的 Bot，
    這樣使用者改了風控 / 參數（例如拖曳水位線），執行中的排程下一輪就生效，不必重啟後端。

    :param bot_id: 要執行的 Bot 的資料庫 id。
    :param ignore_market_hours: 是否略過「開市才執行」的檢查。
        排程自動跑時用預設 False（休市就跳過，省 API、避免怪單）；
        手動測試（/run）時傳 True，方便休市時間也能驗證風控邏輯。

    流程（持倉與否走不同分支）：
    - 持倉中：先跑風控（止損/追蹤止損/止盈），任一觸發就平倉；
              沒觸發才看策略要不要賣。
      → 重點：風控必須「不分策略訊號」都先檢查，所以不能像舊版那樣
        策略一觀望就提早 return，否則持倉時的止損會被跳過。
    - 空手中：跑策略，出現買進訊號 → 先過組合層守門（熔斷 / 購買力）才進場。
    """
    # --- 0. 用 id 重查最新的 Bot（step-06 核心）---
    db = SessionLocal()
    try:
        bot = db.query(Bot).filter(Bot.id == bot_id).first()
    finally:
        db.close()
    if bot is None:
        # Bot 已被刪除 → 移除殭屍排程，避免持續對著不存在的 Bot 報錯
        bot_manager.stop_bot(bot_id)
        return

    try:
        emit_activity(bot, "cycle_start", "醒來，開始這一輪檢查")

        # --- 1. 休市就跳過（手動執行可用 ignore_market_hours 略過此檢查）---
        if not ignore_market_hours and not alpaca_client.is_market_open():
            print(f"[{bot.name}] 美股休市中，本次跳過。")
            _record_decision(bot, Signal.HOLD, "美股休市中", None, ACTION_SKIPPED_MARKET_CLOSED)
            _mark_checked(bot)  # 有跑這一輪（只是休市沒動作），仍更新檢查時間
            _emit_cycle_end(bot, "skipped_market_closed")
            return

        # --- 2. 查目前持倉與現價 ---
        emit_activity(bot, "fetch_data", f"查詢 {bot.symbol} 持倉與現價")
        position = alpaca_client.get_position(bot.symbol)
        current_price = alpaca_client.get_latest_price(bot.symbol)

        # 空手但 DB 記著券商端保護單 id → 多半是託管止損在本機不在場時成交了，
        # 先回填交易/決策紀錄（維運安全軌 H1），再照常走空手分支。
        if position is None and bot.protective_order_id:
            _settle_broker_exit(bot)

        if position is not None:
            _handle_holding(bot, position, current_price)
        else:
            _handle_flat(bot, current_price)

        _mark_checked(bot)  # 這一輪成功跑完，記錄檢查時間
        _emit_cycle_end(bot, "ok")

    except Exception as e:
        # 單一 Bot 出錯不應影響其他 Bot，這裡接住並通知
        notify(f"[{bot.name}] 執行時發生錯誤：{e}")
        _emit_cycle_end(bot, "error", detail=str(e))


def _emit_cycle_end(bot, status: str, detail: str = "") -> None:
    """發「這一輪結束」事件：帶下一輪間隔秒數，前端據此倒數 + 偵測排程失聯。

    next_run_in_sec：Bot 啟用中才有值（排程會再來）；手動執行（/run）且未啟用
    時為 None，前端不倒數。getattr 防呆：測試假物件沒這些欄位也不炸。
    """
    is_active = bool(getattr(bot, "is_active", False))
    interval = getattr(bot, "check_interval_sec", None) or 60
    emit_activity(
        bot, "cycle_end", detail,
        status=status,
        next_run_in_sec=interval if is_active else None,
        is_active=is_active,
    )


def _handle_holding(bot: Bot, position, current_price: float) -> None:
    """持倉中：先風控出場，再看策略賣出訊號（熔斷不擋出場）。"""
    entry_price = float(position.avg_entry_price)

    # 券商端保護單自癒（維運安全軌 H1）：該掛的沒掛/參數漂移 → 補掛。best-effort 不阻斷。
    _ensure_protective_order(bot, position)

    # 更新「持倉期間最高價」（給追蹤止損用）。
    # 起算基準：資料庫存的 peak_price；若還沒有（剛接手/重啟後第一次）就用進場價起算。
    peak = max(bot.peak_price or entry_price, current_price)
    if peak != bot.peak_price:
        _persist_peak(bot, peak)

    # --- 風控出場判斷（止損 → 追蹤止損 → 止盈）---
    emit_activity(bot, "risk_check", "風控檢查中（止損→追蹤止損→止盈）")
    should_exit, exit_reason = check_exit(
        entry_price=entry_price,
        current_price=current_price,
        peak_price=peak,
        take_profit_pct=bot.take_profit_pct,
        stop_loss_pct=bot.stop_loss_pct,
        trailing_stop_pct=bot.trailing_stop_pct,
    )
    if should_exit:
        # 本機出場前先撤券商端保護單（掛著的 stop 會保留股數，不撤市價賣會被拒）。
        # 撤不掉 = 券商端剛好已成交 → 放棄本機賣出，下一輪由 _settle_broker_exit 回填帳。
        if not _cancel_protective_order(bot):
            _record_decision(bot, Signal.SELL, "券商端保護單已先成交，待下一輪回填", current_price, ACTION_HOLD)
            return
        qty = float(position.qty)
        order = alpaca_client.submit_market_order(bot.symbol, qty, "sell")
        _record_and_notify(bot, "sell", qty, current_price, order, exit_reason)
        exit_kind = classify_exit_kind(exit_reason)
        thesis = build_thesis_breach(_recent_buy_log(bot.id), current_price, exit_kind)
        _record_decision(bot, Signal.SELL, exit_reason, current_price, ACTION_SOLD, qty=qty,
                         exit_kind=exit_kind, thesis_breach=thesis,
                         total_amount=qty * current_price, position_after=_position_after(bot))
        _persist_peak(bot, None)  # 已平倉，清掉最高價紀錄
        return

    # --- 風控沒觸發 → 看策略要不要賣 ---
    # ctx（量 + 指標快照）是選用第三元素：測試常 monkeypatch _run_strategy 回 2-tuple，
    # 用 *rest 容錯，沒帶就視為空 ctx，不影響賣出主流程。
    signal, reason, *rest = _run_strategy(bot)
    ctx = rest[0] if rest else {}
    vol, inds = ctx.get("volume"), ctx.get("indicators")
    snap, strat = ctx.get("market_snapshot"), ctx.get("strategy")
    if signal == Signal.SELL:
        if not _cancel_protective_order(bot):  # 同上：cancel-before-sell
            _record_decision(bot, Signal.SELL, "券商端保護單已先成交，待下一輪回填",
                             current_price, ACTION_HOLD, volume=vol, indicators=inds,
                             market_snapshot=snap, strategy=strat)
            return
        qty = float(position.qty)
        order = alpaca_client.submit_market_order(bot.symbol, qty, "sell")
        _record_and_notify(bot, "sell", qty, current_price, order, reason)
        exit_kind = classify_exit_kind(reason)
        thesis = build_thesis_breach(_recent_buy_log(bot.id), current_price, exit_kind)
        _record_decision(bot, Signal.SELL, reason, current_price, ACTION_SOLD,
                         volume=vol, qty=qty, indicators=inds,
                         market_snapshot=snap, strategy=strat,
                         exit_kind=exit_kind, thesis_breach=thesis,
                         total_amount=qty * current_price, position_after=_position_after(bot))
        _persist_peak(bot, None)
    else:
        # 策略買進/觀望且風控未觸發 → 續抱（不重複買進）
        print(f"[{bot.name}] 續抱 {bot.symbol}：{reason}")
        _record_decision(bot, signal, reason, current_price, ACTION_HOLD,
                         volume=vol, indicators=inds, market_snapshot=snap, strategy=strat)


def _handle_flat(bot: Bot, current_price: float) -> None:
    """空手中：跑策略，出現買進訊號 → 先過組合層守門（熔斷 / 購買力）才進場。"""
    # 沒持倉，確保沒有殘留的最高價（只在原本有值時才寫 DB，省一次無謂的 commit）
    if bot.peak_price is not None:
        _persist_peak(bot, None)

    # ctx（量 + 指標快照）是選用第三元素，沿用容錯：測試 monkeypatch 回 2-tuple 時 ctx 為空
    signal, reason, *rest = _run_strategy(bot)
    ctx = rest[0] if rest else {}
    vol, inds = ctx.get("volume"), ctx.get("indicators")
    snap, strat = ctx.get("market_snapshot"), ctx.get("strategy")
    if signal != Signal.BUY:
        print(f"[{bot.name}] {bot.symbol} 空手觀望：{reason}")
        _record_decision(bot, signal, reason, current_price, ACTION_HOLD,
                         volume=vol, indicators=inds, market_snapshot=snap, strategy=strat)
        return

    # --- 想買進：組合回撤熔斷（step-09，只擋進不擋出）---
    if check_breaker()["tripped"]:
        print(f"[{bot.name}] 組合回撤熔斷中，跳過買進 {bot.symbol}。")
        _record_decision(bot, signal, "組合回撤熔斷，暫停新增曝險", current_price,
                         ACTION_SKIPPED_CIRCUIT_BREAKER, volume=vol, indicators=inds,
                         market_snapshot=snap, strategy=strat)
        return

    # 用設定金額換算要買幾股。
    # 會掛券商端保護單的 Bot 必須買「整股」（Alpaca 的 stop/trailing 單不支援碎股）；
    # 沒掛保護單需求的維持碎股（保留 4 位小數），行為與舊版一致。
    needs_protection = settings.BROKER_STOP_ENABLED and plan_protective_order(
        current_price,
        stop_loss_pct=bot.stop_loss_pct,
        trailing_stop_pct=bot.trailing_stop_pct,
    ) is not None
    if needs_protection:
        qty = whole_share_qty(bot.trade_amount, current_price)
        if qty <= 0:
            print(f"[{bot.name}] trade_amount ${bot.trade_amount:.2f} 買不起 1 股 {bot.symbol}"
                  f"（${current_price:.2f}，券商端止損需整股），跳過買進。")
            _record_decision(
                bot, signal,
                f"trade_amount ${bot.trade_amount:.2f} 買不起 1 股（${current_price:.2f}；券商端止損需整股）",
                current_price, ACTION_SKIPPED_NO_BUYING_POWER,
                volume=vol, indicators=inds, market_snapshot=snap, strategy=strat,
            )
            return
    else:
        qty = round(bot.trade_amount / current_price, 4)

    # --- 購買力守門（step-05，best-effort；查不到就放行）---
    buying_power = _available_buying_power()
    if buying_power is not None and qty * current_price > buying_power:
        print(f"[{bot.name}] 購買力不足（需 ${qty * current_price:.2f} > 可用 ${buying_power:.2f}），跳過買進。")
        _record_decision(
            bot, signal,
            f"購買力不足：需 ${qty * current_price:.2f}，可用 ${buying_power:.2f}",
            current_price, ACTION_SKIPPED_NO_BUYING_POWER,
            volume=vol, indicators=inds, market_snapshot=snap, strategy=strat,
        )
        return

    order = alpaca_client.submit_market_order(bot.symbol, qty, "buy")
    _record_and_notify(bot, "buy", qty, current_price, order, reason)
    # 進場當下就把「預期獲利點 / 預計停損點」結構化記下（賣出時才回填得出哪個假設失效）。
    # 只在有設門檻時記；trailing 停損點是動態的，進場當下的值意義不大，故不記 stop。
    target_price = current_price * (1 + bot.take_profit_pct) if bot.take_profit_pct else None
    stop_price = current_price * (1 - bot.stop_loss_pct) if bot.stop_loss_pct else None
    _record_decision(bot, Signal.BUY, reason, current_price, ACTION_BOUGHT,
                     volume=vol, qty=qty, indicators=inds,
                     market_snapshot=snap, strategy=strat,
                     target_price=target_price, stop_price=stop_price,
                     total_amount=qty * current_price, position_after=_position_after(bot))
    _persist_peak(bot, current_price)  # 進場價當作最高價的起點
    if needs_protection:
        # 把止損託管到券商端（失敗不擋主流程，下一輪自癒補掛）
        _place_protective_order(bot, qty, current_price)


def _run_strategy(bot: Bot):
    """抓 K 線、跑策略，回傳 (訊號, 原因)。抓不到資料時視為觀望。

    Phase 6 step-01：實盤改走「回測同一條資料路徑」——
    - 走 `market_data.get_bars`（與回測/海選同一個分派器），不再寫死打 `alpaca_client`。
    - 資料源用 `settings.DATA_SOURCE`（全系統唯一設定），不再鎖死 Alpaca。
    - 回看天數用 `required_lookback_days` 依策略參數推算，不再寫死 60
      （否則長均線等策略資料不夠、靜默失準）。

    Phase 7 step-03：bot.adaptive 開啟時走「自適應選策略」——
    先算當下市場狀態，查「狀態→最佳策略對照表」挑策略；無可信策略時保守觀望。

    Phase 7 step-05（層驗證收尾）：固定策略路徑的 BUY 也過 meta 二級過濾。
    層驗證證明只有 meta-labeling 在樣本外加分（adaptive 反而 −115、已維持關），
    且驗證的 baseline 正是「固定策略訊號 + should_take」這條路徑，故把它收回線上。
    閘由 `settings.META_LABEL_ENABLED` 控（關掉 = 純一級訊號，向後相容）。
    """
    if getattr(bot, "adaptive", False):
        return _run_adaptive_strategy(bot)

    days = required_lookback_days(bot.strategy, bot.params or {})
    emit_activity(bot, "fetch_data", f"抓取 {bot.symbol} 最近 {days} 天 K 線")
    df = market_data.get_bars(bot.symbol, days=days, source=settings.DATA_SOURCE)
    if df.empty:
        return Signal.HOLD, f"抓不到 {bot.symbol} 的資料", {}
    emit_activity(bot, "compute_signal", f"計算 {bot.strategy} 策略訊號")
    strategy = get_strategy(bot.strategy, bot.params or {})
    signal, reason = strategy.generate_signal(df)

    # 決策上下文（量 + 指標快照 + 市場快照 + 策略名）：抓到 df 就算一次，沿 3-tuple
    # 帶回給 _record_decision，讓觀望/買賣各分支都記得下「當時站在均線哪邊、放量縮量」。
    ctx = {"volume": _bar_volume(df),
           "indicators": _indicator_snapshot(bot.strategy, bot.params or {}, df),
           "market_snapshot": compute_market_snapshot(df),
           "strategy": bot.strategy}

    # meta 二級過濾：只把關進場（BUY）。流程與 layer_validation.MetaFilteredStrategy
    # 一致，線上行為才等於樣本外驗證量到的那條（+27.8 OOS EV）。SELL/HOLD 不受影響。
    if signal == Signal.BUY:
        from backend.services.regime_features import compute_features
        from backend.services.regime import classify_regime
        from backend.services.meta_label import should_take

        features = compute_features(df)
        regime = classify_regime(features)
        take, conf = should_take(signal, features, regime)
        if not take:
            return Signal.HOLD, f"[meta {regime}] 二級過濾否決進場（信心 {conf:.2f} < 門檻）", ctx
        reason = f"二級信心 {conf:.2f}｜{reason}"

    return signal, reason, ctx


def _run_adaptive_strategy(bot: Bot):
    """自適應模式（Phase 7 step-03）：依當下市場狀態挑策略再產生訊號。

    1. 抓一段夠長的 K 線（與對照表建立時同窗口，特徵才一致）。
    2. 算當下特徵 → 查該標的的「狀態→最佳策略對照表」（快取）。
    3. 該狀態有可信策略 → 用它產生訊號；無（fallback）→ 保守觀望。
    對照表計算或查詢失敗都不可中斷交易主流程，故 best-effort 退回觀望。
    """
    # 延遲 import 避免載入順序問題（selector 會用到 backtest_engine 等較重的相依）
    from backend.services.regime_features import compute_features
    from backend.services.strategy_selector import get_regime_strategy_map, select_strategy
    from backend.services.meta_label import should_take

    days = settings.REGIME_MAP_DAYS
    emit_activity(bot, "fetch_data", f"抓取 {bot.symbol} 最近 {days} 天 K 線（自適應）")
    df = market_data.get_bars(bot.symbol, days=days, source=settings.DATA_SOURCE)
    if df.empty:
        return Signal.HOLD, f"抓不到 {bot.symbol} 的資料", {}

    # 量先算（df 已在手）；指標快照要等選定策略後才算（用該策略的公式）。
    vol = _bar_volume(df)

    try:
        emit_activity(bot, "compute_signal", "自適應：辨識市場狀態、挑選策略中")
        regime_map = get_regime_strategy_map(bot.symbol)
    except Exception as e:
        return Signal.HOLD, f"自適應：對照表建立失敗（{e}），保守觀望", {"volume": vol, "indicators": None}

    features = compute_features(df)
    pick = select_strategy(features, regime_map)
    if pick["fallback"] or not pick["strategy"]:
        return (Signal.HOLD, f"自適應：{pick['regime']} 狀態無可信策略，保守觀望",
                {"volume": vol, "indicators": None, "market_snapshot": compute_market_snapshot(df)})

    strategy = get_strategy(pick["strategy"], pick["params"])
    signal, reason = strategy.generate_signal(df)
    # 指標快照用「這輪實際挑中的策略」的公式（與固定策略路徑同一套 compute_overlays）；
    # strategy 欄記「這輪實際挑中的」而非設定值，自適應的審計才精準。
    ctx = {"volume": vol,
           "indicators": _indicator_snapshot(pick["strategy"], pick["params"], df),
           "market_snapshot": compute_market_snapshot(df),
           "strategy": pick["strategy"]}

    # Phase 7 step-05：二級過濾（meta-labeling）只把關「進場」。一級給了 BUY，再問二級
    # 「這次該不該下注、信心多高」；信心不足 → 縮回觀望（出場 SELL 不受此門檻影響）。
    if signal == Signal.BUY:
        take, conf = should_take(signal, features, pick["regime"])
        if not take:
            return (Signal.HOLD, (
                f"[自適應 {pick['regime']}→{pick['strategy']}] 二級過濾否決進場"
                f"（信心 {conf:.2f} < 門檻），保守觀望"
            ), ctx)
        reason = f"二級信心 {conf:.2f}｜{reason}"

    # 把「這輪是哪個狀態挑了哪個策略」帶進原因，方便決策審計事後查驗
    return signal, f"[自適應 {pick['regime']}→{pick['strategy']}] {reason}", ctx


def _record_and_notify(bot, side, qty, price, order, reason) -> None:
    """把交易記到資料庫並發通知。"""
    # 這裡是所有成交的單一漏斗 → 順手發即時事件給前端可視化（fire-and-forget）
    emit_activity(
        bot, "order_submitted",
        f"{'買進' if side == 'buy' else '賣出'} {qty} 股",
        order={"side": side, "qty": safe_float(qty)},
    )
    db = SessionLocal()
    try:
        log = TradeLog(
            bot_id=bot.id,
            symbol=bot.symbol,
            side=side,
            qty=qty,
            price=price,
            order_id=str(getattr(order, "id", "")),
            reason=reason,
        )
        db.add(log)
        db.commit()
    finally:
        db.close()

    action = "買進" if side == "buy" else "賣出"
    notify(
        f"🤖 [{bot.name}] {action} {bot.symbol} {qty} 股 @ 約 ${price:.2f}\n原因：{reason}"
    )


class BotManager:
    """用排程器管理所有 Bot 的定時執行。"""

    def __init__(self) -> None:
        # coalesce + misfire_grace_time：電腦睡眠/卡頓錯過觸發時刻時，
        # 醒來後 1 小時內補觸發一次（coalesce=多次錯過只補一次）。
        # APScheduler 預設錯過 1 秒就放棄——家用電腦會睡，必須放寬。
        self.scheduler = BackgroundScheduler(
            job_defaults={"coalesce": True, "misfire_grace_time": 3600},
        )
        self.scheduler.start()

    def start_bot(self, bot: Bot, interval_seconds: int = 60) -> None:
        """啟動一個 Bot，讓它每隔 interval_seconds 秒跑一次。

        Phase 6 step-06：排程只記 bot.id（整數），不鎖死當下的 ORM 物件，
        run_bot_once 每輪用 id 重查最新值，改設定才會即時生效。
        """
        job_id = f"bot_{bot.id}"
        # 若已存在同 id 的工作，先移除避免重複
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
        self.scheduler.add_job(
            run_bot_once,
            "interval",
            seconds=interval_seconds,
            args=[bot.id],
            id=job_id,
            replace_existing=True,
        )
        notify(f"▶️ Bot 已啟動：{bot.name}（每 {interval_seconds} 秒檢查一次）")

    def stop_bot(self, bot_id: int) -> None:
        """停止一個 Bot。"""
        job_id = f"bot_{bot_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            notify(f"⏸️ Bot 已停止：id={bot_id}")

    def schedule_auto_deploy(self, hour: int) -> None:
        """
        掛上「模式 B 盤前自動部署」的每日定時工作（改版 Phase 4）。

        每天 hour 時跑一次 run_auto_deploy（force=False，所以是否真的部署仍由
        AUTO_DEPLOY_ENABLED 總開關決定）。在 main.py 啟動時呼叫一次即可。
        延遲 import 避免循環依賴（automation 反過來會用到 bot_manager）。
        """
        from backend.services.automation import run_auto_deploy

        job_id = "auto_deploy"
        self.scheduler.add_job(
            run_auto_deploy,
            "cron",
            hour=hour,
            id=job_id,
            replace_existing=True,
        )

    def schedule_opportunity_scan(self, interval_minutes: int) -> None:
        """
        掛上「常駐機會探勘」的週期工作（Phase 10 step-02）。

        每隔 interval_minutes 分鐘跑一次 run_opportunity_scan（內部會先過盤中閘、收盤跳過）。
        interval_minutes <= 0 代表關閉常駐掃描：移除既有 job（若有）並返回。
        在 main.py 啟動時呼叫一次；之後改 scan_interval_min 規則時即時重掛。
        延遲 import 避免循環依賴（opportunity_scan 反過來用到 services）。
        """
        from backend.services.opportunity_scan import run_opportunity_scan

        job_id = "opportunity_scan"
        if interval_minutes <= 0:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            return
        self.scheduler.add_job(
            run_opportunity_scan,
            "interval",
            minutes=interval_minutes,
            id=job_id,
            replace_existing=True,
        )

    def schedule_heartbeat(self, hour: int) -> None:
        """
        掛上「每日心跳日報」的定時工作（維運安全軌 H2）。

        每天 hour 時發一則「我還活著」摘要通知（不依賴開市——休市日也要證明系統活著）。
        在 main.py 啟動時呼叫一次即可。延遲 import 避免循環依賴。
        """
        from backend.services.catchup import make_daily_idempotent
        from backend.services.heartbeat import run_daily_heartbeat

        self.scheduler.add_job(
            # 同日防重複：開機補跑可能已先發過今天的日報，cron 再觸發會自動跳過
            make_daily_idempotent("heartbeat_daily", run_daily_heartbeat),
            "cron",
            hour=hour,
            id="heartbeat_daily",
            replace_existing=True,
        )

    def schedule_deadman_ping(self, interval_minutes: int) -> None:
        """
        掛上「dead-man ping」的週期工作（維運安全軌 H2）。

        每隔 interval_minutes 分鐘對外側監測服務發一個 GET；本機掛掉 → ping 停 →
        外側（healthchecks.io）主動發警報。interval_minutes <= 0 或 URL 沒設 = 關：
        移除既有 job（若有）並返回。在 main.py 啟動時呼叫一次即可。
        """
        from backend.services.heartbeat import ping_deadman

        job_id = "deadman_ping"
        if interval_minutes <= 0 or not settings.HEARTBEAT_PING_URL:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            return
        self.scheduler.add_job(
            ping_deadman,
            "interval",
            minutes=interval_minutes,
            id=job_id,
            replace_existing=True,
        )

    def schedule_tracking_check(self, hour: int) -> None:
        """
        掛上「tracking error 每日對帳」的定時工作（維運安全軌 H3）。

        每天 hour 時（建議美股收盤後）比對各啟用 Bot 的「Paper 實跑 vs 回測 OOS」，
        連續違規自動降級停 Bot + 通知（不平倉、不撤保護單，人再決定）。
        在 main.py 啟動時呼叫一次即可。延遲 import 避免循環依賴
        （tracking 反過來會用到 bot_manager.stop_bot）。
        """
        from backend.services.catchup import make_daily_idempotent
        from backend.services.tracking import run_tracking_check

        self.scheduler.add_job(
            # 同日防重複：與開機補跑共用 job_run_log 判斷，同一天最多實際執行一次
            make_daily_idempotent("tracking_check", run_tracking_check),
            "cron",
            hour=hour,
            id="tracking_check",
            replace_existing=True,
        )

    def schedule_discovery(self, hour: int) -> None:
        """
        掛上「探勘橋」的每日定時工作（Phase 12 step-02）。

        每天 hour 時跑一次 run_discovery_batch（收件匣素材 → 本機 LLM triage → candidate）。
        DISCOVERY_ENABLED=false 代表完全不掛：移除既有 job（若有）並返回
        （run_discovery_batch 內部還有一道開關雙保險）。在 main.py 啟動時呼叫一次即可。
        延遲 import 避免循環依賴。
        """
        from backend.services.catchup import make_daily_idempotent
        from backend.services.discovery import run_discovery_batch

        job_id = "discovery_bridge"
        if not settings.DISCOVERY_ENABLED:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            return
        self.scheduler.add_job(
            # 同日防重複：與開機補跑共用 job_run_log 判斷，同一天最多實際執行一次
            make_daily_idempotent(job_id, run_discovery_batch),
            "cron",
            hour=hour,
            id=job_id,
            replace_existing=True,
        )

    def schedule_auto_validate(self, hour: int) -> None:
        """
        掛上「候選自動批次驗證」的每日定時工作（Phase 12 step-03）。

        每天 hour 時跑一次 run_auto_validate（candidate → 既有 OOS 閘 → validated/rejected，
        判準零修改；不自動晉升 curated）。AUTO_VALIDATE_ENABLED=false 代表完全不掛：
        移除既有 job（若有）並返回（run_auto_validate 內部還有一道開關雙保險）。
        在 main.py 啟動時呼叫一次即可。延遲 import 避免循環依賴。
        """
        from backend.services.catchup import make_daily_idempotent
        from backend.services.auto_validate import run_auto_validate

        job_id = "auto_validate"
        if not settings.AUTO_VALIDATE_ENABLED:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            return
        self.scheduler.add_job(
            # 同日防重複：與開機補跑共用 job_run_log 判斷，同一天最多實際執行一次
            make_daily_idempotent(job_id, run_auto_validate),
            "cron",
            hour=hour,
            id=job_id,
            replace_existing=True,
        )

    def schedule_auto_deploy_knowledge(self, hour: int) -> None:
        """
        掛上「知識庫策略 → 自動建 Paper Bot」的每日定時工作。

        每天 hour 時跑一次 run_auto_deploy_knowledge（取目標狀態未部署的知識 → 建 Paper Bot
        掛網跑；★只建 paper、不碰真錢雙閘）。AUTO_DEPLOY_KNOWLEDGE_ENABLED=false 代表完全不掛：
        移除既有 job（若有）並返回（run_auto_deploy_knowledge 內部還有一道開關雙保險）。
        在 main.py 啟動時呼叫一次即可。延遲 import 避免循環依賴。

        ★ 與既有 screener 版 schedule_auto_deploy（盤前海選自動部署）不同：本檔走知識庫，
          job_id 用 "auto_deploy_knowledge" 區隔，互不影響。
        """
        from backend.services.catchup import make_daily_idempotent
        from backend.services.auto_deploy_knowledge import run_auto_deploy_knowledge

        job_id = "auto_deploy_knowledge"
        if not settings.AUTO_DEPLOY_KNOWLEDGE_ENABLED:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            return
        self.scheduler.add_job(
            # 同日防重複：與開機補跑共用 job_run_log 判斷，同一天最多實際執行一次
            make_daily_idempotent(job_id, run_auto_deploy_knowledge),
            "cron",
            hour=hour,
            id=job_id,
            replace_existing=True,
        )

    def schedule_bot_review(self, hour: int) -> None:
        """
        掛上「bot 汰弱審查員」的每日定時工作（Phase 13）。

        每天 hour 時跑一次 run_bot_review（考核 paper 艦隊 → upsert fit → 軟汰弱不及格 Bot；
        ★只碰 paper，不碰真錢相關狀態）。BOT_REVIEW_ENABLED=false 代表完全不掛：移除既有
        job（若有）並返回（run_bot_review 內部還有一道開關雙保險）。在 main.py 啟動時呼叫一次
        即可。延遲 import 避免循環依賴。
        """
        from backend.services.catchup import make_daily_idempotent
        from backend.services.bot_review import run_bot_review

        job_id = "bot_review"
        if not settings.BOT_REVIEW_ENABLED:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            return
        self.scheduler.add_job(
            # 同日防重複：與開機補跑共用 job_run_log 判斷，同一天最多實際執行一次
            make_daily_idempotent(job_id, run_bot_review),
            "cron",
            hour=hour,
            id=job_id,
            replace_existing=True,
        )

    def schedule_collector_scan(self, interval_minutes: int) -> None:
        """
        掛上「市場蒐集員收料」的週期工作（Phase 10 step-04）。

        每隔 interval_minutes 分鐘跑一次 run_collector_scan（抓 RSS → 收件匣 → 有新料提醒）。
        interval_minutes <= 0 代表關閉常駐收料：移除既有 job（若有）並返回。
        在 main.py 啟動時呼叫一次即可。延遲 import 避免循環依賴。
        """
        from backend.services.collector import run_collector_scan

        job_id = "collector_scan"
        if interval_minutes <= 0:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            return
        self.scheduler.add_job(
            run_collector_scan,
            "interval",
            minutes=interval_minutes,
            id=job_id,
            replace_existing=True,
        )

    def schedule_leader_backtest(self, hour: int) -> None:
        """
        掛上「每日領導股回測紀錄」的定時工作。

        每天 hour 時對 LEADER_BACKTEST_SYMBOLS 各跑一輪全自動掃描（OOS EV 排名），
        各檔冠軍存一筆 BacktestRun（只落紀錄、不下單、不建 Bot）。
        LEADER_BACKTEST_ENABLED=false 代表完全不掛：移除既有 job（若有）並返回
        （run_leader_backtest 內部還有一道開關雙保險）。在 main.py 啟動時呼叫一次即可。
        """
        from backend.services.catchup import make_daily_idempotent
        from backend.services.daily_watch import run_leader_backtest

        job_id = "leader_backtest"
        if not settings.LEADER_BACKTEST_ENABLED:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            return
        self.scheduler.add_job(
            # 同日防重複：與開機補跑共用 job_run_log 判斷，同一天最多實際執行一次
            make_daily_idempotent(job_id, run_leader_backtest),
            "cron",
            hour=hour,
            id=job_id,
            replace_existing=True,
        )

    def schedule_catchup_on_boot(self) -> None:
        """
        掛上「開機補跑」的一次性工作（後端啟動時呼叫，立刻在排程器執行緒池跑一次）。

        把「開關有開 + 排定時刻已過 + 今天還沒跑」的每日 job 依管線順序補跑——
        家用電腦不是 24/7，早上沒開機的日子靠這個救回來。
        CATCHUP_ON_BOOT=false = 不掛（補跑功能整個關閉，cron 行為照舊）。
        """
        from backend.services.catchup import run_catchup

        if not settings.CATCHUP_ON_BOOT:
            return
        # "date" 觸發器不給 run_date = 排進去就盡快跑一次；用排程器執行緒池，不擋 FastAPI 啟動
        self.scheduler.add_job(
            run_catchup,
            "date",
            id="catchup_on_boot",
            replace_existing=True,
        )


# 全域共用的 Bot 管理器
bot_manager = BotManager()
