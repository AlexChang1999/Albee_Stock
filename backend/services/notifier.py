"""
通知服務
========
當 Bot 有重要事件（下單、錯誤）時，發送通知。

設計重點（新手友善）：
- 永遠會在主控台（console）印出訊息。
- 有設定 Discord Webhook，就額外推播到 Discord。
- 推播失敗不會讓主程式崩潰（優雅降級）。

Discord 用 Webhook：到頻道「設定 → 整合 → 建立 Webhook」拿到網址，
填進 .env 的 DISCORD_WEBHOOK_URL 即可，不需要任何套件或機器人權限。
"""

import os
import time

import requests

# Discord 頻道 Webhook 網址（留空 = 不啟用 Discord 通知）
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

_MAX_RETRIES = 3  # 429 最多重試次數


def _send_discord(message: str) -> None:
    """推播到 Discord Webhook（沒設定就直接跳過）。429 依 retry_after 重試最多 3 次。"""
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        for attempt in range(_MAX_RETRIES):
            resp = requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=10)
            if resp.status_code in (200, 204):
                return
            if resp.status_code == 429:
                # 尊重 Discord 的限流視窗，等完再重送
                retry_after = resp.json().get("retry_after", 1.0)
                time.sleep(float(retry_after) + 0.1)
                continue
            # 其他錯誤不重試
            print(f"⚠️  Discord 推播失敗（{resp.status_code}）：{resp.text}")
            return
        print(f"⚠️  Discord 推播連續 {_MAX_RETRIES} 次 429，放棄")
    except Exception as e:
        print(f"⚠️  Discord 推播發生例外：{e}")


def notify(message: str) -> None:
    """
    發送通知到所有已設定的管道。
    :param message: 要通知的文字內容
    """
    # 主控台 log 是 best-effort：cp950 等編碼印不出 emoji 時絕不能讓例外往上炸——
    # 這行只是回音，炸掉會連後面真正的 Discord 推播都一起死（心跳日報實測踩過）。
    try:
        print(f"[通知] {message}")
    except UnicodeEncodeError:
        print("[通知] (訊息含主控台編碼印不出的字元，內容已照常送推播管道)")
    _send_discord(message)
