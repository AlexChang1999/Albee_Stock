"""
政治專討員 — Discord 常駐 runner（Phase 10 step-05）
=====================================================
獨立常駐程式：連到一個 Discord 頻道，偵測政治貼文（例如川普發文鏡像）→ 本機 Ollama
判讀 → 落表（political_events）。判讀分數由 `political.political_size_factor` 接既有風險煞車。

★ 來源前提（最重要）：Discord bot **只能讀「它所在的頻道」**，不會自己去 Truth Social / X
  抓川普。你要先有一個「把川普貼文同步進來的 Discord 頻道」（RSS→webhook / 鏡像 bot），
  把這支 runner 拉進那個頻道、設定 .env 的 token 與 channel id，它才有東西可讀。
  沒設 token → 本程式印出指引後直接結束（可測試骨架，不會卡住）。

獨立執行（不掛在 FastAPI app 裡，避免阻塞）：
    venv\\Scripts\\python.exe -m backend.bots.political_watcher

核心判讀 / 落表邏輯都在 services/political.py（純函式、可離線測試）；
本檔只做「連 Discord + 取訊息 + 呼叫 service」這層薄薄的 I/O 膠水。
discord 套件採延遲 import，沒裝 / 不跑 runner 時，不影響其餘後端與測試。
"""

import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta

from backend.config import settings
from backend.services import political, notifier


def _passes_author_filter(author_name: str) -> bool:
    """只處理設定的作者（POLITICAL_AUTHOR_FILTER）；留空＝不過濾、收該頻道所有貼文。"""
    flt = (settings.POLITICAL_AUTHOR_FILTER or "").strip().lower()
    return (not flt) or flt in (author_name or "").lower()


def _notifier_webhook_id(url: str | None = None) -> str:
    """
    從系統通知的 DISCORD_WEBHOOK_URL 解析出 webhook id（URL 形如 .../webhooks/<id>/<token>）。

    ★ 自我回饋防護：我們的通知（心跳 / 政治風險警報）若發進 watcher 監看的同一頻道，
    會被自己讀回去 → 判讀 → 再發警報 → 無限迴圈（真實發生過）。靠 webhook id 認出
    「這則是我們自己發的」直接跳過。解析不到（沒設 / 格式不對）回空字串＝不過濾。
    """
    m = re.search(r"/webhooks/(\d+)", url if url is not None else (notifier.DISCORD_WEBHOOK_URL or ""))
    return m.group(1) if m else ""


def _is_own_notification(message_webhook_id, own_webhook_id: str) -> bool:
    """這則訊息是不是我們自己的通知 webhook 發的（是 → 不能吃，會自我回饋）。純函式。"""
    return bool(own_webhook_id) and str(message_webhook_id or "") == own_webhook_id


# 自我回饋第二層防護（內容指紋）：我們系統通知的固定開頭。webhook id 防護擋不到
# 「換 webhook 之前」已留在頻道歷史裡的舊警報，回補時會被撿回來，靠這層擋。
_ECHO_PREFIXES = ("🏛️ 政治風險訊號", "💓")


def _should_backfill_message(content: str, author_name: str) -> bool:
    """
    這則訊息要不要收（回補與即時監聽共用）：
    有文字內容（純圖片 / embed 空文字不收）+ 過作者過濾 + 不是我們自己的通知回音。
    抽成純函式方便離線測試；筆數上限由呼叫端（on_ready 回補迴圈）控制。
    """
    text = (content or "").strip()
    if not text or not _passes_author_filter(author_name):
        return False
    return not text.startswith(_ECHO_PREFIXES)


def _alert_allowed(author: str, now: datetime, last_sent: dict, cooldown_min: int) -> bool:
    """
    同作者政治警報節流：冷卻期內回 False（不再發、只印 console）。純函式（就地更新 last_sent）。

    最後一道防線——不管來源倒貨、回補重判、迴圈怎麼炸，同作者在 cooldown 分鐘內最多一則警報。
    cooldown_min <= 0 視為關閉節流（一律放行）。
    """
    if cooldown_min <= 0:
        return True
    prev = last_sent.get(author)
    if prev is not None and (now - prev) < timedelta(minutes=cooldown_min):
        return False
    last_sent[author] = now
    return True


def _handle_message(*, content: str, author_name: str, channel_name: str,
                    posted_at: datetime, history: dict, db,
                    notify_on_alert: bool, alert_state: dict | None = None) -> dict | None:
    """
    處理單則訊息（抽成純邏輯，方便離線測試）：算頻率 → 判讀 → 落表 → 回判讀結果。

    :param history: {author_name: [datetime, ...]}，記憶體裡的近期發文時間（算頻率用）。
    :param notify_on_alert: 是否在重大負面時發通知。回補歷史貼文傳 False（只補資料、
        不對舊貼文補發警報，殺掉「重啟補一波舊貼文→洗一波通知」）；即時監聽傳 True。
    :param alert_state: 同作者警報節流的記憶體狀態（{author: 上次發送時間}）；None＝不節流。
    :return: 落表後的判讀 dict；被作者過濾擋下則回 None。
    """
    if not _passes_author_filter(author_name):
        return None

    # 更新該作者的發文時間軌跡，算頻率特徵（觀測佐證，不放大部位）
    history[author_name].append(posted_at)
    freq = political.frequency_features(history[author_name], posted_at)

    # 本機 Ollama 判讀（守外送閘；連不上回中性、不阻斷）
    verdict = political.judge_post_best_effort(content)

    saved = political.record_event(
        db,
        source=f"discord:{channel_name}",
        author=author_name,
        text=content,
        posted_at=posted_at,
        verdict=verdict,
        freq=freq,
    )

    # 通知條件層層收斂（防洗版）：
    #   1. 確實是新落表（saved 非 None；撞唯一鍵的重判舊貼文不發）
    #   2. 呼叫端允許發（回補路徑一律不發）
    #   3. 判讀重大負面（煞車語意；中性 / 偏多不洗頻）
    #   4. 過同作者節流冷卻（來源倒貨 / 連環觸發時最多一則）
    if (
        saved is not None
        and notify_on_alert
        and verdict.get("label") == "bearish"
        and (alert_state is None
             or _alert_allowed(author_name, datetime.now(), alert_state,
                               settings.POLITICAL_ALERT_COOLDOWN_MIN))
    ):
        notifier.notify(
            f"🏛️ 政治風險訊號：{author_name} 貼文判讀偏空"
            f"（score={verdict.get('score')}）。{verdict.get('reason', '')}"
        )
    return verdict


def main() -> None:
    """連 Discord 常駐讀訊息。沒 token / 沒裝 discord 套件 → 印指引後結束（不報錯）。"""
    token = (settings.POLITICAL_DISCORD_TOKEN or "").strip()
    channel_id = (settings.POLITICAL_CHANNEL_ID or "").strip()

    if not token:
        print(
            "⚠️ 政治專討員未啟動：沒設定 POLITICAL_DISCORD_TOKEN。\n"
            "   前提：先有一個『把川普貼文同步進來的 Discord 頻道』，把這支 bot 拉進去，\n"
            "   再到 .env 設 POLITICAL_DISCORD_TOKEN 與 POLITICAL_CHANNEL_ID。\n"
            "   （判讀仍走本機 Ollama；POLITICAL_ENABLED 才會把分數接進風險煞車。）"
        )
        sys.exit(2)  # exit 2 = 設定缺失，看門狗應停止而非重啟

    try:
        import discord
    except Exception:
        print("⚠️ 未安裝 discord 套件。請先 `pip install discord.py` 再啟動 runner。")
        sys.exit(2)  # exit 2 = 設定缺失，看門狗應停止而非重啟

    intents = discord.Intents.default()
    intents.message_content = True  # 需要在 Discord 開發者後台開啟 Message Content Intent
    client = discord.Client(intents=intents)

    # 記憶體裡的作者→近期發文時間（算頻率特徵；runner 重啟即清空，不影響落表）
    history: dict = defaultdict(list)

    # 同作者警報節流狀態（{author: 上次發送時間}）；重啟清空，搭配 DB 唯一鍵防重判
    alert_state: dict = {}

    # 自我回饋防護：我們系統通知的 webhook id（這個 webhook 發的訊息一律不吃）
    own_webhook_id = _notifier_webhook_id()

    @client.event
    async def on_ready():
        print(f"🏛️ 政治專討員已上線：{client.user}（監看頻道 {channel_id or '全部'}）")

        # ===== 自我回饋偵測：通知 webhook 不可以跟監看頻道同一個頻道 =====
        # 同頻道 = 自己的警報被自己讀回去 → 判讀 → 再發警報 → 無限迴圈（真實踩過）。
        if own_webhook_id and channel_id:
            try:
                wh = await discord.Webhook.from_url(
                    notifier.DISCORD_WEBHOOK_URL, client=client
                ).fetch()  # URL 自帶 token，免 Manage Webhooks 權限
                if str(getattr(wh, "channel_id", "")) == channel_id:
                    print(
                        "🚨 設定錯誤：DISCORD_WEBHOOK_URL（系統通知）跟 POLITICAL_CHANNEL_ID"
                        "（鏡像監看頻道）是同一個頻道！會自我回饋洗版。\n"
                        "   請到另一個『通知專用』頻道建新 webhook，換掉 .env 的 DISCORD_WEBHOOK_URL。\n"
                        "   （已啟用 webhook 防護：自己發的訊息不會吃，但鏡像若共用同一 webhook 也會被擋。）"
                    )
            except Exception:  # noqa: BLE001  撈不到 webhook 資訊（權限不夠等）→ 不擋啟動
                pass

        # ===== 啟動回補：時間型補齊（只補比 DB 既有最新貼文更新的，且一律不發通知） =====
        # 電腦非 24h 開機，啟動前漏掉的貼文靠這段補。
        #   - DB 有資料 → 只補 created_at > 既有最新 posted_at 的（補漏、不重判舊貨）。
        #   - DB 空（剛搬 Neon）→ 退回只補最近 N 筆保底，避免空表瞬間把整段歷史補爆。
        #   - 回補一律 notify_on_alert=False：只補資料、不對歷史貼文補發警報（防重啟洗版）。
        limit = settings.POLITICAL_BACKFILL_LIMIT
        if limit <= 0 or not channel_id:
            return
        try:
            channel = client.get_channel(int(channel_id))
            if channel is None:
                channel = await client.fetch_channel(int(channel_id))
        except Exception as e:  # noqa: BLE001  頻道 ID 錯 / bot 沒進伺服器 → 不回補，照常監聽
            print(f"⚠️ 回補略過：拿不到頻道 {channel_id}（{e}）")
            return

        try:
            db_probe = political.get_session()
            try:
                since = political.latest_event_time(db_probe)  # DB 既有最新貼文時間（空表＝None）
            finally:
                db_probe.close()

            # history 由新到舊吐；多撈一些再過濾（純圖片 / embed 空文字訊息不算數）
            picked = []
            async for message in channel.history(limit=max(50, limit * 10)):
                if message.author == client.user:
                    continue
                # 自我回饋防護：自己系統通知 webhook 發的訊息不吃
                if _is_own_notification(getattr(message, "webhook_id", None), own_webhook_id):
                    continue
                if not _should_backfill_message(
                    message.content or "",
                    str(getattr(message.author, "name", message.author)),
                ):
                    continue
                # 時間型補齊：DB 已有資料時只補更新的；舊貼文已收過、不重判
                if since is not None and message.created_at is not None and message.created_at <= since:
                    continue
                picked.append(message)
                # 空表才用筆數上限保底；有 since 時靠時間窗界定、不另設小上限
                if since is None and len(picked) >= limit:
                    break

            # 反轉成「由舊到新」處理：頻率特徵與『最新事件』的時序才正確
            added = skipped = 0
            for message in reversed(picked):
                author_name = str(getattr(message.author, "name", message.author))
                posted_at = message.created_at or datetime.now()
                db = political.get_session()
                try:
                    if political.event_exists(db, author=author_name, posted_at=posted_at):
                        skipped += 1  # 上次回補 / 即時監聽已收過 → 防重跳過
                        continue
                    _handle_message(
                        content=message.content or "",
                        author_name=author_name,
                        channel_name=str(getattr(message.channel, "name", message.channel.id)),
                        posted_at=posted_at,
                        history=history,
                        db=db,
                        notify_on_alert=False,  # 回補不對歷史貼文補發警報
                    )
                    added += 1
                finally:
                    db.close()
            print(f"🔁 回補完成：新增 {added} 筆、跳過 {skipped} 筆（已存在；回補不發通知）")
        except Exception as e:  # noqa: BLE001  回補失敗不影響後續即時監聽
            print(f"⚠️ 回補失敗（不影響即時監聽）：{e}")

    @client.event
    async def on_message(message):
        # 忽略自己 / 機器人自身發言
        if message.author == client.user:
            return
        # 自我回饋防護：自己系統通知 webhook 發的訊息不吃（吃了會判讀→再警報→無限迴圈）
        if _is_own_notification(getattr(message, "webhook_id", None), own_webhook_id):
            return
        # 只看設定的頻道（留空＝不限制）
        if channel_id and str(message.channel.id) != channel_id:
            return
        # 與回補同一套收件判斷：有文字 + 過作者過濾 + 不是自己通知的回音
        if not _should_backfill_message(
            message.content or "",
            str(getattr(message.author, "name", message.author)),
        ):
            return

        db = political.get_session()
        try:
            _handle_message(
                content=message.content or "",
                author_name=str(getattr(message.author, "name", message.author)),
                channel_name=str(getattr(message.channel, "name", message.channel.id)),
                posted_at=message.created_at or datetime.now(),
                history=history,
                db=db,
                notify_on_alert=True,   # 即時新貼文才發警報
                alert_state=alert_state,  # 過同作者節流冷卻
            )
        except Exception as e:  # noqa: BLE001  best-effort，單則失敗不讓 runner 崩
            print(f"⚠️ 政治貼文處理失敗：{e}")
        finally:
            db.close()

    client.run(token)


if __name__ == "__main__":
    main()
