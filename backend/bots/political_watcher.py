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

from collections import defaultdict
from datetime import datetime

from backend.config import settings
from backend.services import political, notifier


def _passes_author_filter(author_name: str) -> bool:
    """只處理設定的作者（POLITICAL_AUTHOR_FILTER）；留空＝不過濾、收該頻道所有貼文。"""
    flt = (settings.POLITICAL_AUTHOR_FILTER or "").strip().lower()
    return (not flt) or flt in (author_name or "").lower()


def _handle_message(*, content: str, author_name: str, channel_name: str,
                    posted_at: datetime, history: dict, db) -> dict | None:
    """
    處理單則訊息（抽成純邏輯，方便離線測試）：算頻率 → 判讀 → 落表 → 回判讀結果。

    :param history: {author_name: [datetime, ...]}，記憶體裡的近期發文時間（算頻率用）。
    :return: 落表後的判讀 dict；被作者過濾擋下則回 None。
    """
    if not _passes_author_filter(author_name):
        return None

    # 更新該作者的發文時間軌跡，算頻率特徵（觀測佐證，不放大部位）
    history[author_name].append(posted_at)
    freq = political.frequency_features(history[author_name], posted_at)

    # 本機 Ollama 判讀（守外送閘；連不上回中性、不阻斷）
    verdict = political.judge_post_best_effort(content)

    political.record_event(
        db,
        source=f"discord:{channel_name}",
        author=author_name,
        text=content,
        posted_at=posted_at,
        verdict=verdict,
        freq=freq,
    )

    # 重大負面才提醒（煞車語意）；中性 / 偏多不洗頻
    if verdict.get("label") == "bearish":
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
        return

    try:
        import discord
    except Exception:
        print("⚠️ 未安裝 discord 套件。請先 `pip install discord.py` 再啟動 runner。")
        return

    intents = discord.Intents.default()
    intents.message_content = True  # 需要在 Discord 開發者後台開啟 Message Content Intent
    client = discord.Client(intents=intents)

    # 記憶體裡的作者→近期發文時間（算頻率特徵；runner 重啟即清空，不影響落表）
    history: dict = defaultdict(list)

    @client.event
    async def on_ready():
        print(f"🏛️ 政治專討員已上線：{client.user}（監看頻道 {channel_id or '全部'}）")

    @client.event
    async def on_message(message):
        # 忽略自己 / 機器人自身發言
        if message.author == client.user:
            return
        # 只看設定的頻道（留空＝不限制）
        if channel_id and str(message.channel.id) != channel_id:
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
            )
        except Exception as e:  # noqa: BLE001  best-effort，單則失敗不讓 runner 崩
            print(f"⚠️ 政治貼文處理失敗：{e}")
        finally:
            db.close()

    client.run(token)


if __name__ == "__main__":
    main()
