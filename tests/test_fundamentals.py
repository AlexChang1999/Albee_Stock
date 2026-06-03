"""
基本面 / 財報 / 新聞 ── 純函式測試
==================================
只測「清洗轉換」的純函式（_clean / _statement_to_records / _normalize_news），
餵假資料、不連網，驗證輸出可安全轉成 JSON 且格式一致。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe tests\\test_fundamentals.py
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import math

import numpy as np
import pandas as pd

from backend.services.fundamentals import (
    _clean,
    _statement_to_records,
    _normalize_news,
)


def test_clean_handles_nan_and_inf():
    """NaN / 無限大 → None（JSON 不接受這兩種）。"""
    assert _clean(float("nan")) is None
    assert _clean(math.inf) is None
    assert _clean(None) is None
    print("✅ NaN/inf/None 清成 None 通過")


def test_clean_converts_numpy_and_timestamp():
    """numpy 數字 → 原生型別；Timestamp → ISO 日期字串。"""
    assert _clean(np.int64(42)) == 42
    assert isinstance(_clean(np.float64(3.5)), float)
    assert _clean(pd.Timestamp("2026-03-31")) == "2026-03-31"
    assert _clean("Apple Inc.") == "Apple Inc."  # 字串原樣
    print("✅ numpy/Timestamp/字串 轉換通過")


def test_statement_to_records():
    """財報 DataFrame（科目當列、期間當欄）→ 每期一筆，NaN 變 None。"""
    df = pd.DataFrame(
        {
            pd.Timestamp("2025-09-30"): [100.0, float("nan")],
            pd.Timestamp("2024-09-30"): [90.0, 5.0],
        },
        index=["Total Revenue", "Net Income"],
    )
    records = _statement_to_records(df)
    assert len(records) == 2, records
    assert records[0]["period"] == "2025-09-30", records[0]
    assert records[0]["items"]["Total Revenue"] == 100.0
    assert records[0]["items"]["Net Income"] is None  # NaN → None
    print("✅ 財報轉每期一筆通過")


def test_statement_to_records_empty():
    """空 DataFrame → 空 list。"""
    assert _statement_to_records(pd.DataFrame()) == []
    print("✅ 空財報 → 空 list 通過")


def test_normalize_news_new_shape():
    """yfinance 新版新聞結構（包在 content 裡）應正確攤平。"""
    raw = [
        {
            "content": {
                "title": "Apple 發表新品",
                "provider": {"displayName": "Reuters"},
                "canonicalUrl": {"url": "https://news/1"},
                "pubDate": "2026-06-01T10:00:00Z",
            }
        }
    ]
    out = _normalize_news(raw)
    assert out[0]["title"] == "Apple 發表新品"
    assert out[0]["publisher"] == "Reuters"
    assert out[0]["link"] == "https://news/1"
    print("✅ 新版新聞結構通過")


def test_normalize_news_old_shape():
    """yfinance 舊版新聞結構（欄位在最外層）也要能接。"""
    raw = [
        {
            "title": "TSLA 財報",
            "publisher": "Yahoo",
            "link": "https://news/2",
            "providerPublishTime": 1717228800,
        }
    ]
    out = _normalize_news(raw)
    assert out[0]["title"] == "TSLA 財報"
    assert out[0]["publisher"] == "Yahoo"
    assert out[0]["link"] == "https://news/2"
    print("✅ 舊版新聞結構通過")


if __name__ == "__main__":
    test_clean_handles_nan_and_inf()
    test_clean_converts_numpy_and_timestamp()
    test_statement_to_records()
    test_statement_to_records_empty()
    test_normalize_news_new_shape()
    test_normalize_news_old_shape()
    print("\n🎉 全部基本面純函式測試通過！")
