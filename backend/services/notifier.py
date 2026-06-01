"""
通知服務
========
當 Bot 有重要事件（下單、錯誤）時，發送通知。

設計重點（新手友善）：
- 永遠會在主控台（console）印出訊息。
- 如果有設定 LINE，就「額外」推播到 LINE。
- 沒設定 LINE 也不會報錯，程式照常運作（優雅降級）。

註：LINE Notify 已於 2025 年停止服務，這裡改用 LINE Messaging API 的
推播(push)功能。需要 LINE_CHANNEL_ACCESS_TOKEN 和你的 LINE user id。
user id 之後設定好再填到 .env 的 LINE_USER_ID 即可。
"""

import os

import requests

from backend.config import settings

# 你的 LINE user id（之後再設定，現在可留空）
LINE_USER_ID = os.getenv("LINE_USER_ID", "")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def notify(message: str) -> None:
    """
    發送通知。
    :param message: 要通知的文字內容
    """
    # 1) 一定先在主控台印出（加時間，方便看 log）
    print(f"[通知] {message}")

    # 2) 如果 LINE 設定齊全，就推播到 LINE
    if settings.LINE_CHANNEL_ACCESS_TOKEN and LINE_USER_ID:
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
