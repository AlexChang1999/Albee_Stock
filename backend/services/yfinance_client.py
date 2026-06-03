"""
yfinance 資料源
===============
用免費的 yfinance 抓「日 K 線」歷史資料，當作 Alpaca 之外的第二資料源。

為什麼有這支：
- Alpaca 免費版歷史資料有限制；yfinance 免金鑰、歷史更長，適合做回測研究。
- 本檔回傳的 DataFrame 「格式」刻意做得跟 `alpaca_client.get_bars` 完全一樣，
  這樣下游的策略與回測引擎完全不用改，就能直接吃 yfinance 的資料。

資料契約（必須對齊 alpaca_client.get_bars，否則下游會壞）：
- 欄位：open / high / low / close / volume / timestamp
- 排序：舊 → 新（oldest-to-new）
- index：已 reset_index（整數索引）
- 抓不到資料時回傳「空 DataFrame」，讓回測引擎的空檢查能正常運作。
"""

import pandas as pd
import yfinance as yf

# yfinance 的原始欄位名稱（首字大寫）對應到我們要的小寫欄位名稱
_COLUMN_MAP = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
}


def _normalize(raw: pd.DataFrame) -> pd.DataFrame:
    """
    把 yfinance `Ticker.history()` 回傳的原始 DataFrame，
    轉成本專案統一契約的格式。

    抽成獨立的「純函式」是為了好寫測試——
    測試時餵一個假的 yfinance 格式 DataFrame 進來，
    不用真的連網就能驗證欄位轉換正確。

    :param raw: yfinance 原始資料，index 是日期，欄位含 Open/High/Low/Close/Volume...
    :return: 含 open/high/low/close/volume/timestamp 的 DataFrame（舊→新、整數索引）
    """
    # 抓不到資料 → 回傳空 DataFrame（與 alpaca_client 對齊）
    if raw is None or raw.empty:
        return pd.DataFrame()

    df = raw.copy()

    # 1. 把日期 index 變成一個正常欄位（原本 index 名稱通常是 "Date"）
    df = df.reset_index()
    # reset 後第一欄就是原本的日期 index，統一改名成 timestamp
    date_col = df.columns[0]
    df = df.rename(columns={date_col: "timestamp"})

    # 2. 把價量欄位改成小寫（Open → open ...）
    df = df.rename(columns=_COLUMN_MAP)

    # 3. 只保留契約需要的欄位（丟掉 Dividends、Stock Splits 等用不到的欄位）
    keep = ["timestamp", "open", "high", "low", "close", "volume"]
    df = df[[c for c in keep if c in df.columns]]

    # 4. 確保是「舊 → 新」排序（yfinance 預設已是升冪，這裡保險起見再排一次）
    df = df.sort_values("timestamp").reset_index(drop=True)

    return df


def get_bars(symbol: str, days: int = 60) -> pd.DataFrame:
    """
    取得最近 N 天的日 K 線資料，回傳格式與 alpaca_client.get_bars 一致。

    :param symbol: 股票代號，例如 "AAPL"
    :param days: 往前抓幾天（日曆天；實際回傳的是這段期間內的交易日）
    :return: 含 open/high/low/close/volume/timestamp 的 DataFrame
    """
    ticker = yf.Ticker(symbol)
    # period="60d" 代表抓最近 60 天；auto_adjust=False 讓 open/high/low/close
    # 維持「原始未還原」價格，行為比較貼近 Alpaca 的原始 K 線。
    raw = ticker.history(period=f"{days}d", auto_adjust=False)
    return _normalize(raw)
