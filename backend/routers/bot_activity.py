"""
Bot 活動即時推送 API
====================
WebSocket /ws/bot-activity ── 前端連上後，即時收到所有 Bot 執行循環的步驟事件
（喚醒→抓數據→算訊號→風控→決策→下單→待機），給 Dashboard 卡片動畫與決策即時流用。

協議：
- 前端 → 後端：不需要任何指令，連上就收全部事件（前端自己按 bot_id 過濾）。
  receive 只用來偵測斷線。
- 後端 → 前端：每則 JSON 事件，schema 見 services/bot_activity.py 的 emit()。
  新連線會先收到最近事件的回放（ring buffer），feed 不會一開始空白。

實際的「執行緒橋接 + 扇出」邏輯都在 services/bot_activity.py 的 hub 裡，
這支只負責收連線、清連線。
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.services.bot_activity import hub

router = APIRouter(tags=["BotActivity"])


@router.websocket("/ws/bot-activity")
async def ws_bot_activity(ws: WebSocket):
    """前端的 Bot 活動事件通道：連上即收，斷線即清。"""
    await hub.connect(ws)
    try:
        while True:
            # 前端不需要送指令；這個 receive 只是為了偵測斷線
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(ws)
    except Exception:
        # 任何其他異常也安全清掉這個連線
        hub.disconnect(ws)
