"""
決策脈絡擷取純函式測試
======================
驗證 services/decision_context 的三個純函式：
- compute_market_snapshot：均線位置 / 排列 / 量能狀態 / 資料不足 / 空輸入。
- classify_exit_kind：止損 vs 追蹤止損 vs 止盈 vs 券商端 vs 策略反轉（關鍵字互含的判斷順序）。
- build_thesis_breach：買入假設失效 / 達標回填（物件與 dict 兩種 entry_log、缺欄位容錯）。

不連網、不碰 DB。執行（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_decision_context.py -q
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from backend.services.decision_context import (
    compute_market_snapshot,
    classify_exit_kind,
    build_thesis_breach,
)
from backend.models.decision_log import (
    EXIT_KIND_STOP_LOSS,
    EXIT_KIND_TAKE_PROFIT,
    EXIT_KIND_TRAILING,
    EXIT_KIND_SIGNAL_REVERSAL,
    EXIT_KIND_BROKER_SETTLED,
)


def _df(closes, vols=None):
    n = len(closes)
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="D"),
        "close": closes,
        "volume": vols if vols is not None else [1_000_000.0] * n,
    })


# ---------- compute_market_snapshot ----------

def test_snapshot_uptrend_bull_stack():
    """遞增收盤（上升趨勢）→ 多頭排列、現價在各均線上方。"""
    snap = compute_market_snapshot(_df([100.0 + i for i in range(80)]))
    assert snap is not None
    assert snap["ma_stack"] == "多頭排列"          # ma5 > ma20 > ma60
    assert snap["price_vs_ma20_pct"] > 0           # 現價在 20 日均上方
    assert {"ma5", "ma20", "ma60"} <= snap.keys()


def test_snapshot_downtrend_bear_stack():
    """遞減收盤 → 空頭排列、現價在均線下方。"""
    snap = compute_market_snapshot(_df([200.0 - i for i in range(80)]))
    assert snap["ma_stack"] == "空頭排列"
    assert snap["price_vs_ma20_pct"] < 0


def test_snapshot_volume_spike_state():
    """最後一根爆量 → vol_ratio 高、vol_state=爆量。"""
    closes = [100.0 + i for i in range(40)]
    vols = [1_000_000.0] * 39 + [3_000_000.0]
    snap = compute_market_snapshot(_df(closes, vols))
    assert snap["vol_ratio"] > 2.0
    assert snap["vol_state"] == "爆量"


def test_snapshot_short_df_omits_long_ma():
    """只有 10 根 → 算得出 ma5，但 ma20/ma60 省略，不報錯。"""
    snap = compute_market_snapshot(_df([100.0 + i for i in range(10)]))
    assert "ma5" in snap
    assert "ma20" not in snap and "ma60" not in snap
    assert "ma_stack" not in snap                  # 三條不齊不判排列


def test_snapshot_empty_or_none():
    assert compute_market_snapshot(None) is None
    assert compute_market_snapshot(pd.DataFrame()) is None


# ---------- classify_exit_kind ----------

def test_exit_kind_stop_loss():
    assert classify_exit_kind("止損 -5.0%（現價 228.00 ≤ 228.00）") == EXIT_KIND_STOP_LOSS


def test_exit_kind_trailing_not_confused_with_stop_loss():
    """『追蹤止損』含『止損』二字，必須先判成 trailing 而非 stop_loss。"""
    assert classify_exit_kind("追蹤止損 -3.0%（從最高 250.00 回落）") == EXIT_KIND_TRAILING


def test_exit_kind_take_profit():
    assert classify_exit_kind("止盈 +10.0%（現價 264.00 ≥ 264.00）") == EXIT_KIND_TAKE_PROFIT


def test_exit_kind_broker_settled_precedence():
    """券商端回填語句含『止損』，必須先判成 broker_settled。"""
    r = "券商端止損/追蹤止損觸發（託管單成交，本機回填）"
    assert classify_exit_kind(r) == EXIT_KIND_BROKER_SETTLED


def test_exit_kind_signal_reversal_default():
    assert classify_exit_kind("死亡交叉，均線翻空") == EXIT_KIND_SIGNAL_REVERSAL
    assert classify_exit_kind(None) is None


# ---------- build_thesis_breach ----------

class _Entry:
    def __init__(self, price, target_price, stop_price, created_at):
        self.price = price
        self.target_price = target_price
        self.stop_price = stop_price
        self.created_at = created_at


def test_thesis_none_entry():
    assert build_thesis_breach(None, 100.0, EXIT_KIND_STOP_LOSS) is None


def test_thesis_stop_loss_points_to_failed_assumption():
    entry = _Entry(240.0, 264.0, 228.0, datetime(2026, 6, 1))
    msg = build_thesis_breach(entry, 228.0, EXIT_KIND_STOP_LOSS, exit_time=datetime(2026, 6, 4))
    assert "跌破預設停損" in msg
    assert "$228.00" in msg
    assert "未達" in msg and "$264.00" in msg       # 點出當初預期目標未達
    assert "進場 $240.00" in msg
    assert "持有 3 天" in msg


def test_thesis_take_profit_records_success():
    entry = _Entry(240.0, 264.0, 228.0, datetime(2026, 6, 1))
    msg = build_thesis_breach(entry, 264.0, EXIT_KIND_TAKE_PROFIT, exit_time=datetime(2026, 6, 6))
    assert "達成預設停利目標" in msg
    assert "+10.0%" in msg


def test_thesis_signal_reversal_lists_untouched_levels():
    entry = _Entry(240.0, 264.0, 228.0, datetime(2026, 6, 1))
    msg = build_thesis_breach(entry, 237.0, EXIT_KIND_SIGNAL_REVERSAL, exit_time=datetime(2026, 6, 2))
    assert "策略訊號反轉出場" in msg
    assert "未觸及" in msg
    assert "持有 1 天" in msg


def test_thesis_accepts_dict_and_missing_fields():
    """entry_log 用 dict、且缺 target/stop → 不報錯，省略相關片語。"""
    entry = {"price": 50.0, "target_price": None, "stop_price": None,
             "created_at": datetime(2026, 6, 1)}
    msg = build_thesis_breach(entry, 47.5, EXIT_KIND_STOP_LOSS, exit_time=datetime(2026, 6, 1, 5))
    assert "跌破預設停損" in msg
    assert "進場 $50.00" in msg
    assert "未達" not in msg                         # 沒 target 就不提「未達」
    assert "持有不到 1 天" in msg
