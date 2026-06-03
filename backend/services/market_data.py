"""
資料源分派器
============
讓回測 / Bot 能選擇要用哪個資料源抓 K 線，但「預設行為完全不變」。

設計重點：
- 預設 source="alpaca"，所以原本所有呼叫的行為一模一樣，不會被影響。
- 想用免費的 yfinance 做研究時，傳 source="yfinance" 即可。
- 兩個資料源回傳的 DataFrame 格式相同（契約一致），下游策略/回測零改動。
"""

import pandas as pd

from backend.services import yfinance_client
from backend.services.alpaca_client import alpaca_client

# 支援的資料源 → 對應的取資料函式
_SOURCES = {
    "alpaca": alpaca_client.get_bars,
    "yfinance": yfinance_client.get_bars,
}


def get_bars(symbol: str, days: int = 60, source: str = "alpaca") -> pd.DataFrame:
    """
    依指定的資料源抓日 K 線。

    :param symbol: 股票代號
    :param days: 往前抓幾天
    :param source: 資料源，"alpaca"（預設）或 "yfinance"
    :return: 含 open/high/low/close/volume/timestamp 的 DataFrame
    :raises ValueError: 傳入不支援的 source 時
    """
    fetch = _SOURCES.get(source)
    if fetch is None:
        supported = "、".join(_SOURCES.keys())
        raise ValueError(f"不支援的資料源：{source}（可用：{supported}）")
    return fetch(symbol, days=days)
