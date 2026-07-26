"""
SNR 3.0 供需區策略單元測試
==========================
手構 OHLC 假資料驗證 BUY / SELL / HOLD 三情境 + touch 計數陷阱，完全不需連線。

BUY 資料是一齣 38 根的「六幕劇」（用縮小參數壓短資料）：
  幕A bar0-24 ：平盤暖機（建立 ATR 與平均實體基準）
  幕B bar25-27：下跌打底，bar27 low=105.0 是 swing low（需求區錨點）
  幕C bar28-29：右側回升 2 根 → swing low 於 bar29 起「已知」（右側確認，合法延遲）
  幕D bar28   ：多頭吞噬收離 zone 上緣（左側爆發離開 → zone 有效）
  幕E bar29-34：走遠橫盤，low 全程不觸碰 zone（保持 Fresh、零歷史觸碰）
  幕F bar35-37：bar35 錘子刺入 zone（Rejection）→ bar36 多頭吞噬（Confirmation）
               → bar37 收盤突破前 3 根高點（Structure Break）→ 當根發 BUY

SELL 資料 = BUY 資料以 220 為軸上下鏡像（o'=220-o、c'=220-c、h'=220-l、l'=220-h），
鎖住多空邏輯完全對稱。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_snr_3_0.py -q
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

from backend.strategies import get_strategy
from backend.strategies.base import Signal
from backend.strategies.snr_3_0 import Snr30Strategy

# 縮小參數壓短測試資料（need = 30 + 3 + 2 + 1 = 36 根）
PARAMS = {
    "zone_lookback": 30,
    "swing_window": 2,
    "atr_period": 3,
    "expansion_lookback": 5,
    "structure_break_lookback": 3,
}


def _buy_df() -> pd.DataFrame:
    """六幕劇 BUY 資料（38 根，見檔頭說明）。zone=[105.00, 105.95]、觸碰帶上緣≈106.33。"""
    o, h, l, c = [], [], [], []

    def bar(o_, h_, l_, c_):
        o.append(o_); h.append(h_); l.append(l_); c.append(c_)

    for _ in range(25):                     # 幕A 暖機平盤
        bar(109.8, 110.5, 109.5, 110.2)
    bar(110.0, 110.0, 108.0, 108.0)         # 25 幕B 下跌
    bar(108.0, 108.0, 105.5, 106.0)         # 26
    bar(106.0, 106.0, 105.0, 105.5)         # 27 ★swing low（zone 錨點）
    bar(105.5, 106.6, 105.4, 106.5)         # 28 幕C/D 多頭吞噬、收離 zone 上緣（爆發離開）
    bar(106.5, 107.2, 106.5, 107.0)         # 29（右側確認完成，low 不觸碰）
    bar(107.0, 107.6, 106.9, 107.5)         # 30 幕E 走遠橫盤（全程零觸碰 → Fresh）
    bar(107.5, 108.0, 107.3, 107.8)         # 31
    bar(107.8, 108.0, 107.2, 107.5)         # 32
    bar(107.5, 107.8, 107.2, 107.6)         # 33
    bar(107.5, 107.5, 106.5, 106.6)         # 34 回落逼近 zone（尚未觸碰）
    bar(106.45, 106.5, 105.2, 106.35)       # 35 幕F 錘子：low 刺入 zone、下影/全距≈0.88（Rejection）
    bar(106.3, 107.7, 106.2, 107.6)         # 36 多頭吞噬 bar35（Confirmation）
    bar(107.6, 108.3, 107.5, 108.2)         # 37 收盤 108.2 > 前 3 根最高 107.7（Structure Break→BUY）
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c})


def _mirror(df: pd.DataFrame, axis: float = 220.0) -> pd.DataFrame:
    """上下鏡像：多頭情境變成完全對稱的空頭情境（high/low 互換）。"""
    return pd.DataFrame({
        "open": axis - df["open"],
        "high": axis - df["low"],
        "low": axis - df["high"],
        "close": axis - df["close"],
    })


def test_buy_full_sequence():
    """七步序列在最後一根完成 → 回 BUY。"""
    strategy = Snr30Strategy(PARAMS)
    signal, reason = strategy.generate_signal(_buy_df())
    assert signal == Signal.BUY, f"預期 buy，實際 {signal}（{reason}）"
    assert "多頭" in reason, reason
    print(f"✅ BUY 測試通過：{reason}")


def test_no_early_signal_before_structure_break():
    """同一份資料截到倒數第 2 根（結構未突破）→ 必須還是 HOLD（驗不提早發訊）。"""
    strategy = Snr30Strategy(PARAMS)
    df = _buy_df().iloc[:-1]  # 截掉 bar37：Rejection/Confirmation 都有了、就差結構突破
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.HOLD, f"預期 hold，實際 {signal}（{reason}）"
    assert "結構" in reason, reason  # 進度追蹤應指出「缺結構突破」
    print(f"✅ 不提早發訊測試通過：{reason}")


def test_sell_full_sequence_mirror():
    """BUY 資料上下鏡像 → 空頭七步序列 → 回 SELL（鎖多空邏輯完全對稱）。"""
    strategy = Snr30Strategy(PARAMS)
    signal, reason = strategy.generate_signal(_mirror(_buy_df()))
    assert signal == Signal.SELL, f"預期 sell，實際 {signal}（{reason}）"
    assert "空頭" in reason, reason
    print(f"✅ SELL（鏡像）測試通過：{reason}")


def test_allow_short_false_no_sell():
    """allow_short=False → 同一份空頭資料只回 HOLD（不產做空訊號）。"""
    strategy = Snr30Strategy({**PARAMS, "allow_short": False})
    signal, reason = strategy.generate_signal(_mirror(_buy_df()))
    assert signal == Signal.HOLD, f"預期 hold，實際 {signal}（{reason}）"
    print("✅ allow_short=False 不做空測試通過")


def test_stale_zone_blocks_buy():
    """
    ★touch 計數陷阱鎖定：走遠期間（bar31）low 刺入 zone 一次 = 1 個歷史觸碰群
    → 到 bar35 這波已是第 2 次回踩 → Fresh 失效（max_touches=1）→ 不得發 BUY。
    若把「當前回踩」誤算進 touch 數，或漏數歷史觸碰，這條會抓到。
    """
    df = _buy_df()
    # bar31 改成下影刺入 zone（low 105.8 ≤ 觸碰帶 106.33）後收回
    df.loc[31, ["open", "high", "low", "close"]] = [107.5, 107.6, 105.8, 107.3]
    strategy = Snr30Strategy(PARAMS)
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.HOLD, f"stale zone 不該進場，實際 {signal}（{reason}）"
    print(f"✅ stale zone 擋單測試通過：{reason}")


def test_hold_insufficient_data():
    """資料不足 → HOLD，不丟例外。"""
    strategy = Snr30Strategy(PARAMS)
    df = pd.DataFrame({"open": [10] * 10, "high": [10] * 10,
                       "low": [10] * 10, "close": [10] * 10})
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.HOLD, f"預期 hold，實際 {signal}"
    assert "資料不足" in reason, reason
    print("✅ 資料不足 HOLD 測試通過")


def test_hold_flat_market_no_zone():
    """純平盤（無 swing、無波動）→ 找不到 Fresh Zone → HOLD。"""
    strategy = Snr30Strategy(PARAMS)
    df = pd.DataFrame({"open": [100.0] * 40, "high": [100.0] * 40,
                       "low": [100.0] * 40, "close": [100.0] * 40})
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.HOLD, f"預期 hold，實際 {signal}（{reason}）"
    print(f"✅ 平盤無 zone HOLD 測試通過：{reason}")


def test_hold_missing_ohlc_columns():
    """只有 close 欄（缺 open/high/low）→ HOLD，不丟例外（本策略不能退化 close-only）。"""
    strategy = Snr30Strategy(PARAMS)
    df = pd.DataFrame({"close": [100.0 + i * 0.1 for i in range(40)]})
    signal, reason = strategy.generate_signal(df)
    assert signal == Signal.HOLD, f"預期 hold，實際 {signal}"
    print("✅ 缺 OHLC 欄 HOLD 測試通過")


def test_get_strategy_instantiation():
    """get_strategy 能用預設參數建立實例（註冊表接通）。"""
    strategy = get_strategy("snr_3_0", {})
    assert isinstance(strategy, Snr30Strategy)
    assert strategy.name == "snr_3_0"
    print("✅ get_strategy 實例化測試通過")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
