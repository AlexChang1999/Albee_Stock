"""
通知服務
========
當 Bot 有重要事件（下單、錯誤）時，發送通知。

設計重點（新手友善）：
- 永遠會在主控台（console）印出訊息。
- 有設定哪個管道，就「額外」推播到那個管道（目前支援 LINE、Discord）。
- 任何管道沒設定或推播失敗，都不會讓主程式崩潰（優雅降級）；
  且各管道彼此獨立——LINE 掛掉不影響 Discord，反之亦然。

註：LINE Notify 已於 2025 年停止服務，這裡改用 LINE Messaging API 的
推播(push)功能。需要 LINE_CHANNEL_ACCESS_TOKEN 和你的 LINE user id。
user id 之後設定好再填到 .env 的 LINE_USER_ID 即可。

Discord 用最簡單的 Webhook：到頻道「設定 → 整合 → 建立 Webhook」拿到網址，
填進 .env 的 DISCORD_WEBHOOK_URL 即可，不需要任何套件或機器人權限。
"""

import os

import requests

from backend.config import settings

# 你的 LINE user id（之後再設定，現在可留空）
LINE_USER_ID = os.getenv("LINE_USER_ID", "")

# Discord 頻道 Webhook 網址（留空 = 不啟用 Discord 通知）
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def _send_line(message: str) -> None:
    """推播到 LINE（設定不齊就直接跳過）。"""
    if not (settings.LINE_CHANNEL_ACCESS_TOKEN and LINE_USER_ID):
        return
    try:
        headers = {
            "Authorization": f"Bearer {settings.LINE_CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "to": LINE_USER_ID,
            "messages": [{"type": "text", "text": message}],
        }
        resp = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"⚠️  LINE 推播失敗（{resp.status_code}）：{resp.text}")
    except Exception as e:
        # 通知失敗不應該讓主程式崩潰，所以只印出警告
        print(f"⚠️  LINE 推播發生例外：{e}")


def _send_discord(message: str) -> None:
    """推播到 Discord Webhook（沒設定就直接跳過）。"""
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        # Discord Webhook 規格：POST 一個 JSON，content 就是訊息文字
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=10)
        # 成功是 200 或 204（No Content），其餘視為失敗
        if resp.status_code not in (200, 204):
            print(f"⚠️  Discord 推播失敗（{resp.status_code}）：{resp.text}")
    except Exception as e:
        print(f"⚠️  Discord 推播發生例外：{e}")


def notify(message: str) -> None:
    """
    發送通知到所有已設定的管道。
    :param message: 要通知的文字內容
    """
    # 1) 一定先在主控台印出（方便看 log）
    print(f"[通知] {message}")

    # 2) 各管道獨立推播，互不影響（任一失敗不擋其他）
    _send_line(message)
    _send_discord(message)
