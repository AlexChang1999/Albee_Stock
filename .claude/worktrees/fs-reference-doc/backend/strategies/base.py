"""
策略基底類別
============
所有交易策略的共同父類別。

設計概念：
- 每個策略都要實作 generate_signal()，吃一份 K 線資料(DataFrame)，
  吐出一個「訊號」：買(buy) / 賣(sell) / 觀望(hold)。
- Bot 不需要知道策略內部怎麼算，只要拿到訊號就好（這就是「鬆耦合」）。
"""

from abc import ABC, abstractmethod

import pandas as pd


class Signal:
    """交易訊號的三種值，用常數避免打錯字。"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class BaseStrategy(ABC):
    """策略基底。新策略請繼承這個類別並實作 generate_signal()。"""

    # 策略名稱（子類別覆寫）
    name: str = "base"

    def __init__(self, params: dict | None = None) -> None:
        # params 是策略參數，例如均線交叉的 {"short_window": 5, "long_window": 20}
        self.params = params or {}

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame) -> tuple[str, str]:
        """
        根據 K 線資料產生交易訊號。
        :param df: 含 close 欄位的 K 線資料（時間由舊到新）
        :return: (訊號, 原因說明)
                 訊號為 Signal.BUY / Signal.SELL / Signal.HOLD
        """
        raise NotImplementedError
