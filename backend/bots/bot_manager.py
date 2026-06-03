"""
Bot 管理器
==========
負責「執行」與「排程」Bot。

一個 Bot 的執行流程（run_bot_once）：
1. 抓該標的的歷史 K 線資料
2. 丟給策略，產生訊號（buy / sell / hold）
3. 依訊號決定動作：
   - buy ：若目前沒持倉 → 買進（用設定的金額換算股數）
   - sell：若目前有持倉 → 全部賣出
   - hold：什麼都不做
4. 把交易記到資料庫，並發通知

排程的部分用 APScheduler：每個啟用的 Bot 會定時（預設每 60 秒）跑一次。
注意：實際抓資料/下單需要有效的 Alpaca 金鑰才會成功。
"""

from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from backend.database import SessionLocal
from backend.models import Bot, TradeLog
from backend.services.alpaca_client import alpaca_client
from backend.services.notifier import notify
from backend.services.risk_manager import check_exit
from backend.strategies import get_strategy, Signal


# 追蹤止損要記住「持倉期間出現過的最高價」。
# 改存資料庫欄位 bot.peak_price（取代舊版記憶體 dict）：後端重啟後最高價仍在，
# 追蹤止損不會被重置、保護不中斷。None = 空手或尚未進場。
def _persist_peak(bot: Bot, peak: float | None) -> None:
    """把某 Bot 的「持倉最高價」寫回資料庫（peak=None 代表清除）。

    注意：bot 可能是排程帶進來的舊物件，這裡用 bot.id 重新查一筆最新的來更新，
    避免 session 過期問題。查不到（例如測試用的假物件）就靜默跳過。
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


def run_bot_once(bot: Bot, ignore_market_hours: bool = False) -> None:
    """
    執行單一 Bot 一次完整循環。

    :param ignore_market_hours: 是否略過「開市才執行」的檢查。
        排程自動跑時用預設 False（休市就跳過，省 API、避免怪單）；
        手動測試（/run）時傳 True，方便休市時間也能驗證風控邏輯。

    流程（持倉與否走不同分支）：
    - 持倉中：先跑風控（止損/追蹤止損/止盈），任一觸發就平倉；
              沒觸發才看策略要不要賣。
      → 重點：風控必須「不分策略訊號」都先檢查，所以不能像舊版那樣
        策略一觀望就提早 return，否則持倉時的止損會被跳過。
    - 空手中：跑策略，出現買進訊號就進場。
    """
    try:
        # --- 0. 休市就跳過（手動執行可用 ignore_market_hours 略過此檢查）---
        if not ignore_market_hours and not alpaca_client.is_market_open():
            print(f"[{bot.name}] 美股休市中，本次跳過。")
            _mark_checked(bot)  # 有跑這一輪（只是休市沒動作），仍更新檢查時間
            return

        # --- 1. 查目前持倉與現價 ---
        position = alpaca_client.get_position(bot.symbol)
        current_price = alpaca_client.get_latest_price(bot.symbol)

        if position is not None:
            _handle_holding(bot, position, current_price)
        else:
            _handle_flat(bot, current_price)

        _mark_checked(bot)  # 這一輪成功跑完，記錄檢查時間

    except Exception as e:
        # 單一 Bot 出錯不應影響其他 Bot，這裡接住並通知
        notify(f"[{bot.name}] 執行時發生錯誤：{e}")


def _handle_holding(bot: Bot, position, current_price: float) -> None:
    """持倉中：先風控出場，再看策略賣出訊號。"""
    entry_price = float(position.avg_entry_price)

    # 更新「持倉期間最高價」（給追蹤止損用）。
    # 起算基準：資料庫存的 peak_price；若還沒有（剛接手/重啟後第一次）就用進場價起算。
    peak = max(bot.peak_price or entry_price, current_price)
    if peak != bot.peak_price:
        _persist_peak(bot, peak)

    # --- 風控出場判斷（止損 → 追蹤止損 → 止盈）---
    should_exit, exit_reason = check_exit(
        entry_price=entry_price,
        current_price=current_price,
        peak_price=peak,
        take_profit_pct=bot.take_profit_pct,
        stop_loss_pct=bot.stop_loss_pct,
        trailing_stop_pct=bot.trailing_stop_pct,
    )
    if should_exit:
        qty = float(position.qty)
        order = alpaca_client.submit_market_order(bot.symbol, qty, "sell")
        _record_and_notify(bot, "sell", qty, current_price, order, exit_reason)
        _persist_peak(bot, None)  # 已平倉，清掉最高價紀錄
        return

    # --- 風控沒觸發 → 看策略要不要賣 ---
    signal, reason = _run_strategy(bot)
    if signal == Signal.SELL:
        qty = float(position.qty)
        order = alpaca_client.submit_market_order(bot.symbol, qty, "sell")
        _record_and_notify(bot, "sell", qty, current_price, order, reason)
        _persist_peak(bot, None)
    else:
        # 策略買進/觀望且風控未觸發 → 續抱（不重複買進）
        print(f"[{bot.name}] 續抱 {bot.symbol}：{reason}")


def _handle_flat(bot: Bot, current_price: float) -> None:
    """空手中：跑策略，出現買進訊號就進場。"""
    # 沒持倉，確保沒有殘留的最高價（只在原本有值時才寫 DB，省一次無謂的 commit）
    if bot.peak_price is not None:
        _persist_peak(bot, None)

    signal, reason = _run_strategy(bot)
    if signal == Signal.BUY:
        # 用設定金額換算要買幾股（保留 4 位小數，支援碎股）
        qty = round(bot.trade_amount / current_price, 4)
        order = alpaca_client.submit_market_order(bot.symbol, qty, "buy")
        _record_and_notify(bot, "buy", qty, current_price, order, reason)
        _persist_peak(bot, current_price)  # 進場價當作最高價的起點
    else:
        print(f"[{bot.name}] {bot.symbol} 空手觀望：{reason}")


def _run_strategy(bot: Bot):
    """抓 K 線、跑策略，回傳 (訊號, 原因)。抓不到資料時視為觀望。"""
    df = alpaca_client.get_bars(bot.symbol, days=60)
    if df.empty:
        return Signal.HOLD, f"抓不到 {bot.symbol} 的資料"
    strategy = get_strategy(bot.strategy, bot.params or {})
    return strategy.generate_signal(df)


def _record_and_notify(bot, side, qty, price, order, reason) -> None:
    """把交易記到資料庫並發通知。"""
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
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

    def start_bot(self, bot: Bot, interval_seconds: int = 60) -> None:
        """啟動一個 Bot，讓它每隔 interval_seconds 秒跑一次。"""
        job_id = f"bot_{bot.id}"
        # 若已存在同 id 的工作，先移除避免重複
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
        self.scheduler.add_job(
            run_bot_once,
            "interval",
            seconds=interval_seconds,
            args=[bot],
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


# 全域共用的 Bot 管理器
bot_manager = BotManager()
