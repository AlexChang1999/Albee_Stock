"""
掃盤頻率研究 CLI（2026-07 回測驗證日）
======================================
回答「check_interval_sec 該設 30 / 60 / 120 / 180 / 300 / 600 秒哪個？」——用數據，不用感覺。

★ 誠實前提（報告必讀）：
  本系統策略吃的是**日 K**（alpaca_client 硬編 TimeFrame.Day），訊號一天只變一次。
  掃頻完全**不影響進場時機**（無論 30s 或 600s 掃，都是同一根日 K 算出同一個訊號）。
  掃頻真正影響的只有兩件事：
  1. **風控出場延遲**：停損/停利/追蹤止損是逐輪比對現價觸發的，掃得慢 = 觸價後
     要等到下一輪才市價出場，期間價格繼續跑 = 額外滑價。
  2. **API 用量**：每輪每 Bot 至少一次資料請求，Alpaca 免費上限 200 req/min。

方法：
  - 抓股票池的**分鐘 K**（Alpaca IEX 免費、僅本腳本用，不動 live 日 K 路徑）近 N 天。
  - 每個「symbol × 交易日」模擬：開盤價進場，掛停損 −7%（對照艦隊建議風控），
    找出日內第一個觸價分鐘 t*；對每個掃描間隔 Δ，出場時點 = t* 之後第一個
    「從開盤起每 Δ 秒」的檢查 tick，額外滑價 =（觸價價 − tick 當下價格）。
    停利 +15% 同理（方向相反）。彙總各 Δ 的額外滑價分布（bps）。
  - API 用量：以目前 DB 的啟用 Bot 數（或 --bots 指定）算各 Δ 的 req/min 與限流餘裕。

只讀資料，不碰 DB 寫入、不下單。

用法：
    venv\\Scripts\\python.exe scripts\\scan_frequency_study.py --days 30
輸出：
    docs/reference/analysis-2026-07-02/scan-frequency.csv / scan-frequency.md
"""

import argparse
import csv
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd  # noqa: E402

from backend.config import settings  # noqa: E402

OUT_DIR = ROOT / "docs" / "reference" / "analysis-2026-07-02"

INTERVALS = [30, 60, 120, 180, 300, 600]  # 待比較的掃描間隔（秒）
STOP_LOSS = 0.07    # 模擬用風控參數（與 full_backtest_report 的對照組一致）
TAKE_PROFIT = 0.15


def fetch_minute_bars(symbols: list[str], days: int) -> pd.DataFrame:
    """抓分鐘 K（Alpaca IEX 免費源）。僅此研究腳本使用，不動 live 的日 K 路徑。"""
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    client = StockHistoricalDataClient(settings.ALPACA_API_KEY, settings.ALPACA_SECRET_KEY)
    end = datetime.now(timezone.utc) - timedelta(minutes=16)  # 免費版 15 分鐘延遲
    start = end - timedelta(days=days)
    req = StockBarsRequest(symbol_or_symbols=symbols, timeframe=TimeFrame.Minute,
                           start=start, end=end)
    bars = client.get_stock_bars(req)
    df = bars.df.reset_index()  # columns: symbol, timestamp, open high low close volume ...
    return df


def simulate_day(day_df: pd.DataFrame) -> list[dict]:
    """
    對單一 symbol × 交易日模擬停損/停利觸發與各掃描間隔的出場滑價。

    回傳 0~2 筆事件（一天最多各觸發一次 SL 與 TP 情境；兩情境獨立模擬，
    因為艦隊 Bot 是「其中一個先觸發就出場」，這裡分開統計兩種延遲成本）。
    """
    day_df = day_df.sort_values("timestamp").reset_index(drop=True)
    if len(day_df) < 30:  # 太稀疏的日子（IEX 冷門時段）不納入
        return []
    entry = float(day_df.iloc[0]["open"])
    open_ts = day_df.iloc[0]["timestamp"]
    events = []

    for kind, level, adverse in (
        ("stop_loss", entry * (1 - STOP_LOSS), True),
        ("take_profit", entry * (1 + TAKE_PROFIT), False),
    ):
        if adverse:
            hit = day_df[day_df["low"] <= level]
        else:
            hit = day_df[day_df["high"] >= level]
        if hit.empty:
            continue
        t_star = hit.iloc[0]["timestamp"]  # 第一個觸價分鐘
        sec_from_open = (t_star - open_ts).total_seconds()

        row = {"kind": kind, "entry": entry, "level": level}
        for iv in INTERVALS:
            # 下一個檢查 tick（從開盤起每 iv 秒）；觸價分鐘自己算 0 延遲下限
            import math
            tick_sec = math.ceil(sec_from_open / iv) * iv
            tick_ts = open_ts + pd.Timedelta(seconds=tick_sec)
            after = day_df[day_df["timestamp"] >= tick_ts]
            if after.empty:
                # 收盤前沒有下一個 tick → 收盤才出（用最後一根收盤價）
                px = float(day_df.iloc[-1]["close"])
            else:
                px = float(after.iloc[0]["open"])
            # 額外滑價（bps，正 = 比觸價價位更差）
            slip = (level - px) / entry * 1e4 if adverse else (px - level) / entry * -1e4
            row[f"slip_bps_{iv}"] = slip
        events.append(row)
    return events


def main() -> int:
    ap = argparse.ArgumentParser(description="掃盤頻率研究（分鐘 K 模擬出場延遲 + API 用量）")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--symbols", type=str, default=settings.AUTO_DEPLOY_KNOWLEDGE_SYMBOLS)
    ap.add_argument("--bots", type=int, default=190, help="啟用中的 Bot 數（算 API 用量）")
    args = ap.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"抓 {len(symbols)} 檔近 {args.days} 天分鐘 K…", flush=True)
    df = fetch_minute_bars(symbols, args.days)
    print(f"共 {len(df)} 根分鐘 K", flush=True)

    # 只留正常時段（13:30–20:00 UTC ≈ 美東 9:30–16:00，忽略 DST 邊界誤差——研究用足夠）
    df["date"] = df["timestamp"].dt.date
    df["utc_hm"] = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute
    df = df[(df["utc_hm"] >= 13 * 60 + 30) & (df["utc_hm"] < 20 * 60)]

    all_events = []
    for (sym, day), g in df.groupby(["symbol", "date"]):
        for ev in simulate_day(g):
            ev["symbol"] = sym
            ev["date"] = str(day)
            all_events.append(ev)

    sl_events = [e for e in all_events if e["kind"] == "stop_loss"]
    tp_events = [e for e in all_events if e["kind"] == "take_profit"]
    n_days = df.groupby(["symbol", "date"]).ngroups

    # ---------- 彙總 ----------
    rows = []
    for iv in INTERVALS:
        def stats_of(evts):
            vals = [e[f"slip_bps_{iv}"] for e in evts if f"slip_bps_{iv}" in e]
            if not vals:
                return (None, None, None)
            vals_sorted = sorted(vals)
            p95 = vals_sorted[min(len(vals) - 1, int(len(vals) * 0.95))]
            return (round(statistics.mean(vals), 2), round(statistics.median(vals), 2), round(p95, 2))

        sl_mean, sl_med, sl_p95 = stats_of(sl_events)
        tp_mean, tp_med, tp_p95 = stats_of(tp_events)
        req_per_min = args.bots * 60 / iv  # 每 Bot 每輪至少 1 次資料請求
        rows.append({
            "interval_sec": iv,
            "sl_events": len(sl_events),
            "sl_slip_bps_mean": sl_mean, "sl_slip_bps_median": sl_med, "sl_slip_bps_p95": sl_p95,
            "tp_events": len(tp_events),
            "tp_slip_bps_mean": tp_mean, "tp_slip_bps_median": tp_med, "tp_slip_bps_p95": tp_p95,
            "api_req_per_min": round(req_per_min, 1),
            "api_headroom_pct": round((1 - req_per_min / settings.ALPACA_RATE_LIMIT_PER_MIN) * 100, 1)
            if settings.ALPACA_RATE_LIMIT_PER_MIN else None,
        })

    with open(OUT_DIR / "scan-frequency.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    lines = [
        "# 掃盤頻率研究（30~600 秒）",
        "",
        "## 誠實前提",
        "",
        "- 本系統策略吃**日 K**，訊號一天只變一次 → **掃頻不影響進場時機**。",
        "- 掃頻只影響：(1) 風控出場延遲（觸價後等下一輪檢查的額外滑價）(2) API 用量。",
        f"- 樣本：{len(symbols)} 檔 × 近 {args.days} 天分鐘 K，共 {n_days} 個 symbol-日、",
        f"  停損情境觸發 {len(sl_events)} 次、停利情境觸發 {len(tp_events)} 次",
        f"  （模擬開盤進場、停損 -{STOP_LOSS:.0%} / 停利 +{TAKE_PROFIT:.0%}）。",
        "- ⚠️ 艦隊現況 190 個 Bot **全部沒設停損/停利** → 現況下掃頻對出場也幾乎無影響，",
        "  只剩 API 用量差異；下表的滑價成本是「若啟用風控」的前瞻依據。",
        "",
        "| 間隔(s) | SL 額外滑價 bps（均值/中位/p95） | TP 額外滑價 bps（均值/中位/p95） | API req/min（190 bots） | 限流餘裕 |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['interval_sec']} | {r['sl_slip_bps_mean']} / {r['sl_slip_bps_median']} / {r['sl_slip_bps_p95']} "
            f"| {r['tp_slip_bps_mean']} / {r['tp_slip_bps_median']} / {r['tp_slip_bps_p95']} "
            f"| {r['api_req_per_min']} | {r['api_headroom_pct']}% |"
        )
    (OUT_DIR / "scan-frequency.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"完成：報告在 {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
