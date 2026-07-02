"""
股票 → 產業（sector）對照 ── Phase 16 M7
========================================
股票池瘦身要「同 sector 只留 RS 最強 3~4 檔」，先得知道每檔屬於哪個產業。

策略：**手工 dict 為主**（38 檔池子固定、手寫最可靠、離線可用），
yfinance 補洞為輔（池子未來加新股時不會直接掛掉；查不到回 "unknown"）。

sector key 用 SPDR 產業 ETF 代號（XLK/XLF/XLE…），與 fund_flow_report 的
產業輪動報表同一套語言；指數型 ETF 標 "index"（不參與同 sector 竞爭瘦身）。
"""

from __future__ import annotations

# 手工對照（現行 38 檔池；新增股票先補這裡，補不到才落 yfinance）
SECTOR_BY_SYMBOL: dict[str, str] = {
    # 指數 ETF（不參與個股瘦身競爭）
    "SPY": "index", "QQQ": "index", "DIA": "index", "IWM": "index", "VTI": "index",
    # 半導體 / 科技（XLK）
    "NVDA": "XLK", "AMD": "XLK", "AVGO": "XLK", "TSM": "XLK", "INTC": "XLK",
    "QCOM": "XLK", "MU": "XLK", "AMAT": "XLK", "LRCX": "XLK", "ASML": "XLK",
    "AAPL": "XLK", "MSFT": "XLK", "ADBE": "XLK", "CRM": "XLK", "ORCL": "XLK",
    # 通訊服務（XLC）
    "GOOGL": "XLC", "META": "XLC", "NFLX": "XLC",
    # 非必需消費（XLY）
    "AMZN": "XLY", "TSLA": "XLY",
    # 能源（XLE）
    "XOM": "XLE", "CVX": "XLE", "COP": "XLE",
    # 金融（XLF）
    "JPM": "XLF", "BAC": "XLF", "WFC": "XLF", "GS": "XLF", "MS": "XLF",
    # 工業（XLI）
    "CAT": "XLI", "BA": "XLI", "HON": "XLI", "UNP": "XLI", "GE": "XLI",
}

# 中文標籤（報表顯示用）
SECTOR_LABELS: dict[str, str] = {
    "index": "指數ETF", "XLK": "科技", "XLC": "通訊服務", "XLY": "非必需消費",
    "XLE": "能源", "XLF": "金融", "XLI": "工業", "XLV": "醫療", "XLP": "必需消費",
    "XLB": "原物料", "XLU": "公用事業", "XLRE": "房地產", "unknown": "未知",
}

# yfinance 的英文 sector 名 → 我們的 ETF key（補洞用）
_YF_SECTOR_MAP = {
    "Technology": "XLK", "Communication Services": "XLC",
    "Consumer Cyclical": "XLY", "Consumer Defensive": "XLP",
    "Energy": "XLE", "Financial Services": "XLF", "Industrials": "XLI",
    "Healthcare": "XLV", "Basic Materials": "XLB", "Utilities": "XLU",
    "Real Estate": "XLRE",
}


def sector_of(symbol: str) -> str:
    """
    查一檔股票的 sector key。手工 dict 優先；沒有才問 yfinance（網路查詢，
    失敗/查不到回 "unknown"——誠實缺值，不猜）。
    """
    sym = symbol.upper()
    if sym in SECTOR_BY_SYMBOL:
        return SECTOR_BY_SYMBOL[sym]
    try:
        import yfinance as yf
        info = yf.Ticker(sym).info or {}
        return _YF_SECTOR_MAP.get(info.get("sector"), "unknown")
    except Exception:
        return "unknown"


def sector_label(key: str) -> str:
    """sector key → 中文標籤（找不到回原 key，不壞報表）。"""
    return SECTOR_LABELS.get(key, key)
