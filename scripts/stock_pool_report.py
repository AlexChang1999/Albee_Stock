"""
股票池體檢 CLI（2026-07 回測驗證日）
====================================
回答「38 檔是不是太多？哪些該留、哪些該踢？」——每檔給完整數據，分層建議，不只給結論。

每檔統計（資料來源）：
  1. 冠軍策略 OOS EV / 勝率（讀 full_backtest_report 產出的 backtest-champions.csv；
     沒跑過會提示先跑那支）。
  2. 訊號頻率：冠軍組合整段回測的年化交易次數（回測 trades）。
  3. 假突破率：整段回測中「進場後 ≤3 根日 K 就虧損出場」的 round trip 佔比
     （突破型進場最常見的失敗模式：一進就回頭）。
  4. DecisionLog 實盤決策彙總（近 N 天）：buy / sell / hold 次數 → 實際有沒有在動。
  5. StrategySymbolFit（bot 汰弱審查員的既有評分）：good / poor / insufficient 統計。
  6. 市場狀態特徵（regime_features）：volume_ratio / volatility / trend_strength。

分層規則（透明、可調）：
  - 核心池：OOS EV > 0 且 **OOS round trips ≥ 3（樣本要夠，1~2 筆的 100% 勝率是統計噪音）**
    且 假突破率 < 40% 且（DecisionLog 有訊號 或 回測年交易 ≥ 3）
  - 觀察池：OOS EV > 0 但其餘條件不滿足（最常見：OOS 樣本不足 → edge 未被證實）
  - 建議剔除：OOS EV ≤ 0（樣本外沒有正期望 → 監控它只是燒 API 與注意力）

只讀 DB（彙總查詢）與快取 K 線；不寫 DB、不下單。

用法：
    venv\\Scripts\\python.exe scripts\\stock_pool_report.py
輸出：
    docs/reference/analysis-2026-07-02/stock-pool.csv / stock-pool.md
"""

import csv
import json
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
import sqlalchemy as sa  # noqa: E402

from backend.config import settings  # noqa: E402
from backend.database import SessionLocal  # noqa: E402
from backend.services import bar_cache  # noqa: E402
from backend.services.backtest_engine import run_backtest  # noqa: E402
from backend.services.regime_features import compute_features  # noqa: E402

OUT_DIR = ROOT / "docs" / "reference" / "analysis-2026-07-02"
CHAMPIONS_CSV = OUT_DIR / "backtest-champions.csv"
FALSE_BREAKOUT_MAX_BARS = 3  # 進場後 ≤N 根就虧損出場 = 假突破


def load_champions() -> dict[str, dict]:
    if not CHAMPIONS_CSV.exists():
        print(f"找不到 {CHAMPIONS_CSV}，請先跑 scripts/full_backtest_report.py")
        sys.exit(1)
    out = {}
    with open(CHAMPIONS_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            out[row["symbol"]] = row
    return out


def false_breakout_rate(trades: list[dict]) -> tuple[float | None, int]:
    """配對 buy→sell round trip；回（假突破率%, round trip 數）。"""
    rts = []
    buy = None
    for t in trades:
        if t["side"] == "buy":
            buy = t
        elif t["side"] == "sell" and buy is not None:
            try:
                held = (pd.Timestamp(t["date"]) - pd.Timestamp(buy["date"])).days
            except Exception:
                held = None
            rts.append({"profit": t.get("profit", 0.0), "held_days": held})
            buy = None
    if not rts:
        return None, 0
    false_n = sum(
        1 for r in rts
        if r["profit"] < 0 and r["held_days"] is not None and r["held_days"] <= FALSE_BREAKOUT_MAX_BARS + 2
        # 日曆日近似交易日：3 根 K ≈ 最多 5 個日曆日（跨週末）
    )
    return round(false_n / len(rts) * 100, 1), len(rts)


def decision_counts(db, since_days: int = 30) -> dict[str, dict]:
    """DecisionLog 近 N 天 per-symbol 訊號彙總（一次查詢，不逐檔打 DB）。"""
    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    rows = db.execute(sa.text(
        "SELECT symbol, signal, count(*) FROM decision_logs "
        "WHERE created_at >= :since GROUP BY symbol, signal"), {"since": since}).fetchall()
    out: dict[str, dict] = {}
    for sym, sig, n in rows:
        out.setdefault(sym, {})[sig] = n
    return out


def fit_verdicts(db) -> dict[str, dict]:
    """StrategySymbolFit per-symbol verdict 統計（表不存在或空時回 {}）。"""
    try:
        rows = db.execute(sa.text(
            "SELECT symbol, verdict, count(*) FROM strategy_symbol_fits GROUP BY symbol, verdict"
        )).fetchall()
    except Exception:
        return {}
    out: dict[str, dict] = {}
    for sym, verdict, n in rows:
        out.setdefault(sym, {})[verdict] = n
    return out


def main() -> int:
    symbols = [s.strip().upper() for s in settings.AUTO_DEPLOY_KNOWLEDGE_SYMBOLS.split(",") if s.strip()]
    champions = load_champions()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        dec = decision_counts(db)
        fits = fit_verdicts(db)
    finally:
        db.close()

    rows = []
    for i, sym in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] {sym}", flush=True)
        c = champions.get(sym)
        oos_ev = float(c["oos_ev"]) if c and c["oos_ev"] not in ("", "None") else None
        oos_rts = int(float(c["oos_round_trips"])) if c and c.get("oos_round_trips") not in (None, "", "None") else 0

        # 冠軍組合重跑（K 線已有本機快取，快）拿 trades 算訊號頻率與假突破率
        fb_rate, n_rts, trades_per_year = None, 0, None
        if c:
            try:
                r = run_backtest(c["strategy"], sym, params=json.loads(c["params"]),
                                 days=int(float(c.get("data_points", 750)) * 1.6))
                fb_rate, n_rts = false_breakout_rate(r["trades"])
                years = max(r["data_points"] / 252, 0.5)
                trades_per_year = round(r["num_round_trips"] / years, 1)
            except Exception as e:
                print(f"  ⚠️ 重跑失敗：{e}")

        # 市場狀態特徵（近 120 天）
        feats = {}
        try:
            df = bar_cache.get_bars_cached(sym, days=120, source=settings.DATA_SOURCE)
            feats = compute_features(df)
        except Exception:
            pass

        d = dec.get(sym, {})
        f = fits.get(sym, {})
        live_signals = (d.get("buy", 0) or 0) + (d.get("sell", 0) or 0)

        # ---- 分層 ----
        # OOS round trips < 3 的「100% 勝率 / 高 EV」是小樣本統計噪音，不能當已證實的 edge
        if oos_ev is None:
            tier = "資料不足"
        elif oos_ev <= 0:
            tier = "建議剔除"
        elif (oos_rts >= 3 and (fb_rate is not None and fb_rate < 40)
              and (live_signals > 0 or (trades_per_year or 0) >= 3)):
            tier = "核心池"
        else:
            tier = "觀察池（樣本不足）" if oos_rts < 3 else "觀察池"

        rows.append({
            "symbol": sym, "tier": tier,
            "champion": c["strategy"] if c else None,
            "oos_ev": oos_ev,
            "oos_round_trips": oos_rts,
            "oos_win_rate_pct": c["oos_win_rate_pct"] if c else None,
            "trades_per_year": trades_per_year,
            "false_breakout_pct": fb_rate,
            "round_trips": n_rts,
            "live_buy_30d": d.get("buy", 0), "live_sell_30d": d.get("sell", 0),
            "live_hold_30d": d.get("hold", 0),
            "fit_good": f.get("good", 0), "fit_poor": f.get("poor", 0),
            "fit_insufficient": f.get("insufficient", 0),
            "volume_ratio": feats.get("volume_ratio"),
            "volatility_20d": feats.get("volatility_20d"),
            "trend_strength": feats.get("trend_strength"),
        })

    with open(OUT_DIR / "stock-pool.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    tiers: dict[str, list] = {}
    for r in rows:
        tiers.setdefault(r["tier"], []).append(r["symbol"])

    lines = [
        "# 股票池體檢報告",
        "",
        f"- 現行池：{len(symbols)} 檔（AUTO_DEPLOY_KNOWLEDGE_SYMBOLS）",
        "- 分層結果：" + " / ".join(f"{k} {len(v)}" for k, v in tiers.items()),
        "",
    ] + [f"- **{k}**：{', '.join(v)}" for k, v in tiers.items()] + [
        "",
        "分層規則：核心 = OOS EV>0 **且 OOS round trips ≥ 3**（1~2 筆的 100% 勝率是小樣本噪音）"
        "且假突破率<40% 且有訊號活動；觀察 = OOS EV>0 其餘不滿足；剔除 = OOS EV≤0（樣本外無正期望）。",
        "",
        "| symbol | 分層 | 冠軍策略 | OOS EV | OOS交易數 | OOS勝率% | 年交易次數 | 假突破率% | 30天實盤 buy/sell | fit good/poor | 量比 | 波動20d |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda x: (x["oos_ev"] is None, -(x["oos_ev"] or 0))):
        vr = f"{r['volume_ratio']:.2f}" if r["volume_ratio"] is not None else "-"
        vol = f"{r['volatility_20d']:.2f}" if r["volatility_20d"] is not None else "-"
        lines.append(
            f"| {r['symbol']} | {r['tier']} | {r['champion']} | {r['oos_ev']} | {r['oos_round_trips']} "
            f"| {r['oos_win_rate_pct']} | {r['trades_per_year']} | {r['false_breakout_pct']} "
            f"| {r['live_buy_30d']}/{r['live_sell_30d']} | {r['fit_good']}/{r['fit_poor']} | {vr} | {vol} |"
        )
    (OUT_DIR / "stock-pool.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"完成：報告在 {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
