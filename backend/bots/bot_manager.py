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

from apscheduler.schedulers.background import BackgroundScheduler

from backend.database import SessionLocal
from backend.models import Bot, TradeLog
from backend.services.alpaca_client import alpaca_client
from backend.services.notifier import notify
from backend.strategies import get_strategy, Signal


def run_bot_once(bot: Bot) -> None:
    """執行單一 Bot 一次完整的策略循環。"""
    try:
        # --- 1. 抓資料 ---
        df = alpaca_client.get_bars(bot.symbol, days=60)
        if df.empty:
            notify(f"[{bot.name}] 抓不到 {bot.symbol} 的資料，跳過這次。")
            return

        # --- 2. 跑策略 ---
        strategy = get_strategy(bot.strategy, bot.params or {})
        signal, reason = strategy.generate_signal(df)

        # 觀望就直接結束，不下單
        if signal == Signal.HOLD:
            print(f"[{bot.name}] {bot.symbol} 訊號：觀望 — {reason}")
            return

        # --- 3. 依訊號下單 ---
        position = alpaca_client.get_position(bot.symbol)
        current_price = alpaca_client.get_latest_price(bot.symbol)

        if signal == Signal.BUY:
            if position is not None:
                print(f"[{bot.name}] 已持有 {bot.symbol}，不重複買進。")
                return
            # 用設定金額換算要買幾股（保留 4 位小數，支援碎股）
            qty = round(bot.trade_amount / current_price, 4)
            order = alpaca_client.submit_market_order(bot.symbol, qty, "buy")
            _record_and_notify(bot, "buy", qty, current_price, order, reason)

        elif signal == Signal.SELL:
            if position is None:
                print(f"[{bot.name}] 沒有 {bot.symbol} 持倉，無法賣出。")
                return
            # 賣出全部持倉
            qty = float(position.qty)
            order = alpaca_client.submit_market_order(bot.symbol, qty, "sell")
            _record_and_notify(bot, "sell", qty, current_price, order, reason)

    except Exception as e:
        # 單一 Bot 出錯不應影響其他 Bot，這裡接住並通知
        notify(f"[{bot.name}] 執行時發生錯誤：{e}")


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


# 全域共用的 Bot 管理器
bot_manager = BotManager()
