"""
持倉 API
========
唯讀端點：列出帳戶目前所有持倉 + 浮動損益，給前端 Dashboard 的持倉卡用。

定位：純讀 Alpaca 帳戶現況，不下單、不建 Bot。無金鑰 / 離線 / 失敗一律優雅降級回
空清單（不丟 500），讓前端沒設定金鑰也能正常顯示「目前無持倉」。
"""

from fastapi import APIRouter

from backend.services.alpaca_client import alpaca_client

router = APIRouter(tags=["Positions"])


def _to_float(value):
    """把 Alpaca 回來的字串數字安全轉 float；轉不動回 None（前端自行顯示「—」）。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _serialize(p) -> dict:
    """把一個 alpaca-py Position 物件映成前端要的精簡 dict（數字都轉 float）。"""
    return {
        "symbol": p.symbol,
        "qty": _to_float(p.qty),
        "avg_entry_price": _to_float(p.avg_entry_price),
        "current_price": _to_float(p.current_price),
        "market_value": _to_float(p.market_value),
        "unrealized_pl": _to_float(p.unrealized_pl),       # 浮動損益（金額）
        "unrealized_plpc": _to_float(p.unrealized_plpc),   # 浮動損益（比率，0.05=+5%）
    }


@router.get("/positions")
def list_positions():
    """
    列出目前所有持倉（含浮動損益）。

    無金鑰 / 連線失敗 → alpaca_client.list_positions() 已回 []，這裡照樣回空清單，
    不讓前端因後端缺金鑰而崩。
    """
    return [_serialize(p) for p in alpaca_client.list_positions()]
