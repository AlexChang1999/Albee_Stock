"""
持倉 API
========
給前端圖表畫「進場均價／固定止損／止盈」水位線用的端點。

為什麼需要：
- Bot 資料庫只存「百分比」（stop_loss_pct…），止損／止盈是相對「進場均價」算的。
- 但進場均價不在 Bot 資料庫，而在 Alpaca 帳戶的「持倉」裡（avg_entry_price）。
- 前端拿到這支回的進場均價後，就能算出實際價位畫線：
    固定止損 = avg_entry_price ×(1 − stop_loss_pct)
    固定止盈 = avg_entry_price ×(1 + take_profit_pct)
"""

from fastapi import APIRouter, HTTPException

from backend.services.alpaca_client import alpaca_client

router = APIRouter(tags=["Positions"])


@router.get("/positions/{symbol}")
def get_position(symbol: str):
    """
    查某檔股票目前持倉的進場均價與股數。

    :param symbol: 股票代號（一律轉大寫）
    :return: 有持倉 → {"symbol", "qty", "avg_entry_price"}
             空手 → {"symbol", "qty": 0, "avg_entry_price": None}
    """
    symbol = symbol.upper()
    try:
        pos = alpaca_client.get_position(symbol)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"查持倉失敗：{e}")

    # 空手：get_position 接住例外後回 None
    if pos is None:
        return {"symbol": symbol, "qty": 0, "avg_entry_price": None}

    return {
        "symbol": symbol,
        # Alpaca 回的是字串，轉成數字給前端好用
        "qty": float(pos.qty),
        "avg_entry_price": float(pos.avg_entry_price),
    }
