"""
即時報價 API
============
提供兩個東西：
1. WebSocket /ws/quotes ── 前端連上後，即時收到訂閱股票的最新價（會一直跳動）
2. GET /quotes/{symbol}  ── 一次性查目前價格（前端剛開啟、還沒收到第一筆推送時先墊著用）

實際的「拉價 + 扇出推送」邏輯都在 services/quote_stream.py 的 hub 裡，
這支只負責「接 WebSocket、解析前端送來的訂閱指令」。
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from backend.services.alpaca_client import alpaca_client
from backend.services.quote_stream import hub

router = APIRouter(tags=["Quotes"])


@router.get("/quotes/{symbol}")
def get_quote(symbol: str):
    """一次性查某股票目前的最新成交價。"""
    try:
        price = alpaca_client.get_latest_price(symbol.upper())
        return {"symbol": symbol.upper(), "price": float(price)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"取得報價失敗：{e}")


@router.websocket("/ws/quotes")
async def ws_quotes(ws: WebSocket):
    """
    前端的即時報價通道。

    前端送的訊息格式（JSON）：
        {"action": "subscribe",   "symbols": ["AAPL", "TSLA"]}
        {"action": "unsubscribe", "symbols": ["TSLA"]}

    後端推回的訊息格式（JSON）：
        {"symbol": "AAPL", "price": 312.05, "ts": 1717400000.0}
    """
    await hub.connect(ws)
    try:
        while True:
            data = await ws.receive_json()
            action = data.get("action")
            # 代號一律轉大寫，跟系統其他地方一致
            symbols = [str(s).upper() for s in data.get("symbols", [])]
            if action == "subscribe":
                hub.subscribe(ws, symbols)
            elif action == "unsubscribe":
                hub.unsubscribe(ws, symbols)
            # 其他 action 一律忽略（保持寬鬆，前端送錯不會炸掉連線）
    except WebSocketDisconnect:
        # 前端正常關閉連線
        hub.disconnect(ws)
    except Exception:
        # 任何其他異常（收到非 JSON 等）也安全清掉這個連線
        hub.disconnect(ws)
