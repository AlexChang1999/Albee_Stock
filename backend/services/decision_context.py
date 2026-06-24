"""
決策脈絡擷取（decision context）
================================
把「結構化交易日誌」需要、但程式在決策當下其實算得出來的脈絡，集中成幾個純函式：

1. compute_market_snapshot(df)：決策當下的市場快照——5/20/60 日均線位置 + 量能狀態。
   與圖表/指標同一套 pandas（收盤均線、均量倍數），故畫面看到的線末端值＝這裡記下的數字。
2. classify_exit_kind(reason)：把賣出 reason 字串對應到機器可讀的出場類型（EXIT_KIND_*）。
   讓週報/月報能統計「止損 vs 停利 vs 策略反轉各佔多少、各自平均盈虧」。
3. build_thesis_breach(entry_log, ...)：賣出時回填「哪個買入假設失效」——撈最近一筆買進的
   target/stop/進場價，跟這次出場價/原因對照，產一句給人 + LLM 檢討看的結構化說明。

全部純函式、不碰 DB / 不發 IO，呼叫端（bot_manager）負責準備資料（df、撈買入紀錄）。
算不出時一律回 None / 空，絕不可拋例外中斷交易主流程。
"""

from datetime import datetime

import pandas as pd

from backend.models.decision_log import (
    EXIT_KIND_STOP_LOSS,
    EXIT_KIND_TAKE_PROFIT,
    EXIT_KIND_TRAILING,
    EXIT_KIND_SIGNAL_REVERSAL,
    EXIT_KIND_BROKER_SETTLED,
)


# ---------- 1. 市場快照 ----------

def _vol_state(ratio: float) -> str:
    """量能倍數（當根量 / 20 日均量）→ 人話狀態。門檻取常見直覺值。"""
    if ratio >= 2.0:
        return "爆量"
    if ratio >= 1.3:
        return "放量"
    if ratio <= 0.7:
        return "量縮"
    return "正常"


def compute_market_snapshot(df: pd.DataFrame | None) -> dict | None:
    """決策當下的市場快照：均線位置（5/20/60）+ 量能狀態。

    回傳 dict（資料不足的項自動省略），例如：
    {
      "price": 240.5,
      "ma5": 238.1, "ma20": 232.4, "ma60": 225.0,
      "price_vs_ma5_pct": 1.01, "price_vs_ma20_pct": 3.49, "price_vs_ma60_pct": 6.89,
      "ma_stack": "多頭排列",          # 5>20>60 多頭、5<20<60 空頭、其餘糾結
      "vol": 1234567.0, "vol_avg20": 980000.0, "vol_ratio": 1.26, "vol_state": "正常",
    }
    無 df / 無 close 欄 / 計算失敗 → None（不擋交易主流程）。
    註：大盤（SPY）趨勢需另抓行情，為免每輪多一次 API 呼叫，本函式不含；後續要時可加。
    """
    if df is None or getattr(df, "empty", True) or "close" not in df.columns:
        return None
    try:
        close = df["close"]
        price = float(close.iloc[-1])
        if pd.isna(price):
            return None
        snap: dict = {"price": round(price, 4)}

        # 各週期收盤均線 + 現價相對位置（%）。資料不足該週期就略過該項。
        for w in (5, 20, 60):
            if len(close) >= w:
                ma = float(close.rolling(window=w).mean().iloc[-1])
                if not pd.isna(ma):
                    snap[f"ma{w}"] = round(ma, 4)
                    if ma:
                        snap[f"price_vs_ma{w}_pct"] = round((price - ma) / ma * 100, 2)

        # 均線排列（要三條都有才判）
        ma5, ma20, ma60 = snap.get("ma5"), snap.get("ma20"), snap.get("ma60")
        if None not in (ma5, ma20, ma60):
            if ma5 > ma20 > ma60:
                snap["ma_stack"] = "多頭排列"
            elif ma5 < ma20 < ma60:
                snap["ma_stack"] = "空頭排列"
            else:
                snap["ma_stack"] = "糾結"

        # 量能狀態：當根量 vs 20 日均量
        if "volume" in df.columns:
            vol = float(df["volume"].iloc[-1])
            if not pd.isna(vol):
                snap["vol"] = round(vol, 2)
                if len(df["volume"]) >= 20:
                    vol_avg = float(df["volume"].rolling(window=20).mean().iloc[-1])
                    if not pd.isna(vol_avg) and vol_avg > 0:
                        ratio = vol / vol_avg
                        snap["vol_avg20"] = round(vol_avg, 2)
                        snap["vol_ratio"] = round(ratio, 2)
                        snap["vol_state"] = _vol_state(ratio)

        return snap or None
    except Exception:
        return None


# ---------- 2. 出場類型分類 ----------

def classify_exit_kind(reason: str | None) -> str | None:
    """賣出 reason 字串 → EXIT_KIND_*。

    對應 risk_manager 的出場原因字串與券商回填語句。判斷有順序（關鍵字會互含）：
      券商端（含「止損」字樣，最優先）→ 追蹤止損（含「止損」）→ 止損 → 止盈 → 其餘＝策略反轉。
    無 reason → None。
    """
    if not reason:
        return None
    r = str(reason)
    if "券商端" in r or "託管單" in r:
        return EXIT_KIND_BROKER_SETTLED
    if "追蹤止損" in r:
        return EXIT_KIND_TRAILING
    if "止損" in r:
        return EXIT_KIND_STOP_LOSS
    if "止盈" in r:
        return EXIT_KIND_TAKE_PROFIT
    return EXIT_KIND_SIGNAL_REVERSAL


# ---------- 3. 買入假設失效回填 ----------

def _num(obj, key: str) -> float | None:
    """從 DecisionLog 物件或 dict 取數值欄，容錯回 None。"""
    val = obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _format_holding(entry_time, exit_time) -> str:
    """持有時間人話：>=1 天記天數，否則「不到 1 天」。entry_time 缺則回空字串。"""
    if not entry_time:
        return ""
    exit_time = exit_time or datetime.now()
    try:
        days = (exit_time - entry_time).days
    except Exception:
        return ""
    return f"持有 {days} 天" if days >= 1 else "持有不到 1 天"


def build_thesis_breach(
    entry_log,
    exit_price: float | None,
    exit_kind: str | None,
    exit_time=None,
) -> str | None:
    """賣出時回填「哪個買入假設失效 / 達標」——對照最近一筆買進的 target/stop/進場價。

    :param entry_log: 最近一筆 bought 的 DecisionLog（或同欄位 dict）；None＝查無買進紀錄。
    :param exit_price: 這次出場價。
    :param exit_kind: 出場類型（EXIT_KIND_*）。
    :return: 一句結構化說明；無買進紀錄可對照時 None。

    虧損出場（止損/追蹤/反轉）會明確點出「當初預期漲抵 $target 未達」——
    符合規範「比對買入預期，指出哪個假設失效」。停利則記錄假設成立。
    """
    if entry_log is None:
        return None
    entry_price = _num(entry_log, "price")
    target = _num(entry_log, "target_price")
    stop = _num(entry_log, "stop_price")
    entry_time = entry_log.get("created_at") if isinstance(entry_log, dict) \
        else getattr(entry_log, "created_at", None)

    # 本回合報酬率（進場→出場）
    ret_str = ""
    if entry_price and exit_price:
        ret_pct = (exit_price - entry_price) / entry_price * 100
        ret_str = f"，{ret_pct:+.1f}%"
    entry_str = f"進場 ${entry_price:.2f}{ret_str}" if entry_price else ""

    # 主因（依出場類型）
    if exit_kind == EXIT_KIND_TAKE_PROFIT:
        head = "達成預設停利目標" + (f" ${target:.2f}" if target else "")
        tail = ""
    elif exit_kind == EXIT_KIND_STOP_LOSS:
        head = "跌破預設停損" + (f" ${stop:.2f}" if stop else "")
        tail = f"；當初預期漲抵 ${target:.2f} 未達" if target else ""
    elif exit_kind == EXIT_KIND_TRAILING:
        head = "自持倉高點回落，觸發追蹤止損"
        tail = f"；當初預期漲抵 ${target:.2f} 未達" if target else ""
    elif exit_kind == EXIT_KIND_BROKER_SETTLED:
        head = "券商端保護單成交出場"
        tail = ""
    else:  # signal_reversal 或未知
        head = "策略訊號反轉出場"
        bracket = []
        if target:
            bracket.append(f"停利 ${target:.2f}")
        if stop:
            bracket.append(f"停損 ${stop:.2f}")
        tail = f"；未觸及{'／'.join(bracket)}" if bracket else ""

    held = _format_holding(entry_time, exit_time)
    held_str = f"；{held}" if held else ""

    detail = f"（{entry_str}）" if entry_str else ""
    return f"{head}{detail}{tail}{held_str}"
