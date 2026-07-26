"""
完整回測報告 CLI（2026-07 回測驗證日）
======================================
對整個監控股票池（AUTO_DEPLOY_KNOWLEDGE_SYMBOLS，預設 38 檔）跑「全自動掃描」：
每檔 9 種策略 × 參數網格，一律以樣本外（OOS）EV 排名挑冠軍（防過擬合），
冠軍再帶延伸指標（Sharpe / Sortino / MDD / CAGR）+ 蒙地卡羅壓力測試 +
「加風控出場」對照組（艦隊目前全部沒設停損/停利——這個對照組回答『該不該設』）。

只讀資料、只寫報告檔，不碰 DB、不下單。

用法（專案根目錄）：
    venv\\Scripts\\python.exe scripts\\full_backtest_report.py            # 全池、3 年
    venv\\Scripts\\python.exe scripts\\full_backtest_report.py --days 730 --symbols AAPL,MSFT
輸出：
    docs/reference/analysis-2026-07-02/backtest-champions.csv   每檔冠軍 + 全套指標
    docs/reference/analysis-2026-07-02/backtest-leaderboard.csv 全部策略×參數組合（每檔前 N 名）
    docs/reference/analysis-2026-07-02/backtest-report.md       報告本文
"""

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Windows 主控台 cp950 印 emoji/中文會崩潰
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from backend.config import settings  # noqa: E402
from backend.services.analytics import extended_metrics, returns_from_equity  # noqa: E402
from backend.services.backtest_engine import run_backtest  # noqa: E402
from backend.services.monte_carlo import stress_summary  # noqa: E402
from backend.services.optimizer import run_auto_backtest  # noqa: E402

def default_out_dir() -> Path:
    """報告輸出夾：docs/reference/analysis-<今天>（M9 週跑每次落在當日夾）。"""
    return ROOT / "docs" / "reference" / f"analysis-{date.today().isoformat()}"


# 「加風控」對照組參數（艦隊目前全 None；此組合僅為對照實驗，非最佳化結果——
# 取 docs/reference/human-vs-ai 一貫的保守量級：停損 7%、停利 15%、追蹤 10%）
RISK_VARIANT = {"stop_loss_pct": 0.07, "take_profit_pct": 0.15, "trailing_stop_pct": 0.10}

TOP_N_LEADERBOARD = 5  # 每檔留前 N 組進 leaderboard CSV（全量太大且無資訊增量）


def parse_symbols(raw: str) -> list[str]:
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


def run(days: int = 1095, symbols: str | None = None, cash: float = 10000.0,
        out_dir: Path | None = None) -> str:
    """跑全池回測報告，落 CSV/markdown 到 out_dir，回傳 markdown 全文（M9 排程用）。"""
    out_dir = Path(out_dir) if out_dir else default_out_dir()
    symbols = parse_symbols(symbols or settings.AUTO_DEPLOY_KNOWLEDGE_SYMBOLS)
    out_dir.mkdir(parents=True, exist_ok=True)

    champions: list[dict] = []
    leaderboard_rows: list[dict] = []
    errors: list[str] = []

    for i, sym in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] {sym} 掃描中…", flush=True)
        try:
            scan = run_auto_backtest(sym, days=days, initial_cash=cash)
        except Exception as e:
            errors.append(f"{sym}: {e}")
            print(f"  ⚠️ {sym} 失敗：{e}", flush=True)
            continue

        for r in scan["leaderboard"][:TOP_N_LEADERBOARD]:
            m = r["metrics"]
            leaderboard_rows.append({
                "symbol": sym, "strategy": r["strategy_key"],
                "params": json.dumps(r["params"], ensure_ascii=False),
                "oos_ev": m["oos_expected_value"], "is_ev": m["is_expected_value"],
                "oos_win_rate_pct": m["oos_win_rate_pct"],
                "oos_return_pct": m["oos_total_return_pct"],
                "oos_round_trips": m["oos_num_round_trips"],
                "full_return_pct": m["total_return_pct"],
                "full_mdd_pct": m["max_drawdown_pct"],
            })

        best = scan["best"]
        if best is None:
            errors.append(f"{sym}: 無有效組合")
            continue

        # 冠軍重跑：拿完整 trades / equity + 延伸指標；再跑「加風控」對照組
        base = run_backtest(best["strategy_key"], sym, params=best["params"],
                            days=days, initial_cash=cash)
        risk = run_backtest(best["strategy_key"], sym, params=best["params"],
                            days=days, initial_cash=cash, **RISK_VARIANT)
        ext = base.get("extended") or {}
        # 蒙地卡羅壓力測試：以冠軍整段日報酬 bootstrap（固定 seed 可重現）
        try:
            stress = stress_summary(returns_from_equity(base["equity_curve"]),
                                    initial_equity=cash, n_paths=500, seed=42)
        except Exception:
            stress = {}

        m = best["metrics"]
        champions.append({
            "symbol": sym,
            "strategy": best["strategy_key"],
            "params": json.dumps(best["params"], ensure_ascii=False),
            "data_points": scan["data_points"],
            # --- 樣本外（挑冠軍依據）---
            "oos_ev": m["oos_expected_value"],
            "oos_expectancy_pct": m["oos_expectancy_pct"],
            "oos_win_rate_pct": m["oos_win_rate_pct"],
            "oos_return_pct": m["oos_total_return_pct"],
            "oos_round_trips": m["oos_num_round_trips"],
            "is_ev": m["is_expected_value"],  # 樣本內對照：IS>>OOS = 過擬合警訊
            # --- 整段（含成本、隔日成交）---
            "return_pct": base["total_return_pct"],
            "buy_hold_pct": base["buy_and_hold_pct"],
            "win_rate_pct": base["win_rate_pct"],
            "profit_factor": base["profit_factor"],
            "expected_value": base["expected_value"],
            "num_round_trips": base["num_round_trips"],
            "max_drawdown_pct": base["max_drawdown_pct"],
            "total_cost": base["total_cost"],
            # --- 延伸指標（quantstats）---
            "sharpe": ext.get("sharpe"),
            "sortino": ext.get("sortino"),
            "cagr_pct": ext.get("cagr_pct"),
            "volatility_ann_pct": ext.get("volatility_ann_pct"),
            # --- 蒙地卡羅（bootstrap 500 路徑）---
            "mc_p5_final": stress.get("final_equity_p5"),
            "mc_p50_final": stress.get("final_equity_p50"),
            "mc_prob_dd20_pct": stress.get("prob_drawdown_exceeds_pct"),
            # --- 加風控對照組（停損7%/停利15%/追蹤10%）---
            "risk_return_pct": risk["total_return_pct"],
            "risk_mdd_pct": risk["max_drawdown_pct"],
            "risk_ev": risk["expected_value"],
            "risk_num_sl": risk["num_stop_loss"],
            "risk_num_tp": risk["num_take_profit"],
            "risk_num_trail": risk["num_trailing_stop"],
        })

    # ---------- 落檔 ----------
    if champions:
        with open(out_dir / "backtest-champions.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(champions[0].keys()))
            w.writeheader()
            w.writerows(champions)
    if leaderboard_rows:
        with open(out_dir / "backtest-leaderboard.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(leaderboard_rows[0].keys()))
            w.writeheader()
            w.writerows(leaderboard_rows)

    # markdown 摘要
    lines = [
        "# 全池完整回測報告",
        "",
        f"- 期間：近 {days} 天（日 K、含成本 {settings.BACKTEST_COMMISSION_BPS}bps 手續費 + "
        f"{settings.BACKTEST_SLIPPAGE_BPS}bps 滑價、隔日開盤成交）",
        f"- 股票池：{len(symbols)} 檔；成功 {len(champions)}、失敗 {len(errors)}",
        f"- 排名依據：**樣本外（OOS，後 {int(settings.OOS_TEST_RATIO*100)}%）期望值**，非整段最佳（防過擬合）",
        "- 風控對照組：停損 7% / 停利 15% / 追蹤 10%（艦隊現況＝全未設）",
        "",
        "| symbol | 冠軍策略 | OOS EV | OOS 勝率% | 整段報酬% | B&H% | PF | MDD% | Sharpe | 風控後報酬% | 風控後MDD% | SL/TP/Trail 觸發 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in sorted(champions, key=lambda x: (x["oos_ev"] if x["oos_ev"] is not None else -9e9), reverse=True):
        lines.append(
            f"| {c['symbol']} | {c['strategy']} {c['params']} | {c['oos_ev']} | {c['oos_win_rate_pct']} "
            f"| {c['return_pct']} | {c['buy_hold_pct']} | {c['profit_factor']} | {c['max_drawdown_pct']} "
            f"| {c['sharpe']} | {c['risk_return_pct']} | {c['risk_mdd_pct']} "
            f"| {c['risk_num_sl']}/{c['risk_num_tp']}/{c['risk_num_trail']} |"
        )
    if errors:
        lines += ["", "## 失敗清單", ""] + [f"- {e}" for e in errors]
    md = "\n".join(lines)
    (out_dir / "backtest-report.md").write_text(md, encoding="utf-8")

    print(f"完成：{len(champions)} 檔冠軍，報告在 {out_dir}")
    return md


def main() -> int:
    """CLI 殼：參數解析後呼叫 run()（M9 排程走 run()，CLI 行為不變）。"""
    ap = argparse.ArgumentParser(description="全池完整回測報告（OOS 排名 + 壓力測試）")
    ap.add_argument("--days", type=int, default=1095, help="回測區間天數（預設 3 年）")
    ap.add_argument("--symbols", type=str, default=settings.AUTO_DEPLOY_KNOWLEDGE_SYMBOLS,
                    help="逗號分隔股票清單（預設 = AUTO_DEPLOY_KNOWLEDGE_SYMBOLS）")
    ap.add_argument("--cash", type=float, default=10000.0)
    args = ap.parse_args()
    run(days=args.days, symbols=args.symbols, cash=args.cash)
    return 0


if __name__ == "__main__":
    sys.exit(main())
