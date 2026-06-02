"""
風控（止盈 / 止損 / 追蹤止損）
==============================
判斷「現在這筆持倉該不該平倉出場」。

刻意設計成「純函式」：
- 只吃數字（進場價、現價、持倉期間最高價、各門檻百分比），回傳要不要出場。
- 完全不碰 Alpaca、不碰資料庫 → 超好寫單元測試，邏輯也好驗證。

三種出場機制（可各自開關，門檻為 None 就略過該條）：
1. 固定止損 stop_loss_pct：現價跌破「進場價 ×(1−門檻)」就出場。保本用。
2. 追蹤止損 trailing_stop_pct：現價從「持倉期間最高價」回落超過門檻就出場。
   特點是止損點會隨價格創新高往上抬，鎖住已經賺到的獲利。
3. 固定止盈 take_profit_pct：現價漲到「進場價 ×(1+門檻)」就出場。落袋為安。

判斷順序：止損 → 追蹤止損 → 止盈（保護優先於獲利）。
任何一條先成立就立刻回傳出場，不再往下判。

百分比都用小數表示：0.10 = 10%。
"""

from __future__ import annotations


def check_exit(
    entry_price: float,
    current_price: float,
    peak_price: float | None = None,
    *,
    take_profit_pct: float | None = None,
    stop_loss_pct: float | None = None,
    trailing_stop_pct: float | None = None,
) -> tuple[bool, str | None]:
    """
    判斷是否該平倉出場。

    :param entry_price: 進場（平均成本）價
    :param current_price: 目前市價
    :param peak_price: 持倉期間出現過的最高價（給追蹤止損用）；沒有就傳 None
    :param take_profit_pct: 固定止盈門檻（小數），None = 不啟用
    :param stop_loss_pct: 固定止損門檻（小數），None = 不啟用
    :param trailing_stop_pct: 追蹤止損門檻（小數），None = 不啟用
    :return: (要不要出場, 原因說明)。不出場時回 (False, None)
    """
    # 進場價或現價不合理（None、0、負數）就不做判斷，避免除錯誤的結論。
    if not entry_price or not current_price or entry_price <= 0:
        return False, None

    # 1) 固定止損：跌破停損價就出場（保本優先，最先判）
    if stop_loss_pct is not None:
        stop_price = entry_price * (1 - stop_loss_pct)
        if current_price <= stop_price:
            return True, f"止損 -{stop_loss_pct * 100:.1f}%（現價 {current_price:.2f} ≤ {stop_price:.2f}）"

    # 2) 追蹤止損：從持倉最高價回落超過門檻就出場
    if trailing_stop_pct is not None and peak_price:
        trail_price = peak_price * (1 - trailing_stop_pct)
        if current_price <= trail_price:
            return True, (
                f"追蹤止損 -{trailing_stop_pct * 100:.1f}%"
                f"（最高 {peak_price:.2f} → 現價 {current_price:.2f} ≤ {trail_price:.2f}）"
            )

    # 3) 固定止盈：漲到停利價就出場
    if take_profit_pct is not None:
        target_price = entry_price * (1 + take_profit_pct)
        if current_price >= target_price:
            return True, f"止盈 +{take_profit_pct * 100:.1f}%（現價 {current_price:.2f} ≥ {target_price:.2f}）"

    # 三條都沒成立 → 續抱
    return False, None
