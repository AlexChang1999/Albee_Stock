"""
基本面 / 財報 / 新聞資料
========================
用免費的 yfinance 抓「非 K 線」的資料，補足 Alpaca 沒有的部分：

- 公司基本資料（profile）：市值、本益比 PE、EPS、股息率、產業、公司簡介…
- 財報三表（financials）：損益表、資產負債表、現金流量表（年度 / 季度）
- 新聞（news）：個股相關新聞標題 + 連結
- 配息 / 分割（actions）：歷史配息與股票分割紀錄

設計重點：
- yfinance 回傳的東西常是 pandas DataFrame / Series，且夾雜 NaN、numpy 型別、
  Timestamp 當索引——這些「不能直接轉成 JSON」。所以下面抽了幾個「純函式」
  專門做清洗轉換（_clean / _statement_to_records / _normalize_news），
  好處是可以「離線單元測試」，不必每次都連網。
- 對外的 get_xxx() 才真的連網抓資料，再交給純函式清洗。
"""

import math

import pandas as pd
import yfinance as yf


# ---------- 純函式（好測試，不碰網路）----------
def _clean(value):
    """
    把單一值清成「可放進 JSON」的乾淨值：
    - NaN / 無限大 → None（JSON 沒有 NaN，硬塞會壞）
    - pandas Timestamp → ISO 字串
    - numpy 數字 → Python 原生 int / float
    """
    # pandas 缺值（NaN / NaT）
    try:
        if value is None or (not isinstance(value, str) and pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass

    # 時間戳記 → 字串
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()

    # 浮點數的無限大也不能進 JSON
    if isinstance(value, float) and math.isinf(value):
        return None

    # numpy 數字 → Python 原生型別（有 .item() 的就轉）
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            return value

    return value


def _statement_to_records(df: pd.DataFrame) -> list[dict]:
    """
    把財報 DataFrame 轉成前端好用的「每個期間一筆」格式。

    yfinance 的財報長相：列(index)是會計科目、欄(columns)是各報告期間的日期。
    這裡轉成：
        [
          {"period": "2025-09-30", "items": {"Total Revenue": 123, ...}},
          {"period": "2024-09-30", "items": {...}},
        ]
    """
    if df is None or df.empty:
        return []

    records = []
    for period in df.columns:
        items = {}
        for line_item in df.index:
            items[str(line_item)] = _clean(df.loc[line_item, period])
        records.append({"period": _clean(period), "items": items})
    return records


def _normalize_news(raw: list) -> list[dict]:
    """
    把 yfinance 的新聞清成統一格式：{title, publisher, link, published}。

    yfinance 不同版本新聞結構不一樣：
    - 新版每筆包在 item["content"] 裡（content.title / canonicalUrl.url / provider…）
    - 舊版直接 item["title"] / item["link"] / item["publisher"]
    這裡兩種都接，缺欄位就給空字串，確保前端永遠拿到一致格式。
    """
    out = []
    for item in raw or []:
        content = item.get("content", item)  # 新版在 content 裡，舊版就是本身
        # 連結：新版在 canonicalUrl.url 或 clickThroughUrl.url
        link = ""
        for key in ("canonicalUrl", "clickThroughUrl"):
            if isinstance(content.get(key), dict):
                link = content[key].get("url", "")
                if link:
                    break
        link = link or content.get("link", "")
        # 發布者：新版在 provider.displayName，舊版在 publisher
        provider = content.get("provider")
        publisher = (
            provider.get("displayName", "")
            if isinstance(provider, dict)
            else content.get("publisher", "")
        )
        out.append({
            "title": content.get("title", ""),
            "publisher": publisher,
            "link": link,
            "published": content.get("pubDate", content.get("providerPublishTime", "")),
        })
    return out


# 公司基本資料要挑出來顯示的欄位（中文標籤）。
# yfinance 的 .info 欄位很多很雜，這裡只挑新手看得懂、實用的。
_PROFILE_FIELDS = {
    "longName": "公司名稱",
    "sector": "產業類別",
    "industry": "細分產業",
    "country": "國家",
    "marketCap": "市值",
    "trailingPE": "本益比 (PE)",
    "forwardPE": "預估本益比",
    "trailingEps": "每股盈餘 (EPS)",
    "dividendYield": "股息殖利率",
    "beta": "Beta 值",
    "fiftyTwoWeekHigh": "52 週最高",
    "fiftyTwoWeekLow": "52 週最低",
    "currency": "計價幣別",
    "fullTimeEmployees": "員工人數",
    "website": "官網",
    "longBusinessSummary": "公司簡介",
}


# ---------- 對外函式（會連網）----------
def get_profile(symbol: str) -> dict:
    """取得公司基本資料（挑重點欄位）。"""
    info = yf.Ticker(symbol).info or {}
    fields = {
        key: _clean(info.get(key))
        for key in _PROFILE_FIELDS
        if info.get(key) is not None
    }
    return {"symbol": symbol.upper(), "labels": _PROFILE_FIELDS, "fields": fields}


def get_financials(symbol: str, period: str = "annual") -> dict:
    """
    取得財報三表。period="annual"（年度）或 "quarterly"（季度）。
    回傳 income（損益表）/ balance（資產負債表）/ cashflow（現金流量表）。
    """
    ticker = yf.Ticker(symbol)
    if period == "quarterly":
        income, balance, cashflow = (
            ticker.quarterly_financials,
            ticker.quarterly_balance_sheet,
            ticker.quarterly_cashflow,
        )
    else:
        income, balance, cashflow = (
            ticker.financials,
            ticker.balance_sheet,
            ticker.cashflow,
        )
    return {
        "symbol": symbol.upper(),
        "period": period,
        "income": _statement_to_records(income),
        "balance": _statement_to_records(balance),
        "cashflow": _statement_to_records(cashflow),
    }


def get_news(symbol: str) -> dict:
    """取得個股相關新聞。"""
    raw = yf.Ticker(symbol).news
    return {"symbol": symbol.upper(), "news": _normalize_news(raw)}


def get_actions(symbol: str) -> dict:
    """取得配息與股票分割歷史。"""
    ticker = yf.Ticker(symbol)
    dividends = ticker.dividends  # Series：index=日期, value=每股配息
    splits = ticker.splits        # Series：index=日期, value=分割比例

    div_list = [
        {"date": _clean(idx), "amount": _clean(val)}
        for idx, val in (dividends.items() if dividends is not None else [])
    ]
    split_list = [
        {"date": _clean(idx), "ratio": _clean(val)}
        for idx, val in (splits.items() if splits is not None else [])
    ]
    return {"symbol": symbol.upper(), "dividends": div_list, "splits": split_list}
