"""
SNR 3.0 支撐阻力精準進場策略（Supply & Demand + Structure Confirmation）
=====================================================================
供需區 + 新鮮度過濾 + 多重確認的支撐阻力策略。

核心概念（詳見 docs/reference/strategies/snr_3_0.md）：
1. Fresh Zone：找「第一次（或很少）被回踩」的支撐/阻力區——以 swing low/high 為錨、
   ATR 決定寬度。碰越多次越可能是流動性陷阱，不再新鮮。
2. 左側爆發：有效區域必須曾以 Expansion（大實體）或 Engulfing（吞噬）強勢離開，
   代表市場可能在該處留下機構資金痕跡。
3. 進場序列：價格回踩 Fresh Zone 後，需依序出現
   Rejection（影線拒絕）→ Confirmation（反轉確認）→ Structure Break（結構突破），
   且 Structure Break 落在「當根」才發出訊號——其餘時點一律 HOLD。

防偷看未來：
- swing 的右側需 swing_window 根確認 → 延遲 swing_window 根才「認定」該 swing
  （用的是當下已知的歷史，合法）；絕不用未來根回頭確認當根。
- 所有判定只用已收盤 K 棒；成交由回測引擎於次根開盤處理，策略不碰成交價。

v1 範圍界線：
- 單一 OHLCV DataFrame（日線可回測），不做真 H4/M30/M1 多時間框架。
- 必須有 open/high/low 欄（影線/吞噬判定離不開），缺欄回 HOLD。
- SELL 訊號在回測 allow_short=True 下＝開空評估；實盤 Bot 只做多（SELL 只平多）。
"""

import pandas as pd

from backend.strategies.base import BaseStrategy, Signal


class Snr30Strategy(BaseStrategy):
    name = "snr_3_0"

    # HOLD 原因的「進度等級」：兩側掃描各自回報走到哪一步，取進度最深的原因給人看，
    # 幫助理解目前缺哪個條件（也是回測 0 交易時 debug 的線索）。
    _P_NO_ZONE = 0      # 尚未找到有效 Fresh Zone
    _P_STALE = 1        # 有 zone 但已被多次觸碰（Fresh 失效）
    _P_NO_RETEST = 2    # 有 Fresh Zone，價格尚未回踩
    _P_NO_REJECT = 3    # 已回踩，尚未出現 Rejection
    _P_NO_CONFIRM = 4   # 有 Rejection，尚未出現 Confirmation
    _P_NO_BREAK = 5     # 有 Confirmation，尚未結構突破

    def generate_signal(self, df: pd.DataFrame) -> tuple[str, str]:
        p = self.params
        zone_lookback = int(p.get("zone_lookback", 80))
        swing_window = int(p.get("swing_window", 3))
        atr_period = int(p.get("atr_period", 14))
        zone_atr_width = float(p.get("zone_atr_width", 0.5))
        touch_tolerance_atr = float(p.get("touch_tolerance_atr", 0.2))
        max_touches = int(p.get("max_touches", 1))
        expansion_body_mult = float(p.get("expansion_body_mult", 1.5))
        expansion_lookback = int(p.get("expansion_lookback", 20))
        rejection_wick_ratio = float(p.get("rejection_wick_ratio", 0.4))
        structure_break_lookback = int(p.get("structure_break_lookback", 5))
        reward_r = float(p.get("reward_r", 2.0))
        atr_buffer = float(p.get("atr_buffer", 0.2))
        allow_short = bool(p.get("allow_short", True))

        need = zone_lookback + atr_period + swing_window + 1
        if len(df) < need:
            return Signal.HOLD, f"資料不足（需要至少 {need} 筆）"
        # 影線/吞噬/實體判定離不開 open/high/low，缺欄無法退化成 close-only
        for col in ("open", "high", "low", "close"):
            if col not in df.columns:
                return Signal.HOLD, f"缺少 {col} 欄位（SNR 3.0 需要完整 OHLC）"

        # 只切工作視窗計算（控制逐根重算成本），轉 numpy 陣列加速索引
        w = df.tail(need).reset_index(drop=True)
        o = w["open"].to_numpy(dtype=float)
        h = w["high"].to_numpy(dtype=float)
        l = w["low"].to_numpy(dtype=float)
        c = w["close"].to_numpy(dtype=float)
        n = len(w)
        last = n - 1

        # ATR（純 pandas：TR = max(高低差, |高-昨收|, |低-昨收|) 的滾動平均）
        prev_close = w["close"].shift(1)
        tr = pd.concat(
            [w["high"] - w["low"],
             (w["high"] - prev_close).abs(),
             (w["low"] - prev_close).abs()],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(atr_period).mean().to_numpy(dtype=float)

        # 平均實體（不含當根：shift(1)，避免大 K 棒拉高自己的門檻）
        body = (w["close"] - w["open"]).abs()
        avg_body = body.rolling(expansion_lookback).mean().shift(1).to_numpy(dtype=float)
        body = body.to_numpy(dtype=float)

        def is_bullish_expansion(k: int) -> bool:
            """陽線且實體 > 近 expansion_lookback 根平均實體 × 倍數。"""
            ab = avg_body[k]
            return c[k] > o[k] and ab == ab and body[k] > ab * expansion_body_mult  # ab==ab 排 NaN

        def is_bearish_expansion(k: int) -> bool:
            ab = avg_body[k]
            return c[k] < o[k] and ab == ab and body[k] > ab * expansion_body_mult

        def is_bullish_engulfing(k: int) -> bool:
            """前根空方 K、當根多方 K，且當根實體完整包住前根實體。"""
            if k < 1:
                return False
            return (c[k - 1] < o[k - 1] and c[k] > o[k]
                    and o[k] <= c[k - 1] and c[k] >= o[k - 1])

        def is_bearish_engulfing(k: int) -> bool:
            if k < 1:
                return False
            return (c[k - 1] > o[k - 1] and c[k] < o[k]
                    and o[k] >= c[k - 1] and c[k] <= o[k - 1])

        # swing 偵測：j 的左右各 swing_window 根都「嚴格」更高/更低才算（嚴格比較，
        # 平盤不會人人都是 swing）。右側確認 → 只認定 j <= last - swing_window 的 bar。
        sw = swing_window
        j_lo_bound = max(sw, n - zone_lookback, atr_period)  # zone 只在回看範圍內找，且 ATR 要算得出
        swing_lows = [
            j for j in range(j_lo_bound, n - sw)
            if l[j] < min(l[j - sw:j]) and l[j] < min(l[j + 1:j + sw + 1])
        ]
        swing_highs = [
            j for j in range(j_lo_bound, n - sw)
            if h[j] > max(h[j - sw:j]) and h[j] > max(h[j + 1:j + sw + 1])
        ]

        # rejection 必須落在「最近 scan_window 根」內（序列在當根收尾，太久前的拒絕不算數）
        scan_window = structure_break_lookback + 2

        def scan_side(is_long: bool) -> tuple[int, str | None]:
            """
            掃一側（多/空）的完整進場序列。回 (進度等級, 訊號原因或 None)。
            原因不為 None 代表七步序列在當根完成，可發訊號。
            """
            progress = self._P_NO_ZONE
            anchors = swing_lows if is_long else swing_highs
            # 由最近的 swing 往回找：最近的區域最可能是「當前這波回踩」的目標
            for j in reversed(anchors):
                a = atr[j]
                if a != a or a <= 0:  # NaN 或無波動 → 這個錨算不出 zone
                    continue
                if is_long:
                    zone_lo, zone_hi = l[j], l[j] + zone_atr_width * a
                else:
                    zone_lo, zone_hi = h[j] - zone_atr_width * a, h[j]
                tol = touch_tolerance_atr * a
                zone_mid = (zone_lo + zone_hi) / 2.0

                # --- 2a. 離開驗證：swing 確認後 expansion_lookback 根內，須以爆發/吞噬離開 zone ---
                k_depart = None
                for k in range(j + 1, min(j + 1 + expansion_lookback, n)):
                    if is_long and c[k] > zone_hi and (
                            is_bullish_expansion(k) or is_bullish_engulfing(k)):
                        k_depart = k
                        break
                    if not is_long and c[k] < zone_lo and (
                            is_bearish_expansion(k) or is_bearish_engulfing(k)):
                        k_depart = k
                        break
                if k_depart is None:
                    continue  # 左側無爆發 → 非有效 zone，試下一個 swing

                def touched(t: int) -> bool:
                    """第 t 根是否觸碰 zone（含容忍範圍）。多頭看 low 下探、空頭看 high 上探。"""
                    if is_long:
                        return l[t] <= zone_hi + tol
                    return h[t] >= zone_lo - tol

                # --- 3. 當根往回掃序列完成度（rejection → confirmation → structure break）---
                # 先找「最近 scan_window 根內」的 rejection（觸碰 + 影線拒絕 + 收回 zone_mid 之上/下）
                r_idx = None
                for t in range(max(k_depart + 1, last - scan_window), last + 1):
                    if not touched(t):
                        continue
                    rng = h[t] - l[t]
                    if rng <= 0:
                        continue  # 一字線防除零
                    if is_long:
                        lower_wick = min(o[t], c[t]) - l[t]
                        if lower_wick >= rng * rejection_wick_ratio and c[t] > zone_mid:
                            r_idx = t
                            break
                    else:
                        upper_wick = h[t] - max(o[t], c[t])
                        if upper_wick >= rng * rejection_wick_ratio and c[t] < zone_mid:
                            r_idx = t
                            break

                # --- 2b. touch 計數：離開後、到「當前回踩群開始前」的歷史觸碰群數。
                # ★當前這波回踩自己不算（否則永遠 stale）；連續 in-zone 根合併算同一群。---
                if r_idx is not None:
                    grp_start = r_idx
                    while grp_start - 1 > k_depart and touched(grp_start - 1):
                        grp_start -= 1
                    count_until = grp_start  # 歷史觸碰只數到當前回踩群開始前
                else:
                    count_until = last + 1   # 還沒回踩 → 全部都算歷史
                hist_touches = 0
                in_group = False
                for t in range(k_depart + 1, count_until):
                    if touched(t):
                        if not in_group:
                            hist_touches += 1
                            in_group = True
                    else:
                        in_group = False
                if hist_touches >= max_touches:
                    progress = max(progress, self._P_STALE)
                    continue  # 不新鮮 → 試下一個 swing

                if r_idx is None:
                    # zone 新鮮但序列未開始：分「還沒回踩」與「回踩了但無拒絕」
                    recently_touched = any(
                        touched(t) for t in range(max(k_depart + 1, last - scan_window), last + 1)
                    )
                    progress = max(
                        progress,
                        self._P_NO_REJECT if recently_touched else self._P_NO_RETEST,
                    )
                    continue

                # confirmation：rejection 當根或其後，出現順向吞噬或順向爆發
                cf_idx = None
                for t in range(r_idx, last + 1):
                    if is_long and (is_bullish_engulfing(t) or is_bullish_expansion(t)):
                        cf_idx = t
                        break
                    if not is_long and (is_bearish_engulfing(t) or is_bearish_expansion(t)):
                        cf_idx = t
                        break
                if cf_idx is None:
                    progress = max(progress, self._P_NO_CONFIRM)
                    continue

                # structure break：必須在「當根」收盤突破/跌破前 structure_break_lookback 根極值
                sbl = structure_break_lookback
                if is_long:
                    broke = c[last] > max(h[last - sbl:last])
                else:
                    broke = c[last] < min(l[last - sbl:last])
                if not broke:
                    progress = max(progress, self._P_NO_BREAK)
                    continue

                # --- 七步全過：算參考停損/目標（只寫進 reason 供人看，出場由引擎/反向訊號負責）---
                entry = c[last]
                a_now = atr[last] if atr[last] == atr[last] else a
                if is_long:
                    stop = zone_lo - atr_buffer * a_now
                    if entry <= stop:
                        continue  # 風險距離不合理（進場價已低於停損）
                    target = entry + reward_r * (entry - stop)
                    return progress, (
                        f"SNR 3.0 多頭：Fresh Support {zone_lo:.2f}~{zone_hi:.2f} 回踩"
                        f" + 拒絕 + 多頭確認 + 結構突破"
                        f"（參考停損 {stop:.2f}／目標 {target:.2f}，{reward_r:.1f}R）"
                    )
                stop = zone_hi + atr_buffer * a_now
                if entry >= stop:
                    continue
                target = entry - reward_r * (stop - entry)
                return progress, (
                    f"SNR 3.0 空頭：Fresh Resistance {zone_lo:.2f}~{zone_hi:.2f} 回測"
                    f" + 拒絕 + 空頭確認 + 結構跌破"
                    f"（參考停損 {stop:.2f}／目標 {target:.2f}，{reward_r:.1f}R）"
                )
            return progress, None

        long_progress, long_reason = scan_side(is_long=True)
        if long_reason is not None:
            return Signal.BUY, long_reason

        if allow_short:
            short_progress, short_reason = scan_side(is_long=False)
            if short_reason is not None:
                return Signal.SELL, short_reason
        else:
            short_progress = self._P_NO_ZONE

        # 兩側都沒完成序列 → 依「進度最深」的一側給 HOLD 原因（缺哪個條件講清楚）
        hold_msgs = {
            self._P_NO_ZONE: "尚未找到有效 Fresh Zone",
            self._P_STALE: "Zone 已被多次觸碰，Fresh 條件失效",
            self._P_NO_RETEST: "已找到 Fresh Zone，價格尚未回踩",
            self._P_NO_REJECT: "已回踩 Zone，但尚未出現 Rejection",
            self._P_NO_CONFIRM: "有 Rejection，但尚未出現 Confirmation",
            self._P_NO_BREAK: "有 Confirmation，但尚未結構突破",
        }
        return Signal.HOLD, hold_msgs[max(long_progress, short_progress)]
