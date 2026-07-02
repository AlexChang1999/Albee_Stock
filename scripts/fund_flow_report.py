"""
資金流分析 CLI（2026-07 回測驗證日）
====================================
回答「市場資金現在流向哪裡？哪些族群強勢？哪些股票可能隔日發動？」

方法（全部用免費日 K，價量推導，不需要付費資金流資料）：
  1. **產業輪動**：11 檔 SPDR 產業 ETF vs SPY 的相對強度（RS = ETF 報酬 − SPY 報酬），
     取 1 / 5 / 20 日三個窗口 → 看資金短中期往哪個產業移動。
  2. **量能**：各 ETF 最新量 ÷ 20 日均量 → 輪動有沒有量（有量的輪動才可信）。
  3. **買賣壓 proxy**：orderflow_proxy 的 net_pressure（tick-rule 近似，非真實逐筆資料，
     誠實標註它是 proxy）近 5 日合計。
  4. **領漲股**：把股票池 38 檔映射到產業，在強勢產業內依 5 日 RS + 量比排領漲股。
  5. **隔日發動候選**：強勢產業 × 個股量比 > 1.5 × 淨買壓 > 0 × 5 日 RS > 0 的交集。

只讀資料，不碰 DB、不下單。

用法：
    venv\\Scripts\\python.exe scripts\\fund_flow_report.py
輸出：
    docs/reference/analysis-2026-07-02/fund-flow.csv / fund-flow.md
"""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from backend.config import settings  # noqa: E402
from backend.services import bar_cache  # noqa: E402
from backend.services.orderflow_proxy import compute_orderflow  # noqa: E402

OUT_DIR = ROOT / "docs" / "reference" / "analysis-2026-07-02"

SECTOR_ETFS = {
    "XLK": "科技", "XLF": "金融", "XLE": "能源", "XLV": "醫療", "XLY": "非必需消費",
    "XLP": "必需消費", "XLI": "工業", "XLB": "原物料", "XLU": "公用事業",
    "XLRE": "房地產", "XLC": "通訊服務",
}
BENCH = "SPY"

# 股票池 → 產業 ETF 映射（指數型 ETF 不參與個股排名）
SYMBOL_SECTOR = {
    "NVDA": "XLK", "AMD": "XLK", "AVGO": "XLK", "TSM": "XLK", "INTC": "XLK",
    "QCOM": "XLK", "MU": "XLK", "AMAT": "XLK", "LRCX": "XLK", "ASML": "XLK",
    "AAPL": "XLK", "MSFT": "XLK", "ADBE": "XLK", "CRM": "XLK", "ORCL": "XLK",
    "GOOGL": "XLC", "META": "XLC", "NFLX": "XLC",
    "AMZN": "XLY", "TSLA": "XLY",
    "XOM": "XLE", "CVX": "XLE", "COP": "XLE",
    "JPM": "XLF", "BAC": "XLF", "WFC": "XLF", "GS": "XLF", "MS": "XLF",
    "CAT": "XLI", "BA": "XLI", "HON": "XLI", "UNP": "XLI", "GE": "XLI",
}


def metrics_for(sym: str, bench_close=None) -> dict | None:
    """單一標的的報酬 / 量比 / 淨買壓（近 60 個交易日資料推導）。"""
    try:
        df = bar_cache.get_bars_cached(sym, days=100, source=settings.DATA_SOURCE)
    except Exception:
        return None
    if df is None or len(df) < 25:
        return None
    close = df["close"].astype(float)
    vol = df["volume"].astype(float) if "volume" in df.columns else None

    def ret(n):
        if len(close) <= n:
            return None
        return round((close.iloc[-1] / close.iloc[-1 - n] - 1) * 100, 2)

    out = {"symbol": sym, "ret_1d": ret(1), "ret_5d": ret(5), "ret_20d": ret(20)}
    out["volume_ratio"] = (
        round(float(vol.iloc[-1] / vol.iloc[-21:-1].mean()), 2)
        if vol is not None and len(vol) >= 21 and vol.iloc[-21:-1].mean() > 0 else None
    )
    try:
        flow = compute_orderflow(df)
        # 近 5 日淨買壓合計（proxy；正 = 買方主導）
        out["net_pressure_5d"] = round(float(flow["net_pressure"].iloc[-5:].sum()), 0)
    except Exception:
        out["net_pressure_5d"] = None

    if bench_close is not None:
        for n in (1, 5, 20):
            r, b = out.get(f"ret_{n}d"), bench_close.get(f"ret_{n}d")
            out[f"rs_{n}d"] = round(r - b, 2) if r is not None and b is not None else None
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    bench = metrics_for(BENCH)
    if bench is None:
        print("抓不到 SPY 基準資料")
        return 1

    # ---------- 產業 ETF 輪動 ----------
    etf_rows = []
    for etf, name in SECTOR_ETFS.items():
        m = metrics_for(etf, bench)
        if m:
            m["sector"] = name
            etf_rows.append(m)
    etf_rows.sort(key=lambda x: (x.get("rs_5d") if x.get("rs_5d") is not None else -9e9), reverse=True)
    strong_sectors = [r["symbol"] for r in etf_rows[:3] if (r.get("rs_5d") or 0) > 0]

    # ---------- 個股（映射到產業）----------
    stock_rows = []
    for sym, etf in SYMBOL_SECTOR.items():
        m = metrics_for(sym, bench)
        if m:
            m["sector_etf"] = etf
            m["sector"] = SECTOR_ETFS.get(etf, "")
            stock_rows.append(m)

    # 領漲股：強勢產業內依 5 日 RS 排
    leaders = sorted(
        [r for r in stock_rows if r["sector_etf"] in strong_sectors],
        key=lambda x: (x.get("rs_5d") if x.get("rs_5d") is not None else -9e9), reverse=True,
    )[:10]

    # 隔日發動候選：強產業 × 量比>1.5 × 淨買壓>0 × 5日RS>0
    candidates = [
        r for r in stock_rows
        if r["sector_etf"] in strong_sectors
        and (r.get("volume_ratio") or 0) > 1.5
        and (r.get("net_pressure_5d") or 0) > 0
        and (r.get("rs_5d") or 0) > 0
    ]

    # ---------- 落檔 ----------
    all_rows = [{**r, "kind": "sector_etf"} for r in etf_rows] + \
               [{**r, "kind": "stock"} for r in stock_rows]
    fields = ["kind", "symbol", "sector", "sector_etf", "ret_1d", "ret_5d", "ret_20d",
              "rs_1d", "rs_5d", "rs_20d", "volume_ratio", "net_pressure_5d"]
    with open(OUT_DIR / "fund-flow.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)

    lines = [
        "# 資金流分析（價量推導）",
        "",
        f"- 基準 SPY：1日 {bench['ret_1d']}% / 5日 {bench['ret_5d']}% / 20日 {bench['ret_20d']}%",
        "- 買賣壓為 tick-rule **proxy**（免費日 K 推導，非真實逐筆資料）——方向參考、勿當精確值。",
        "",
        "## 產業輪動（相對 SPY 的 RS，依 5 日排序）",
        "",
        "| ETF | 產業 | RS 1日 | RS 5日 | RS 20日 | 量比 | 淨買壓5日 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in etf_rows:
        lines.append(f"| {r['symbol']} | {r['sector']} | {r.get('rs_1d')} | {r.get('rs_5d')} "
                     f"| {r.get('rs_20d')} | {r.get('volume_ratio')} | {r.get('net_pressure_5d')} |")
    lines += [
        "",
        f"**強勢產業（5日 RS > 0 前三）**：{', '.join(strong_sectors) or '（近 5 日無產業跑贏 SPY）'}",
        "",
        "## 領漲股（強勢產業內，依 5 日 RS）",
        "",
        "| symbol | 產業 | RS 5日 | RS 20日 | 量比 | 淨買壓5日 |",
        "|---|---|---|---|---|---|",
    ]
    for r in leaders:
        lines.append(f"| {r['symbol']} | {r['sector']} | {r.get('rs_5d')} | {r.get('rs_20d')} "
                     f"| {r.get('volume_ratio')} | {r.get('net_pressure_5d')} |")
    lines += [
        "",
        "## 隔日發動候選（強產業 × 量比>1.5 × 淨買壓>0 × 5日RS>0）",
        "",
        (", ".join(r["symbol"] for r in candidates) if candidates
         else "（今日無符合全部條件的候選——這是誠實結果，不硬湊）"),
        "",
        "## 如何把資金流納入策略（改進方案）",
        "",
        "1. **報表因子先行（本腳本）**：每日收盤後跑一次，產業 RS + 領漲股進戰情頁參考，"
        "不直接接下單（先累積觀察期，驗證因子有沒有預測力）。",
        "2. **入庫驗證**：把「產業 5 日 RS 排名」做成 FactorSnapshot 欄位存 DB，累積 60 天後"
        "用既有 OOS 閘驗證「只交易強勢產業成分股」對冠軍策略 EV 有無加分（Phase 7 層驗證同法）。",
        "3. **有加分才上線**：驗證通過 → 加進 screener 第 1.5 層（量能之後、情緒之前）；"
        "驗證不過 → 誠實砍掉（同 Phase 11 macro 層先例）。",
    ]
    (OUT_DIR / "fund-flow.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"完成：ETF {len(etf_rows)} 檔、個股 {len(stock_rows)} 檔、隔日候選 {len(candidates)} 檔 → {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
