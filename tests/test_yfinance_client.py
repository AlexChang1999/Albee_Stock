"""
yfinance 資料源單元測試
=======================
驗證 _normalize() 能把 yfinance 原始格式，正確轉成本專案統一契約。
完全不需連網（餵假資料進去）。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe tests\\test_yfinance_client.py
"""

import sys
from pathlib import Path

# Windows 主控台 cp950 印 emoji 會崩潰，強制改 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from backend.services.yfinance_client import _normalize


def _fake_yfinance_df():
    """造一份假的 yfinance Ticker.history() 輸出：日期當 index，欄位首字大寫。"""
    idx = pd.DatetimeIndex(
        ["2026-01-02", "2026-01-03", "2026-01-06"], name="Date"
    )
    return pd.DataFrame(
        {
            "Open": [10.0, 11.0, 12.0],
            "High": [10.5, 11.5, 12.5],
            "Low": [9.5, 10.5, 11.5],
            "Close": [10.2, 11.2, 12.2],
            "Volume": [1000, 1100, 1200],
            # 這兩欄是 yfinance 會多給、但我們用不到的，應被丟掉
            "Dividends": [0.0, 0.0, 0.0],
            "Stock Splits": [0.0, 0.0, 0.0],
        },
        index=idx,
    )


def test_normalize_columns_match_contract():
    """轉換後欄位應只剩契約定義的 6 欄，且名稱為小寫。"""
    out = _normalize(_fake_yfinance_df())
    assert list(out.columns) == ["timestamp", "open", "high", "low", "close", "volume"], out.columns
    # Dividends / Stock Splits 應被丟掉
    assert "Dividends" not in out.columns
    print("✅ 欄位契約測試通過：", list(out.columns))


def test_normalize_sorted_old_to_new():
    """轉換後資料應為「舊 → 新」排序，且 index 已重設為整數。"""
    out = _normalize(_fake_yfinance_df())
    assert out["timestamp"].is_monotonic_increasing, out["timestamp"]
    assert list(out.index) == [0, 1, 2], out.index
    # close 值應對得上原始資料
    assert out["close"].tolist() == [10.2, 11.2, 12.2], out["close"]
    print("✅ 排序與索引測試通過")


def test_normalize_empty_returns_empty():
    """餵空資料 → 回傳空 DataFrame（讓回測引擎的空檢查能運作）。"""
    out = _normalize(pd.DataFrame())
    assert out.empty, out
    print("✅ 空資料測試通過")


if __name__ == "__main__":
    test_normalize_columns_match_contract()
    test_normalize_sorted_old_to_new()
    test_normalize_empty_returns_empty()
    print("\n🎉 全部 yfinance 資料源測試通過！")
