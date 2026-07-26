"""
分鐘 K 批次預熱 CLI（Phase 16 M6-0）
====================================
把研究矩陣（research_matrix）要用的多 timeframe K 線先抓進本機 bar_cache，
之後批跑回測全程命中快取、不再打外部 API。

設計重點：
  - **不重造輪子**：抓取走 `bar_cache.get_bars_cached_multi`（缺口才補抓、寫 parquet），
    限流走 `alpaca_client` 內建的 token bucket（免費版 200 req/min 保險絲）。
  - **斷點續跑**：bar_cache 的 meta 記「已涵蓋區間」，中斷後重跑同指令，
    已抓過的 (symbol, timeframe) 命中快取＝0 次 API，自動從缺的續抓。
  - **順便做資料品質體檢**（M6 Round 1 的守門）：IEX 免費源的分鐘 K 可能稀疏
    （成交清淡的 bar 直接缺格）。每檔算「實際 bar 數 / 理論 bar 數」的稀疏率，
    稀疏率高的 timeframe 之後回測結果不可信 → 先回報使用者再決定是否上付費數據。

只讀寫本機快取；不寫 DB、不下單。

用法（預設核心 6 檔 × 全部 8 個 timeframe × 2 年）：
    venv\\Scripts\\python.exe scripts\\warm_cache.py
    venv\\Scripts\\python.exe scripts\\warm_cache.py --symbols AMD,BAC --timeframes 5Min,15Min --days 365
輸出：
    docs/reference/analysis-<今天>/warm-cache-quality.md（+ console 進度）
"""

import argparse
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd  # noqa: E402

from backend.services import bar_cache, timeframes  # noqa: E402

# 核心池 6 檔（docs/reference/analysis-2026-07-02/stock-pool.md 體檢結果：
# OOS EV>0 且 round trips ≥3 —— 先用它們驗證分鐘 K 品質，OK 再擴全池）
CORE_POOL = ["AMD", "AVGO", "INTC", "ORCL", "BAC", "MS"]

DEFAULT_DAYS = 730  # 2 年：walk-forward 要切多段 IS/OOS，太短切不出摺數

# 稀疏率警戒線：實際 bar 數低於理論值的這個比例就標紅
# （IEX 只涵蓋自家撮合量 ~2-3%，清淡股分鐘 K 大量缺格是已知現象）
SPARSE_WARN = 0.30   # 缺 30% 以上 → ⚠️
SPARSE_BAD = 0.60    # 缺 60% 以上 → ❌ 該 timeframe 回測不可信


def _quality_row(symbol: str, timeframe: str, df: pd.DataFrame) -> dict:
    """
    算單一 (symbol, timeframe) 的品質統計。

    理論 bar 數 = 資料裡「實際出現過的交易日數」× 每日理論 bar 數（RTH 390 分鐘計）。
    用資料裡的交易日當分母（而不是日曆推算），假日/停牌不會被誤算成缺格；
    量到的就純粹是「交易日內缺了幾格」＝ IEX 稀疏問題本身。

    ⚠️ IEX 會回盤前盤後 bar（實測 5Min 一天 166 根 >> RTH 理論 78 根），
    直接拿總 bar 數會灌水掩蓋 RTH 缺格 → 稀疏率只數 9:30–16:00 ET 的 bar。
    """
    if df is None or df.empty:
        return {
            "symbol": symbol, "timeframe": timeframe, "bars": 0, "trading_days": 0,
            "expected": 0, "sparse_pct": 100.0, "first": "-", "last": "-", "flag": "❌ 無資料",
        }
    ts = pd.to_datetime(df["timestamp"])
    days_seen = ts.dt.date.nunique()
    # 日內框架：換到美東時間、只留正規交易時段（RTH）再算稀疏率
    if timeframe != "1Day" and ts.dt.tz is not None:
        et = ts.dt.tz_convert("America/New_York")
        minutes = et.dt.hour * 60 + et.dt.minute
        rth_count = int(((minutes >= 9 * 60 + 30) & (minutes < 16 * 60)).sum())
    else:
        rth_count = len(df)
    expected = days_seen * timeframes.bars_per_day(timeframe)
    sparse = max(0.0, 1.0 - rth_count / expected) if expected else 1.0
    if sparse >= SPARSE_BAD:
        flag = "❌ 稀疏"
    elif sparse >= SPARSE_WARN:
        flag = "⚠️ 偏稀"
    else:
        flag = "✅"
    return {
        "symbol": symbol, "timeframe": timeframe, "bars": len(df), "trading_days": days_seen,
        "expected": int(expected), "sparse_pct": round(sparse * 100, 1),
        "first": str(ts.iloc[0])[:16], "last": str(ts.iloc[-1])[:16], "flag": flag,
    }


def warm(symbols: list[str], tf_list: list[str], days: int, source: str) -> list[dict]:
    """逐 timeframe 批次預熱（一個 timeframe 一桶，最多 2 次 HTTP），回品質統計列。"""
    rows: list[dict] = []
    total = len(tf_list)
    for i, tf in enumerate(tf_list, 1):
        t0 = time.monotonic()
        print(f"[{i}/{total}] 預熱 {tf} × {len(symbols)} 檔 × {days} 天 ...", flush=True)
        result = bar_cache.get_bars_cached_multi(symbols, days=days, source=source, timeframe=tf)
        elapsed = time.monotonic() - t0
        for sym in symbols:
            row = _quality_row(sym, tf, result.get(sym))
            rows.append(row)
            print(
                f"    {sym:<6} bars={row['bars']:>7} 交易日={row['trading_days']:>4} "
                f"稀疏率={row['sparse_pct']:>5.1f}% {row['flag']}",
                flush=True,
            )
        print(f"    {tf} 完成，耗時 {elapsed:.1f}s", flush=True)
    return rows


def write_report(rows: list[dict], days: int, source: str, out_dir: Path) -> Path:
    """品質體檢寫 markdown（給 M6 Round 1 前的人在迴路判斷用）。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "warm-cache-quality.md"
    bad = [r for r in rows if r["sparse_pct"] >= SPARSE_BAD * 100]
    warn = [r for r in rows if SPARSE_WARN * 100 <= r["sparse_pct"] < SPARSE_BAD * 100]
    lines = [
        "# 分鐘 K 快取預熱 + 資料品質體檢",
        "",
        f"- 日期：{date.today().isoformat()}；來源：{source}（免費 IEX feed）；回看：{days} 天",
        f"- 檔數 × 框架：{len({r['symbol'] for r in rows})} × {len({r['timeframe'] for r in rows})}",
        f"- 判定：稀疏率 ≥{int(SPARSE_BAD*100)}% ❌ 回測不可信；≥{int(SPARSE_WARN*100)}% ⚠️ 偏稀；其餘 ✅",
        f"- 結論：❌ {len(bad)} 組 / ⚠️ {len(warn)} 組 / ✅ {len(rows) - len(bad) - len(warn)} 組"
        +("；**存在不可信組合，擴池或上付費數據前先給人看**" if bad else ""),
        "",
        "| symbol | timeframe | bars | 交易日 | 理論bars | 稀疏率% | 最早 | 最晚 | 判定 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda r: (-r["sparse_pct"], r["symbol"])):
        lines.append(
            f"| {r['symbol']} | {r['timeframe']} | {r['bars']} | {r['trading_days']} "
            f"| {r['expected']} | {r['sparse_pct']} | {r['first']} | {r['last']} | {r['flag']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="分鐘 K 批次預熱 + 品質體檢（M6-0）")
    parser.add_argument("--symbols", default=",".join(CORE_POOL),
                        help=f"逗號分隔（預設核心 6 檔：{','.join(CORE_POOL)}）")
    parser.add_argument("--timeframes", default=",".join(timeframes.ALL_TIMEFRAMES),
                        help=f"逗號分隔（預設全部：{','.join(timeframes.ALL_TIMEFRAMES)}）")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS,
                        help=f"往前抓幾個日曆天（預設 {DEFAULT_DAYS}）")
    parser.add_argument("--source", default="alpaca", help="資料源（預設 alpaca）")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    tf_list = [timeframes.validate(t.strip()) for t in args.timeframes.split(",") if t.strip()]

    t0 = time.monotonic()
    rows = warm(symbols, tf_list, args.days, args.source)
    out_dir = ROOT / "docs" / "reference" / f"analysis-{date.today().isoformat()}"
    report = write_report(rows, args.days, args.source, out_dir)
    print(f"\n總耗時 {time.monotonic() - t0:.1f}s；品質報告 → {report.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
