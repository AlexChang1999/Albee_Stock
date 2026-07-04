"""
研究矩陣批跑 CLI（Phase 16 M6）—— Round 1：timeframe 海選
==========================================================
回答「哪個 timeframe × 哪個策略值得繼續投資研究？」
全策略（PARAM_GRIDS 9 種 × 各參數網格）× 全 timeframe × 無 filter × 預設出場，
walk-forward 聚合 OOS 排名 → 每 timeframe 留前 3 策略，給 Round 2（stop×R:R）當輸入。

設計重點：
  - **不重造輪子**：單一 (symbol, timeframe) 的掃描直接用 `optimizer.run_auto_backtest`
    （已含 walk-forward 聚合 OOS + 樣本數/過擬合守門 + 向量化快路徑）。
    本腳本只做外層編排：fold 窗換算、逐格跑、聚合、報表。
  - **fold 窗按 bar 密度換算**：`VALIDATION_TRAIN_WINDOW=180/60/60` 是「根數」、
    為日 K 設計。1Min 一天 ~800 根（含盤前盤後），直接沿用會切出幾千個一小時級的
    無意義 fold。這裡把窗換算成「等效交易日」：train 180 / test 60 / step 60 個交易日
    × 該檔實際 bar 密度（len(df)/實際交易日數，含盤前盤後的真實密度，不用理論值）。
  - **斷點續跑**：每格 (symbol, timeframe) 跑完就落 checkpoint JSON
    （data/research/<tag>/），中斷重跑自動跳過已完成的格；`--force` 重算。
  - **只讀快取**：K 線走 bar_cache（先跑 scripts/warm_cache.py 預熱，否則會現抓、很慢）。
  - 每格冠軍落一筆 BacktestRun（metrics 加 study_tag，可在回測歷史頁查）；
    報表凡日內高頻組合標註 PDT 風險（實盤 <$25k 受限；paper 不受影響）。

人在迴路：本輪產出先給人看（榜單 + 判讀），核可後才開 Round 2。

用法（預設核心 6 檔 × 8 timeframe × 730 天）：
    venv\\Scripts\\python.exe scripts\\research_matrix.py
    venv\\Scripts\\python.exe scripts\\research_matrix.py --symbols AMD,BAC --timeframes 5Min,1Day
輸出：
    docs/reference/analysis-<今天>/research-matrix-round1.md（榜單）
    docs/reference/analysis-<今天>/research-matrix-round1.csv（全格明細）
"""

import argparse
import csv
import json
import sys
import time
import warnings
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# quantstats 對「fold 內零交易」的空報酬序列會噴 divide 警告——結果本來就會是 None，
# 純噪音；壓掉讓長跑進度可讀。
warnings.filterwarnings("ignore", category=RuntimeWarning, module="quantstats")

import pandas as pd  # noqa: E402

import numpy as np  # noqa: E402

from backend.config import settings  # noqa: E402
from backend.services import bar_cache, timeframes  # noqa: E402
from backend.services.backtest_engine import _run_on_df, _simulate_from_signals  # noqa: E402
from backend.services.exit_policies import get_exit_policy  # noqa: E402
from backend.services.optimizer import run_auto_backtest  # noqa: E402
from backend.services.validation import walk_forward_splits  # noqa: E402
from backend.services.vectorized_engine import SIGNAL_BUILDERS  # noqa: E402
from backend.strategies import Signal, get_strategy  # noqa: E402

# 核心池 6 檔（stock-pool 體檢：OOS EV>0 且 round trips ≥3；先小池驗證再擴）
CORE_POOL = ["AMD", "AVGO", "INTC", "ORCL", "BAC", "MS"]

DEFAULT_DAYS = 730

# fold 窗的「等效交易日」語意（與日 K 預設 180/60/60 根一致）
TRAIN_TRADING_DAYS = 180
TEST_TRADING_DAYS = 60
STEP_TRADING_DAYS = 60

# 每 timeframe 留前幾名策略進 Round 2
KEEP_TOP_N = 3

# PDT 標註門檻：估計年交易次數超過此值的日內組合，實盤 <$25k 會撞 PDT 限制
# （>150 次/年 ≈ 每週 3 次，貼近「5 個交易日內 4 次 day trade」的邊界）
PDT_TRADES_PER_YEAR = 150

CHECKPOINT_DIR = ROOT / "data" / "research"


def _bar_density(df: pd.DataFrame) -> float:
    """實際 bar 密度 = 總根數 / 出現過的交易日數（含盤前盤後的真實值，不用 RTH 理論值）。"""
    ts = pd.to_datetime(df["timestamp"])
    days_seen = ts.dt.date.nunique()
    return (len(df) / days_seen) if days_seen else 1.0


def _apply_fold_windows(density: float) -> None:
    """把 fold 窗換算成等效交易日（只覆寫本 CLI 行程內的 settings，不影響後端服務）。"""
    settings.VALIDATION_TRAIN_WINDOW = max(int(TRAIN_TRADING_DAYS * density), 30)
    settings.VALIDATION_TEST_WINDOW = max(int(TEST_TRADING_DAYS * density), 10)
    settings.VALIDATION_STEP = max(int(STEP_TRADING_DAYS * density), 10)


def _slim(entry: dict, density: float, tf: str) -> dict:
    """
    從 leaderboard 條目抽出聚合要用的精簡欄位（丟掉 trades / equity_curve 等大塊頭）。
    est_trades_per_year：OOS 交易數 ÷ OOS 總時長（fold 數 × 測試窗 ÷ 密度 ÷ 252 年）。
    """
    m = entry["metrics"]
    folds = m.get("oos_folds") or 0
    trips = m.get("oos_num_round_trips") or 0
    oos_bars = folds * settings.VALIDATION_TEST_WINDOW
    years = oos_bars / (density * 252) if density else 0.0
    return {
        "strategy": entry["strategy_key"],
        "params": entry["params"],
        "oos_ev": m.get("oos_expected_value"),
        "oos_trips": trips,
        "oos_folds": folds,
        "oos_win_rate_pct": m.get("oos_win_rate_pct"),
        "oos_profit_factor": m.get("oos_profit_factor"),
        "oos_sharpe": m.get("oos_sharpe"),
        "oos_max_drawdown_pct": m.get("oos_max_drawdown_pct"),
        "overfit_gap": m.get("overfit_gap"),
        "est_trades_per_year": round(trips / years, 1) if years > 0 else None,
        "timeframe": tf,
    }


def _passes_gate(r: dict) -> bool:
    """與 optimizer 排名守門同義：OOS 樣本夠 + 過擬合差距可接受 + 樣本外有正期望。"""
    gap = r.get("overfit_gap")
    return (
        (r.get("oos_trips") or 0) >= settings.OPTIMIZER_MIN_OOS_TRIPS
        and (gap is None or gap <= settings.OPTIMIZER_MAX_OVERFIT_GAP)
        and (r.get("oos_ev") or 0) > 0
    )


def run_cell(symbol: str, tf: str, days: int) -> dict:
    """
    跑一格 (symbol, timeframe)：按密度換算 fold 窗 → run_auto_backtest →
    每策略抽「該策略最佳組合」精簡列。回 checkpoint dict。
    """
    df = bar_cache.get_bars_cached(symbol, days=days, source="alpaca", timeframe=tf)
    if df.empty:
        return {"symbol": symbol, "timeframe": tf, "error": "no_data", "strategies": []}
    density = _bar_density(df)
    _apply_fold_windows(density)

    res = run_auto_backtest(symbol, days=days, timeframe=tf, walk_forward=True)

    # leaderboard 已依（守門旗標, OOS EV, OOS 報酬）排序 → 每策略取第一次出現的條目
    best_per_strategy: dict[str, dict] = {}
    for e in res["leaderboard"]:
        key = e["strategy_key"]
        if key not in best_per_strategy:
            best_per_strategy[key] = _slim(e, density, tf)

    return {
        "symbol": symbol,
        "timeframe": tf,
        "days": days,
        "data_points": res["data_points"],
        "bar_density": round(density, 1),
        "fold_windows": [settings.VALIDATION_TRAIN_WINDOW,
                         settings.VALIDATION_TEST_WINDOW, settings.VALIDATION_STEP],
        "strategies": list(best_per_strategy.values()),
    }


def _save_champion_to_db(cell: dict, study_tag: str) -> None:
    """每格冠軍（守門通過中 OOS EV 最高者）落一筆 BacktestRun；DB 掛了不擋報表。"""
    survivors = [r for r in cell["strategies"] if _passes_gate(r)]
    if not survivors:
        return
    champ = max(survivors, key=lambda r: r["oos_ev"])
    try:
        from backend.database import SessionLocal
        from backend.models.backtest_run import BacktestRun

        db = SessionLocal()
        try:
            db.add(BacktestRun(
                strategy_key=champ["strategy"],
                params=champ["params"],
                symbol=cell["symbol"],
                period_days=cell["days"],
                metrics={**champ, "study_tag": study_tag},
            ))
            db.commit()
        finally:
            db.close()
    except Exception as exc:  # DB 不可用（例如沒網路連 Neon）→ 報表照出
        print(f"    ⚠️ BacktestRun 落庫失敗（不影響報表）：{exc}", flush=True)


def aggregate(cells: list[dict]) -> dict[str, list[dict]]:
    """
    跨 symbol 聚合：每 (timeframe, strategy) 統計「守門通過的檔數」與通過檔的平均 OOS 指標。
    排名鍵 = (通過檔數, 平均 OOS EV)——先看普遍性（多檔都行才是策略的功勞，
    單檔獨強可能是那檔的特性），再看期望值大小。
    """
    by_tf: dict[str, dict[str, list[dict]]] = {}
    for cell in cells:
        for r in cell.get("strategies", []):
            by_tf.setdefault(cell["timeframe"], {}).setdefault(r["strategy"], []).append(
                {**r, "symbol": cell["symbol"], "pass": _passes_gate(r)}
            )

    ranking: dict[str, list[dict]] = {}
    for tf, strategies in by_tf.items():
        rows = []
        for strat, entries in strategies.items():
            passed = [e for e in entries if e["pass"]]
            def _mean(key):
                vals = [e[key] for e in passed if isinstance(e.get(key), (int, float))]
                return round(sum(vals) / len(vals), 2) if vals else None
            rows.append({
                "strategy": strat,
                "pass_count": len(passed),
                "n_symbols": len(entries),
                "mean_oos_ev": _mean("oos_ev"),
                "mean_trips": _mean("oos_trips"),
                "mean_win_rate": _mean("oos_win_rate_pct"),
                "mean_sharpe": _mean("oos_sharpe"),
                "mean_gap": _mean("overfit_gap"),
                "mean_trades_per_year": _mean("est_trades_per_year"),
                "pass_symbols": ",".join(e["symbol"] for e in passed),
            })
        rows.sort(key=lambda r: (r["pass_count"], r["mean_oos_ev"] or float("-inf")),
                  reverse=True)
        ranking[tf] = rows
    return ranking


def write_reports(cells: list[dict], ranking: dict[str, list[dict]],
                  tf_order: list[str], out_dir: Path, study_tag: str) -> Path:
    """榜單 markdown + 全格明細 CSV。"""
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- CSV：全部 (symbol, timeframe, strategy) 明細 ---
    csv_path = out_dir / "research-matrix-round1.csv"
    fields = ["symbol", "timeframe", "strategy", "params", "oos_ev", "oos_trips",
              "oos_folds", "oos_win_rate_pct", "oos_profit_factor", "oos_sharpe",
              "oos_max_drawdown_pct", "overfit_gap", "est_trades_per_year", "pass"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for cell in cells:
            for r in cell.get("strategies", []):
                w.writerow({**{k: r.get(k) for k in fields},
                            "symbol": cell["symbol"],
                            "params": json.dumps(r["params"]),
                            "pass": _passes_gate(r)})

    # --- markdown 榜單 ---
    md_path = out_dir / "research-matrix-round1.md"
    symbols = sorted({c["symbol"] for c in cells})
    lines = [
        "# 研究矩陣 Round 1 —— timeframe 海選（M6）",
        "",
        f"- 日期：{date.today().isoformat()}；study_tag：`{study_tag}`",
        f"- 池：{', '.join(symbols)}（{len(symbols)} 檔）；回看 {cells[0]['days']} 天；"
        f"無 filter、預設出場（fixed_pct baseline）",
        f"- 守門（沿用 optimizer）：OOS 交易 ≥{settings.OPTIMIZER_MIN_OOS_TRIPS}、"
        f"過擬合差距 ≤{settings.OPTIMIZER_MAX_OVERFIT_GAP}、OOS EV>0",
        "- 排名鍵：先「守門通過檔數」（普遍性）再「平均 OOS EV」（期望值）",
        f"- ⚠️ PDT：估計年交易 >{PDT_TRADES_PER_YEAR} 次的日內組合，"
        "實盤 <$25k 受 PDT 限制（paper 不受影響）",
        "",
    ]
    for tf in tf_order:
        rows = ranking.get(tf)
        if not rows:
            continue
        lines += [f"## {tf}", "",
                  "| # | 策略 | 通過檔數 | 平均OOS EV | 平均OOS交易 | 平均勝率% "
                  "| 平均Sharpe | 平均gap | 年交易估 | 通過檔 | 註 |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for i, r in enumerate(rows, 1):
            keep = "★留" if i <= KEEP_TOP_N and r["pass_count"] > 0 else ""
            pdt = ""
            if (timeframes.is_intraday(tf) and r["mean_trades_per_year"]
                    and r["mean_trades_per_year"] > PDT_TRADES_PER_YEAR):
                pdt = "⚠️PDT"
            note = " ".join(x for x in (keep, pdt) if x)
            lines.append(
                f"| {i} | {r['strategy']} | {r['pass_count']}/{r['n_symbols']} "
                f"| {r['mean_oos_ev']} | {r['mean_trips']} | {r['mean_win_rate']} "
                f"| {r['mean_sharpe']} | {r['mean_gap']} | {r['mean_trades_per_year']} "
                f"| {r['pass_symbols']} | {note} |"
            )
        lines.append("")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


# ======================================================================
# Round 2：stop × R:R（Round 1 存活組合 × 出場政策網格）
# ======================================================================

RR_GRID = [1.5, 2, 2.2, 2.5, 3, 4]

# Round 1 → Round 2 的存活門檻：榜單前 KEEP_TOP_N 且守門通過檔數 ≥ 此值
# （只有 1 檔通過的「前三名」是單檔特性不是策略功勞，不進 Round 2）
SURVIVOR_MIN_PASS = 3


def _exit_grid(tf: str) -> list[dict]:
    """
    出場政策網格（28 組）。exit_type 對齊藍圖要比的四型：
    只SL / 只Trailing / SL+Trailing / SL+Target(R:R)；baseline = 無政策（訊號出場，Round 1 同義）。
    """
    grid = [{"label": "baseline", "policy": None, "params": {}, "exit_type": "訊號出場"}]
    for rr in [None, *RR_GRID]:
        tag = "只SL" if rr is None else "SL+Target"
        grid.append({"label": f"atr2.0_rr{rr}", "policy": "atr",
                     "params": {"atr_len": 14, "atr_mult": 2.0, "rr_multiple": rr},
                     "exit_type": tag})
        grid.append({"label": f"swing20_rr{rr}", "policy": "swing",
                     "params": {"lookback": 20, "rr_multiple": rr}, "exit_type": tag})
    for sl in (0.03, 0.05):
        grid.append({"label": f"fixed_sl{sl}", "policy": "fixed_pct",
                     "params": {"stop_loss_pct": sl}, "exit_type": "只SL"})
    for tr in (0.03, 0.05):
        grid.append({"label": f"fixed_tr{tr}", "policy": "fixed_pct",
                     "params": {"trailing_stop_pct": tr}, "exit_type": "只Trailing"})
    grid.append({"label": "fixed_sl0.05_tr0.03", "policy": "fixed_pct",
                 "params": {"stop_loss_pct": 0.05, "trailing_stop_pct": 0.03},
                 "exit_type": "SL+Trailing"})
    for rr in RR_GRID:
        grid.append({"label": f"fixed_sl0.05_rr{rr}", "policy": "fixed_pct",
                     "params": {"stop_loss_pct": 0.05, "take_profit_pct": round(0.05 * rr, 4)},
                     "exit_type": "SL+Target"})
    if timeframes.is_intraday(tf):  # vwap 僅日內（日 K 掛上等於立刻出場）
        for rr in (None, 2):
            grid.append({"label": f"vwap_rr{rr}", "policy": "vwap",
                         "params": {"rr_multiple": rr},
                         "exit_type": "只SL" if rr is None else "SL+Target"})
    return grid


def load_round1_survivors(round1_dir: Path) -> dict:
    """
    讀 Round 1 checkpoint → 每 timeframe 的存活策略（榜單前 KEEP_TOP_N 且通過檔數 ≥ SURVIVOR_MIN_PASS）
    + 每 (tf, strategy, symbol) 的最佳參數。
    :return: {tf: {"strategies": [strat,...], "params": {(strat, sym): params}}}
    """
    cells = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(round1_dir.glob("*.json"))]
    if not cells:
        raise SystemExit(f"找不到 Round 1 checkpoint：{round1_dir}（先跑 --round 1）")
    ranking = aggregate(cells)
    out: dict = {}
    for tf, rows in ranking.items():
        keep = [r["strategy"] for r in rows[:KEEP_TOP_N]
                if r["pass_count"] >= SURVIVOR_MIN_PASS]
        if not keep:
            continue
        params_map = {}
        for cell in cells:
            if cell["timeframe"] != tf:
                continue
            for r in cell.get("strategies", []):
                if r["strategy"] in keep:
                    params_map[(r["strategy"], cell["symbol"])] = r["params"]
        out[tf] = {"strategies": keep, "params": params_map}
    return out


def _signals_for(strategy_key: str, params: dict, df: pd.DataFrame) -> list:
    """整段訊號：有向量化建構器走快路徑；沒有退回事件式逐根呼叫（安全網，勿算錯）。"""
    builder = SIGNAL_BUILDERS.get(strategy_key)
    if builder is not None:
        buy, sell = builder(df, params or {})
        return list(np.where(buy, Signal.BUY, np.where(sell, Signal.SELL, Signal.HOLD)))
    strategy = get_strategy(strategy_key, params)
    return [strategy.generate_signal(df.iloc[: i + 1]) for i in range(len(df))]


def _wf_exit_metrics(strategy_key: str, params: dict, df: pd.DataFrame,
                     exit_spec: dict, folds: list[dict]) -> dict:
    """
    對一個出場組合跑 walk-forward 聚合 OOS（fold 切法與 Round 1 同一套 →
    baseline 數字可與 Round 1 對上）。訊號每 fold 重算（fold 內自暖機，不偷看未來）。
    """
    total_trips, total_profit, total_wins = 0, 0.0, 0
    win_amt, loss_amt = 0.0, 0.0
    r_multiples: list[float] = []
    for fold in folds:
        test_df = df.iloc[fold["test_start"]: fold["test_end"]].reset_index(drop=True)
        signals = _signals_for(strategy_key, params, test_df)
        policy = (get_exit_policy(exit_spec["policy"], exit_spec["params"])
                  if exit_spec["policy"] else None)
        m = _simulate_from_signals(
            signals, test_df, 10000.0,
            commission_bps=settings.BACKTEST_COMMISSION_BPS,
            slippage_bps=settings.BACKTEST_SLIPPAGE_BPS,
            exit_policy=policy,
        )
        trips = m.get("num_round_trips") or 0
        total_trips += trips
        if trips and isinstance(m.get("expected_value"), (int, float)):
            total_profit += m["expected_value"] * trips
        wins, losses = m.get("num_wins") or 0, m.get("num_losses") or 0
        total_wins += wins
        if wins and m.get("avg_win"):
            win_amt += m["avg_win"] * wins
        if losses and m.get("avg_loss"):
            loss_amt += abs(m["avg_loss"]) * losses
        for t in m.get("trades") or []:
            if t.get("side") == "sell" and "r_multiple" in t:
                r_multiples.append(t["r_multiple"])
    return {
        "label": exit_spec["label"], "policy": exit_spec["policy"],
        "exit_params": exit_spec["params"], "exit_type": exit_spec["exit_type"],
        "oos_ev": round(total_profit / total_trips, 4) if total_trips else 0.0,
        "oos_trips": total_trips,
        "oos_win_rate_pct": round(total_wins / total_trips * 100, 2) if total_trips else 0.0,
        "oos_profit_factor": round(win_amt / loss_amt, 4) if loss_amt else None,
        "oos_avg_r_multiple": round(sum(r_multiples) / len(r_multiples), 3) if r_multiples else None,
    }


def run_round2_cell(symbol: str, tf: str, strategy_key: str, params: dict, days: int) -> dict:
    """一格 (symbol, timeframe, strategy)：28 種出場組合各跑 walk-forward 聚合 OOS。"""
    df = bar_cache.get_bars_cached(symbol, days=days, source="alpaca", timeframe=tf)
    if df.empty:
        return {"symbol": symbol, "timeframe": tf, "strategy": strategy_key,
                "error": "no_data", "exits": []}
    density = _bar_density(df)
    _apply_fold_windows(density)
    folds = walk_forward_splits(len(df))
    if not folds:
        return {"symbol": symbol, "timeframe": tf, "strategy": strategy_key,
                "error": "too_short", "exits": []}
    exits = [_wf_exit_metrics(strategy_key, params, df, spec, folds)
             for spec in _exit_grid(tf)]
    return {"symbol": symbol, "timeframe": tf, "strategy": strategy_key,
            "params": params, "days": days, "n_folds": len(folds), "exits": exits}


def _r2_passes(e: dict) -> bool:
    """Round 2 守門：OOS 樣本夠 + 樣本外正期望（無 IS 掃描故不設 gap 門檻）。"""
    return (e.get("oos_trips") or 0) >= settings.OPTIMIZER_MIN_OOS_TRIPS and (e.get("oos_ev") or 0) > 0


def aggregate_round2(cells: list[dict]) -> dict:
    """跨 symbol 聚合：每 (tf, strategy, 出場組合) 的通過檔數 + 通過檔平均指標。"""
    groups: dict[tuple, list[dict]] = {}
    for cell in cells:
        for e in cell.get("exits", []):
            groups.setdefault((cell["timeframe"], cell["strategy"], e["label"]), []).append(
                {**e, "symbol": cell["symbol"], "pass": _r2_passes(e)}
            )
    rows = []
    for (tf, strat, label), entries in groups.items():
        passed = [e for e in entries if e["pass"]]
        def _mean(key):
            vals = [e[key] for e in passed if isinstance(e.get(key), (int, float))]
            return round(sum(vals) / len(vals), 2) if vals else None
        rows.append({
            "timeframe": tf, "strategy": strat, "label": label,
            "exit_type": entries[0]["exit_type"],
            "pass_count": len(passed), "n_symbols": len(entries),
            "mean_oos_ev": _mean("oos_ev"), "mean_trips": _mean("oos_trips"),
            "mean_win_rate": _mean("oos_win_rate_pct"),
            "mean_pf": _mean("oos_profit_factor"),
            "mean_avg_r": _mean("oos_avg_r_multiple"),
            "pass_symbols": ",".join(e["symbol"] for e in passed),
        })
    return {"rows": rows}


def write_round2_reports(cells: list[dict], agg: dict, tf_order: list[str],
                         out_dir: Path, study_tag: str) -> Path:
    """Round 2 報表：每 (timeframe, strategy) 一張表——baseline 對照 + 出場組合排名。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "research-matrix-round2.csv"
    fields = ["symbol", "timeframe", "strategy", "label", "exit_type", "oos_ev",
              "oos_trips", "oos_win_rate_pct", "oos_profit_factor", "oos_avg_r_multiple", "pass"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for cell in cells:
            for e in cell.get("exits", []):
                w.writerow({**{k: e.get(k) for k in fields},
                            "symbol": cell["symbol"], "timeframe": cell["timeframe"],
                            "strategy": cell["strategy"], "pass": _r2_passes(e)})

    md_path = out_dir / "research-matrix-round2.md"
    rows = agg["rows"]
    lines = [
        "# 研究矩陣 Round 2 —— stop × R:R（M6）",
        "",
        f"- 日期：{date.today().isoformat()}；study_tag：`{study_tag}`",
        "- 輸入：Round 1 存活組合（每 timeframe 前 3 且守門通過 ≥3 檔）",
        f"- 出場網格：atr/swing × rr∈{{None,{','.join(str(r) for r in RR_GRID)}}}、"
        "fixed_pct 四型（只SL/只Trailing/SL+Trailing/SL+Target）、vwap（僅日內）",
        f"- 守門：OOS 交易 ≥{settings.OPTIMIZER_MIN_OOS_TRIPS} 且 OOS EV>0；"
        "排名鍵 =（通過檔數, 平均 OOS EV）",
        "- **判讀基準**：每張表第一列 baseline（無出場政策 = 純訊號出場）。"
        "出場組合沒贏過 baseline 就不值得加。",
        "",
    ]
    for tf in tf_order:
        tf_rows = [r for r in rows if r["timeframe"] == tf]
        if not tf_rows:
            continue
        lines.append(f"## {tf}\n")
        for strat in sorted({r["strategy"] for r in tf_rows}):
            block = [r for r in tf_rows if r["strategy"] == strat]
            base = next((r for r in block if r["label"] == "baseline"), None)
            ranked = sorted([r for r in block if r["label"] != "baseline"],
                            key=lambda r: (r["pass_count"], r["mean_oos_ev"] or float("-inf")),
                            reverse=True)
            lines += [f"### {strat}", "",
                      "| 出場組合 | 型 | 通過檔數 | 平均OOS EV | 平均交易 | 勝率% | PF | 平均R | 通過檔 |",
                      "|---|---|---|---|---|---|---|---|---|"]
            show = ([base] if base else []) + ranked[:8]
            for r in show:
                mark = "**baseline**" if r["label"] == "baseline" else r["label"]
                lines.append(
                    f"| {mark} | {r['exit_type']} | {r['pass_count']}/{r['n_symbols']} "
                    f"| {r['mean_oos_ev']} | {r['mean_trips']} | {r['mean_win_rate']} "
                    f"| {r['mean_pf']} | {r['mean_avg_r']} | {r['pass_symbols']} |"
                )
            lines.append("")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def run_round2(args, symbols: list[str], tf_list: list[str]) -> None:
    """Round 2 主流程：載存活組合 → 逐格跑（checkpoint 續跑）→ 聚合 → 報表。"""
    round1_dirs = sorted(CHECKPOINT_DIR.glob("m6-round1-*"))
    if not round1_dirs:
        raise SystemExit("找不到任何 Round 1 checkpoint，先跑 --round 1")
    survivors = load_round1_survivors(round1_dirs[-1])
    study_tag = f"m6-round2-{date.today().isoformat()}"
    ckpt_dir = CHECKPOINT_DIR / study_tag
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    jobs = [(tf, strat, sym)
            for tf in tf_list if tf in survivors
            for strat in survivors[tf]["strategies"]
            for sym in symbols
            if (strat, sym) in survivors[tf]["params"]]
    print(f"Round 2：{len(jobs)} 格（存活 timeframe：{', '.join(t for t in tf_list if t in survivors)}）",
          flush=True)

    cells: list[dict] = []
    t0 = time.monotonic()
    for n, (tf, strat, sym) in enumerate(jobs, 1):
        ckpt = ckpt_dir / f"{sym}-{tf}-{strat}.json"
        if ckpt.exists() and not args.force:
            cells.append(json.loads(ckpt.read_text(encoding="utf-8")))
            print(f"[{n}/{len(jobs)}] {sym} {tf} {strat} → checkpoint 命中，跳過", flush=True)
            continue
        t1 = time.monotonic()
        print(f"[{n}/{len(jobs)}] {sym} {tf} {strat} 掃描中 ...", flush=True)
        try:
            cell = run_round2_cell(sym, tf, strat, survivors[tf]["params"][(strat, sym)], args.days)
        except Exception as exc:
            cell = {"symbol": sym, "timeframe": tf, "strategy": strat,
                    "error": str(exc), "exits": []}
            print(f"    ❌ 失敗：{exc}", flush=True)
        ckpt.write_text(json.dumps(cell, ensure_ascii=False), encoding="utf-8")
        cells.append(cell)
        n_pass = sum(1 for e in cell.get("exits", []) if _r2_passes(e))
        print(f"    完成，出場組合守門通過 {n_pass}/{len(cell.get('exits', []))}，"
              f"耗時 {time.monotonic() - t1:.0f}s", flush=True)

    agg = aggregate_round2(cells)
    out_dir = ROOT / "docs" / "reference" / f"analysis-{date.today().isoformat()}"
    md = write_round2_reports(cells, agg, tf_list, out_dir, study_tag)
    print(f"\n總耗時 {(time.monotonic() - t0) / 60:.1f} 分；報表 → {md.relative_to(ROOT)}")


# ======================================================================
# Round 3：進場趨勢過濾器（Round 2 冠軍 × 6 filters，逐層 is_layer_worth_it）
# ======================================================================


def load_round2_champions(round2_dir: Path) -> list[dict]:
    """
    讀 Round 2 checkpoint → 每 timeframe 挑一個冠軍 (strategy, 出場組合)：
    排名鍵 =（守門通過檔數, 平均 OOS EV），baseline 也有資格當冠軍
    （出場政策全輸 baseline 時，Round 3 就在純訊號出場上測 filter——誠實）。
    :return: [{timeframe, strategy, exit_label, exit_policy, exit_params,
               params: {(strategy, sym): 策略參數}}]
    """
    cells = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(round2_dir.glob("*.json"))]
    if not cells:
        raise SystemExit(f"找不到 Round 2 checkpoint：{round2_dir}（先跑 --round 2）")
    rows = aggregate_round2(cells)["rows"]
    champions = []
    for tf in {r["timeframe"] for r in rows}:
        tf_rows = [r for r in rows if r["timeframe"] == tf and r["pass_count"] >= SURVIVOR_MIN_PASS]
        if not tf_rows:
            continue
        best = max(tf_rows, key=lambda r: (r["pass_count"], r["mean_oos_ev"] or float("-inf")))
        # 該冠軍組合的出場 spec + 各 symbol 策略參數（從 checkpoint 撈）
        exit_spec = None
        params_map = {}
        for cell in cells:
            if cell["timeframe"] != tf or cell["strategy"] != best["strategy"]:
                continue
            params_map[cell["symbol"]] = cell.get("params") or {}
            if exit_spec is None:
                e = next((e for e in cell.get("exits", []) if e["label"] == best["label"]), None)
                if e:
                    exit_spec = {"label": e["label"], "policy": e["policy"],
                                 "params": e.get("exit_params") or {}}
        if exit_spec is None:
            continue
        champions.append({"timeframe": tf, "strategy": best["strategy"],
                          "exit": exit_spec, "params": params_map,
                          "mean_oos_ev": best["mean_oos_ev"], "pass_count": best["pass_count"]})
    return champions


def _fold_evs(strategy_key: str, params: dict, df: pd.DataFrame, folds: list[dict],
              exit_spec: dict, filter_key: str | None,
              decision_gate: bool = False) -> list[float]:
    """
    每個 fold 的 OOS expected_value（is_layer_worth_it 的原料）。
    filter_key=None 且 decision_gate=False ＝ 不加層（baseline）。
    """
    from backend.services.decision_layer import apply_entry_gate
    from backend.services.trend_filters import apply_entry_filters, get_trend_filter

    evs = []
    for fold in folds:
        test_df = df.iloc[fold["test_start"]: fold["test_end"]].reset_index(drop=True)
        signals = _signals_for(strategy_key, params, test_df)
        if filter_key is not None:
            signals, _ = apply_entry_filters(signals, None, test_df,
                                             [get_trend_filter(filter_key)])
        if decision_gate:
            signals, _ = apply_entry_gate(signals, test_df)
        policy = (get_exit_policy(exit_spec["policy"], exit_spec["params"])
                  if exit_spec["policy"] else None)
        m = _simulate_from_signals(
            signals, test_df, 10000.0,
            commission_bps=settings.BACKTEST_COMMISSION_BPS,
            slippage_bps=settings.BACKTEST_SLIPPAGE_BPS,
            exit_policy=policy,
        )
        ev = m.get("expected_value")
        evs.append(float(ev) if isinstance(ev, (int, float)) else 0.0)
    return evs


def run_round3_cell(symbol: str, champ: dict, days: int) -> dict:
    """一格 (symbol, timeframe)：冠軍組合 baseline vs 各 filter 的逐 fold OOS 比較。"""
    from backend.services.trend_filters import FILTER_REGISTRY
    from backend.services.validation import is_layer_worth_it

    tf = champ["timeframe"]
    strategy_key = champ["strategy"]
    params = champ["params"].get(symbol)
    if params is None:
        return {"symbol": symbol, "timeframe": tf, "strategy": strategy_key,
                "error": "no_params", "filters": []}
    df = bar_cache.get_bars_cached(symbol, days=days, source="alpaca", timeframe=tf)
    if df.empty:
        return {"symbol": symbol, "timeframe": tf, "strategy": strategy_key,
                "error": "no_data", "filters": []}
    _apply_fold_windows(_bar_density(df))
    folds = walk_forward_splits(len(df))
    if len(folds) < settings.VALIDATION_MIN_FOLDS:
        return {"symbol": symbol, "timeframe": tf, "strategy": strategy_key,
                "error": f"folds<{settings.VALIDATION_MIN_FOLDS}", "filters": []}

    baseline_evs = _fold_evs(strategy_key, params, df, folds, champ["exit"], None)
    results = []
    for fkey in FILTER_REGISTRY:
        cand_evs = _fold_evs(strategy_key, params, df, folds, champ["exit"], fkey)
        verdict = is_layer_worth_it(baseline_evs, cand_evs)
        results.append({"filter": fkey, **verdict})
    return {"symbol": symbol, "timeframe": tf, "strategy": strategy_key,
            "exit_label": champ["exit"]["label"], "days": days,
            "n_folds": len(folds), "baseline_fold_evs": baseline_evs, "filters": results}


def write_round3_report(cells: list[dict], champions: list[dict],
                        tf_order: list[str], out_dir: Path, study_tag: str,
                        filename: str = "research-matrix-round3.md",
                        title: str = "研究矩陣 Round 3 —— 進場趨勢過濾器（M6）") -> Path:
    """worth 判定矩陣報表（Round 3 filters 與 Round 4 M10 層驗證共用同一格式）。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / filename
    lines = [
        f"# {title}",
        "",
        f"- 日期：{date.today().isoformat()}；study_tag：`{study_tag}`",
        "- 輸入：Round 2 每 timeframe 冠軍（策略 × 出場組合）；"
        "每 filter 用 `validation.is_layer_worth_it` 逐 fold OOS 判去留",
        f"- 判準：fold 數 ≥{settings.VALIDATION_MIN_FOLDS} 且 OOS 平均 EV 提升 "
        f"≥{settings.VALIDATION_MIN_IMPROVEMENT}（worth=True 才值得上線）",
        "- **加不了分就砍**（M5 框架建好 ≠ 該上線；macro 層的教訓）",
        "",
    ]
    for tf in tf_order:
        champ = next((c for c in champions if c["timeframe"] == tf), None)
        tf_cells = [c for c in cells if c["timeframe"] == tf and c.get("filters")]
        if not champ or not tf_cells:
            continue
        lines += [f"## {tf} —— 冠軍：{champ['strategy']} + {champ['exit']['label']}"
                  f"（Round 2 平均 OOS EV {champ['mean_oos_ev']}，通過 {champ['pass_count']} 檔）", ""]
        filter_keys = [f["filter"] for f in tf_cells[0]["filters"]]
        header = "| symbol | " + " | ".join(filter_keys) + " |"
        lines += [header, "|" + "---|" * (len(filter_keys) + 1)]
        worth_count = {k: 0 for k in filter_keys}
        for cell in sorted(tf_cells, key=lambda c: c["symbol"]):
            row = [cell["symbol"]]
            for f in cell["filters"]:
                mark = f"✅ +{f['improvement']:.0f}" if f["worth"] else f"❌ {f['improvement']:+.0f}"
                row.append(mark)
                if f["worth"]:
                    worth_count[f["filter"]] += 1
            lines.append("| " + " | ".join(row) + " |")
        n = len(tf_cells)
        lines.append("| **worth 檔數** | " +
                     " | ".join(f"**{worth_count[k]}/{n}**" for k in filter_keys) + " |")
        lines.append("")
    lines += [
        "## 判讀規則",
        "",
        f"- filter 在該 timeframe「worth 檔數 ≥ {SURVIVOR_MIN_PASS}」才建議上線；"
        "其餘一律不掛（改 HOLD 的每一筆都是放棄的利潤，沒有 OOS 證據就不付這個代價）。",
        "",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def run_round3(args, symbols: list[str], tf_list: list[str]) -> None:
    """Round 3 主流程：載 Round 2 冠軍 → 逐格 baseline vs filter → worth 矩陣報表。"""
    round2_dirs = sorted(CHECKPOINT_DIR.glob("m6-round2-*"))
    if not round2_dirs:
        raise SystemExit("找不到任何 Round 2 checkpoint，先跑 --round 2")
    champions = [c for c in load_round2_champions(round2_dirs[-1]) if c["timeframe"] in tf_list]
    study_tag = f"m6-round3-{date.today().isoformat()}"
    ckpt_dir = CHECKPOINT_DIR / study_tag
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    jobs = [(champ, sym) for champ in champions for sym in symbols]
    print(f"Round 3：{len(jobs)} 格（冠軍 timeframe：{', '.join(c['timeframe'] for c in champions)}）",
          flush=True)
    cells: list[dict] = []
    t0 = time.monotonic()
    for n, (champ, sym) in enumerate(jobs, 1):
        tf = champ["timeframe"]
        ckpt = ckpt_dir / f"{sym}-{tf}.json"
        if ckpt.exists() and not args.force:
            cells.append(json.loads(ckpt.read_text(encoding="utf-8")))
            print(f"[{n}/{len(jobs)}] {sym} {tf} → checkpoint 命中，跳過", flush=True)
            continue
        t1 = time.monotonic()
        print(f"[{n}/{len(jobs)}] {sym} {tf} {champ['strategy']}+{champ['exit']['label']} 掃描中 ...",
              flush=True)
        try:
            cell = run_round3_cell(sym, champ, args.days)
        except Exception as exc:
            cell = {"symbol": sym, "timeframe": tf, "strategy": champ["strategy"],
                    "error": str(exc), "filters": []}
            print(f"    ❌ 失敗：{exc}", flush=True)
        ckpt.write_text(json.dumps(cell, ensure_ascii=False), encoding="utf-8")
        cells.append(cell)
        n_worth = sum(1 for f in cell.get("filters", []) if f.get("worth"))
        print(f"    完成，worth {n_worth}/{len(cell.get('filters', []))}，"
              f"耗時 {time.monotonic() - t1:.0f}s", flush=True)

    out_dir = ROOT / "docs" / "reference" / f"analysis-{date.today().isoformat()}"
    md = write_round3_report(cells, champions, tf_list, out_dir, study_tag)
    print(f"\n總耗時 {(time.monotonic() - t0) / 60:.1f} 分；報表 → {md.relative_to(ROOT)}")


# ======================================================================
# Round 4：M10 AI Decision Layer 驗證（baseline vs gate / adaptive exit / 兩者）
# ======================================================================

# M10 的三個候選層（在 Round 2 冠軍組合上疊加比較）
R4_VARIANTS = [
    {"label": "decision_gate", "gate": True, "exit_override": None},
    {"label": "adaptive_exit", "gate": False,
     "exit_override": {"label": "adaptive", "policy": "adaptive", "params": {}}},
    {"label": "gate+adaptive", "gate": True,
     "exit_override": {"label": "adaptive", "policy": "adaptive", "params": {}}},
]


def run_round4_cell(symbol: str, champ: dict, days: int) -> dict:
    """一格 (symbol, timeframe)：冠軍組合 baseline vs M10 三個候選層的逐 fold OOS 比較。"""
    from backend.services.validation import is_layer_worth_it

    tf = champ["timeframe"]
    strategy_key = champ["strategy"]
    params = champ["params"].get(symbol)
    if params is None:
        return {"symbol": symbol, "timeframe": tf, "strategy": strategy_key,
                "error": "no_params", "filters": []}
    df = bar_cache.get_bars_cached(symbol, days=days, source="alpaca", timeframe=tf)
    if df.empty:
        return {"symbol": symbol, "timeframe": tf, "strategy": strategy_key,
                "error": "no_data", "filters": []}
    _apply_fold_windows(_bar_density(df))
    folds = walk_forward_splits(len(df))
    if len(folds) < settings.VALIDATION_MIN_FOLDS:
        return {"symbol": symbol, "timeframe": tf, "strategy": strategy_key,
                "error": f"folds<{settings.VALIDATION_MIN_FOLDS}", "filters": []}

    baseline_evs = _fold_evs(strategy_key, params, df, folds, champ["exit"], None)
    results = []
    for v in R4_VARIANTS:
        exit_spec = v["exit_override"] or champ["exit"]
        cand_evs = _fold_evs(strategy_key, params, df, folds, exit_spec,
                             None, decision_gate=v["gate"])
        verdict = is_layer_worth_it(baseline_evs, cand_evs)
        results.append({"filter": v["label"], **verdict})
    return {"symbol": symbol, "timeframe": tf, "strategy": strategy_key,
            "exit_label": champ["exit"]["label"], "days": days,
            "n_folds": len(folds), "baseline_fold_evs": baseline_evs, "filters": results}


def run_round4(args, symbols: list[str], tf_list: list[str]) -> None:
    """Round 4 主流程：結構與 Round 3 全同（同 checkpoint / 同報表格式），只換候選層。"""
    round2_dirs = sorted(CHECKPOINT_DIR.glob("m6-round2-*"))
    if not round2_dirs:
        raise SystemExit("找不到任何 Round 2 checkpoint，先跑 --round 2")
    champions = [c for c in load_round2_champions(round2_dirs[-1]) if c["timeframe"] in tf_list]
    study_tag = f"m10-layer-{date.today().isoformat()}"
    ckpt_dir = CHECKPOINT_DIR / study_tag
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    jobs = [(champ, sym) for champ in champions for sym in symbols]
    print(f"Round 4（M10 層驗證）：{len(jobs)} 格", flush=True)
    cells: list[dict] = []
    t0 = time.monotonic()
    for n, (champ, sym) in enumerate(jobs, 1):
        tf = champ["timeframe"]
        ckpt = ckpt_dir / f"{sym}-{tf}.json"
        if ckpt.exists() and not args.force:
            cells.append(json.loads(ckpt.read_text(encoding="utf-8")))
            print(f"[{n}/{len(jobs)}] {sym} {tf} → checkpoint 命中，跳過", flush=True)
            continue
        t1 = time.monotonic()
        print(f"[{n}/{len(jobs)}] {sym} {tf} {champ['strategy']}+{champ['exit']['label']} 掃描中 ...",
              flush=True)
        try:
            cell = run_round4_cell(sym, champ, args.days)
        except Exception as exc:
            cell = {"symbol": sym, "timeframe": tf, "strategy": champ["strategy"],
                    "error": str(exc), "filters": []}
            print(f"    ❌ 失敗：{exc}", flush=True)
        ckpt.write_text(json.dumps(cell, ensure_ascii=False), encoding="utf-8")
        cells.append(cell)
        n_worth = sum(1 for f in cell.get("filters", []) if f.get("worth"))
        print(f"    完成，worth {n_worth}/{len(cell.get('filters', []))}，"
              f"耗時 {time.monotonic() - t1:.0f}s", flush=True)

    out_dir = ROOT / "docs" / "reference" / f"analysis-{date.today().isoformat()}"
    # 報表沿用 Round 3 的 worth 矩陣格式（filter 欄換成 M10 三候選層）
    md = write_round3_report(cells, champions, tf_list, out_dir, study_tag,
                             filename="research-matrix-round4-m10.md",
                             title="研究矩陣 Round 4 —— M10 AI Decision Layer 驗證")
    print(f"\n總耗時 {(time.monotonic() - t0) / 60:.1f} 分；報表 → {md.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="研究矩陣批跑（M6）")
    parser.add_argument("--round", type=int, default=1, choices=[1, 2, 3, 4],
                        help="第幾輪（1=timeframe 海選；2=stop×R:R；3=filters；4=M10 層驗證）")
    parser.add_argument("--symbols", default=",".join(CORE_POOL))
    parser.add_argument("--timeframes", default=",".join(timeframes.ALL_TIMEFRAMES))
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--force", action="store_true", help="忽略 checkpoint 全部重算")
    parser.add_argument("--no-db", action="store_true", help="冠軍不落 BacktestRun")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    tf_list = [timeframes.validate(t.strip()) for t in args.timeframes.split(",") if t.strip()]

    if args.round == 2:
        run_round2(args, symbols, tf_list)
        return
    if args.round == 3:
        run_round3(args, symbols, tf_list)
        return
    if args.round == 4:
        run_round4(args, symbols, tf_list)
        return

    study_tag = f"m6-round1-{date.today().isoformat()}"
    ckpt_dir = CHECKPOINT_DIR / study_tag
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    cells: list[dict] = []
    total = len(symbols) * len(tf_list)
    done = 0
    t0 = time.monotonic()
    for tf in tf_list:
        for sym in symbols:
            done += 1
            ckpt = ckpt_dir / f"{sym}-{tf}.json"
            if ckpt.exists() and not args.force:
                cells.append(json.loads(ckpt.read_text(encoding="utf-8")))
                print(f"[{done}/{total}] {sym} {tf} → checkpoint 命中，跳過", flush=True)
                continue
            t1 = time.monotonic()
            print(f"[{done}/{total}] {sym} {tf} 掃描中 ...", flush=True)
            try:
                cell = run_cell(sym, tf, args.days)
            except Exception as exc:
                cell = {"symbol": sym, "timeframe": tf, "days": args.days,
                        "error": str(exc), "strategies": []}
                print(f"    ❌ 失敗：{exc}", flush=True)
            ckpt.write_text(json.dumps(cell, ensure_ascii=False), encoding="utf-8")
            cells.append(cell)
            if not args.no_db and cell.get("strategies"):
                _save_champion_to_db(cell, study_tag)
            n_pass = sum(1 for r in cell.get("strategies", []) if _passes_gate(r))
            print(f"    完成，策略守門通過 {n_pass}/{len(cell.get('strategies', []))}，"
                  f"耗時 {time.monotonic() - t1:.0f}s", flush=True)

    ranking = aggregate(cells)
    out_dir = ROOT / "docs" / "reference" / f"analysis-{date.today().isoformat()}"
    md = write_reports(cells, ranking, tf_list, out_dir, study_tag)
    print(f"\n總耗時 {(time.monotonic() - t0) / 60:.1f} 分；榜單 → {md.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
