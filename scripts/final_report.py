"""
Phase 16 最終報告（M12）—— 聚合 M6/M7/M8/M10 產出
===================================================
輸出使用者要的 13 項：架構修改摘要、修改檔案清單、回測流程、walk-forward 結果、
OOS 統計、timeframe 比較、stop strategy 比較、R:R 比較、股票池縮減依據、
半導體 RS 篩選結果、scanner 效能分析、IS vs OOS 過擬合分析、最終建議上線組合。

資料來源（全部讀既有產出，不重跑回測）：
  - M6 Round 1~4 checkpoint（data/research/m6-round*/、m10-layer-*/）
  - M7 股票池報告（docs/reference/analysis-*/stock-pool.md，引用不重算）
  - 報表落 docs/reference/analysis-<今天>/final-report.md

用法：
    venv\\Scripts\\python.exe scripts\\final_report.py
"""

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from scripts import research_matrix as rm  # noqa: E402  # 聚合函式復用，不重造

from backend.config import settings  # noqa: E402
from backend.services import timeframes  # noqa: E402


def _load_cells(pattern: str) -> list[dict]:
    """讀某輪最新一批 checkpoint（沒有 → 空 list，該節誠實標「未跑」）。"""
    dirs = sorted(rm.CHECKPOINT_DIR.glob(pattern))
    if not dirs:
        return []
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(dirs[-1].glob("*.json"))]


def _fmt(v, nd=1):
    return "—" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


# ---------------------------------------------------------------------------
# 各節組裝
# ---------------------------------------------------------------------------

def _sec_architecture() -> list[str]:
    return [
        "## 1. 架構修改摘要（Phase 16）",
        "",
        "| 里程碑 | 內容 | 關鍵產物 |",
        "|---|---|---|",
        "| M1 | 選主鎖修復（租約制 + 下單第三閘） | scheduler_lock / lease daemon |",
        "| M2 | 多 timeframe 資料地基（1Min~1Day 全鏈） | services/timeframes.py、bar_cache 分框架存 |",
        "| M3/M3.5 | walk-forward 聚合 OOS + 排名守門 + 前端欄位 | optimizer._wf_aggregate、overfit_gap |",
        "| M4 | 可插拔出場政策（fixed_pct/atr/swing/vwap + R:R） | services/exit_policies.py，回測實盤共用 |",
        "| M5 | 進場趨勢過濾器框架（6 filters） | services/trend_filters.py |",
        "| M6 | 研究矩陣四輪漏斗（本報告數據來源） | scripts/warm_cache.py、scripts/research_matrix.py |",
        "| M7 | RS 模組 + 股票池瘦身建議 38→20 | services/relative_strength.py、sectors.py |",
        "| M8 | 日內單一掃描迴圈（批次抓全池） | bot_manager.run_intraday_scan + 預取快取 |",
        "| M9 | 4 支報告腳本進 scheduler（週一自動） | bot_manager.schedule_weekly_reports |",
        "| M10 | AI Decision Layer（規則式 entry gate + 動態出場） | services/decision_layer.py、AdaptiveExitPolicy |",
        "",
    ]


def _sec_files() -> list[str]:
    return [
        "## 2. 修改檔案清單（Phase 16 主要）",
        "",
        "- 新增：`backend/services/timeframes.py`、`exit_policies.py`、`trend_filters.py`、"
        "`relative_strength.py`、`sectors.py`、`decision_layer.py`",
        "- 新增：`scripts/warm_cache.py`、`scripts/research_matrix.py`、`scripts/final_report.py`",
        "- 修改：`backend/services/optimizer.py`（walk-forward 聚合 + 守門）、"
        "`backtest_engine.py`（exit_policy 掛點）、`bot_manager.py`（M8 掃描迴圈 + M4 實盤出場）、"
        "`alpaca_client.py`（token bucket 限流 + 批次 API）、`config.py`（相關開關）",
        "- 測試：`tests/test_exit_policies.py`、`test_trend_filters.py`、`test_decision_layer.py`、"
        "`test_intraday_scan.py`、`test_optimizer_walkforward.py`、`test_timeframes.py` 等",
        "",
    ]


def _sec_pipeline() -> list[str]:
    return [
        "## 3. 回測流程（誠實性設計）",
        "",
        "1. 資料：Alpaca IEX 免費源 → 本機 parquet 快取（`warm_cache.py` 預熱；"
        "稀疏率體檢 RTH 5~8%，品質足夠、免上付費數據）。",
        "2. 模擬：訊號於**次根開盤成交**（不偷看未來）、含滑價 5bps；"
        "出場觸價 intrabar 保守（同根破兩邊先算 stop）。",
        "3. 驗證：walk-forward 滾動切分（fold 窗按 bar 密度換算成等效交易日 180/60/60），"
        "**所有排名/守門只看跨折聚合 OOS**（交易 ≥20、過擬合差距 ≤0.5、EV>0）。",
        "4. 漏斗：Round 1 timeframe 海選 → Round 2 stop×R:R → Round 3 filters → "
        "Round 4 AI decision layer，逐層 `is_layer_worth_it`，加不了分就砍。",
        "",
    ]


def _sec_round1(cells: list[dict]) -> list[str]:
    if not cells:
        return ["## 4~6. walk-forward / OOS / timeframe 比較", "", "（Round 1 未跑）", ""]
    ranking = rm.aggregate(cells)
    lines = [
        "## 4. Walk-forward 結果 + 5. OOS 統計 + 6. Timeframe 比較（Round 1）",
        "",
        f"- 池：核心 6 檔（stock-pool 體檢核心池）× 9 策略 × 8 timeframe × 730 天",
        "- 表格值 = 守門通過檔的平均聚合 OOS EV（$/筆，$10k 本金）；「通過」= "
        f"OOS 交易 ≥{settings.OPTIMIZER_MIN_OOS_TRIPS} 且 gap ≤{settings.OPTIMIZER_MAX_OVERFIT_GAP} 且 EV>0",
        "",
        "| timeframe | 冠軍策略 | 通過檔數 | 平均OOS EV | 平均OOS交易 | 年交易估 | 判讀 |",
        "|---|---|---|---|---|---|---|",
    ]
    for tf in timeframes.ALL_TIMEFRAMES:
        rows = ranking.get(tf)
        if not rows:
            continue
        top = rows[0]
        if top["pass_count"] == 0:
            lines.append(f"| {tf} | — | 0 | — | — | — | 全滅（無守門通過組合） |")
            continue
        note = ("甜蜜點" if top["pass_count"] >= 5 else
                "可用" if top["pass_count"] >= 3 else "偏弱")
        pdt = " ⚠️PDT" if (timeframes.is_intraday(tf) and top["mean_trades_per_year"]
                           and top["mean_trades_per_year"] > rm.PDT_TRADES_PER_YEAR) else ""
        lines.append(
            f"| {tf} | {top['strategy']} | {top['pass_count']}/{top['n_symbols']} "
            f"| {_fmt(top['mean_oos_ev'])} | {_fmt(top['mean_trips'])} "
            f"| {_fmt(top['mean_trades_per_year'])}{pdt} | {note} |")
    lines += [
        "",
        "**判讀**：甜蜜點在 30Min~4Hour（多檔普遍通過、EV 高、年交易 17~80 次無 PDT）；"
        "1Min 幾乎全滅（僅 momentum）、1Day 僅 stochastic 存活。"
        "完整榜單見 `research-matrix-round1.md`。",
        "",
    ]
    return lines


def _sec_round2(cells: list[dict]) -> list[str]:
    if not cells:
        return ["## 7. Stop strategy 比較 + 8. R:R 比較", "", "（Round 2 未跑）", ""]
    rows = rm.aggregate_round2(cells)["rows"]

    lines = ["## 7. Stop strategy 比較（Round 2）", "",
             "每 (timeframe, 策略) 比：baseline（純訊號出場）vs 各出場政策最佳者：", "",
             "| timeframe | 策略 | baseline EV | 最佳出場組合 | 其 EV | 出場有加分？ |",
             "|---|---|---|---|---|---|"]
    beat, total = 0, 0
    rr_bucket: dict[str, list[float]] = {}
    for tf in timeframes.ALL_TIMEFRAMES:
        for strat in sorted({r["strategy"] for r in rows if r["timeframe"] == tf}):
            block = [r for r in rows if r["timeframe"] == tf and r["strategy"] == strat]
            base = next((r for r in block if r["label"] == "baseline"), None)
            cands = [r for r in block if r["label"] != "baseline" and r["pass_count"] >= 3]
            if not base or not cands:
                continue
            best = max(cands, key=lambda r: (r["pass_count"], r["mean_oos_ev"] or -1e18))
            better = ((best["pass_count"], best["mean_oos_ev"] or -1e18)
                      > (base["pass_count"], base["mean_oos_ev"] or -1e18))
            total += 1
            beat += bool(better)
            lines.append(
                f"| {tf} | {strat} | {_fmt(base['mean_oos_ev'])}（{base['pass_count']}檔） "
                f"| {best['label']} | {_fmt(best['mean_oos_ev'])}（{best['pass_count']}檔） "
                f"| {'✅ 贏' if better else '❌ 沒贏'} |")
            # R:R 統計原料：label 帶 rr 的組合
            for r in block:
                if "_rr" in r["label"] and r["mean_oos_ev"] is not None and r["pass_count"] >= 3:
                    rr = r["label"].split("_rr")[-1]
                    rr_bucket.setdefault(rr, []).append(r["mean_oos_ev"])
    lines += [
        "",
        f"**結論**：{total} 組比較中，出場政策贏過 baseline 的只有 {beat} 組——"
        "**均值回歸型策略（rsi/bollinger）掛 stop 反而砍掉回彈利潤**，訊號出場已是強基準。"
        "出場政策的價值在「定義 R、供券商端 GTC 保護單」（實盤防斷線）而非拉 EV。",
        "",
        "## 8. R:R 比較（Round 2，跨所有存活組合）",
        "",
        "| rr | 樣本組數 | 平均 OOS EV |",
        "|---|---|---|",
    ]
    for rr in ["None", "1.5", "2", "2.2", "2.5", "3", "4"]:
        vals = rr_bucket.get(rr)
        if vals:
            lines.append(f"| {rr if rr != 'None' else '無 target（只SL）'} | {len(vals)} "
                         f"| {sum(vals) / len(vals):.1f} |")
    lines += ["", "**判讀**：rr 越大 EV 遞增（target 越遠越不截斷趨勢），"
              "rr=None/4 通常最好——與第 7 節同一結論：這批策略的出場截斷傷害 > 保護收益。", ""]
    return lines


def _sec_pool() -> list[str]:
    return [
        "## 9. 股票池縮減依據 + 10. 半導體 RS 篩選（M7）",
        "",
        "- 規則：OOS EV>0 才有資格；指數 ETF 保留；**同 sector 只留 RS 綜合分前 3**"
        "（RS = 1/5/20 日「報酬 − SPY」等權）；上限 20（核心池優先）。",
        "- 結果：38 → 20 檔（建議 `.env` 字串已產出，**人核准後才改**）。",
        "- 半導體 sector（NVDA/AMD/AVGO/TSM/INTC/QCOM/MU/AMAT/LRCX/ASML 10 檔）"
        "RS 篩選留：**AMAT（RS 11.2）、LRCX（3.98）、ASML（1.84）**——"
        "科技股同池競爭下 RS 前 3；核心池的 AMD/AVGO/INTC 因 RS 落後未進瘦身清單，"
        "但 OOS 樣本最足（本研究矩陣即用它們驗證）。",
        "- 完整依據表：`docs/reference/analysis-2026-07-02/stock-pool.md`。",
        "",
    ]


def _sec_scanner() -> list[str]:
    return [
        "## 11. Scanner 效能分析（M8）",
        "",
        "- 舊：38 bot × 各自 interval job 各抓 K 線 → 30s 掃描 = 76+ req/min，撞免費版 200 上限。",
        "- 新：單一 30s job：每 timeframe 1 次 `get_bars_multi` + 1 次 `get_latest_prices` + "
        "1 次 `list_positions` ≈ **6 req/min**（降 ~92%），逐 bot 派發走既有 run_bot_once（零分岔）。",
        "- 進場訊號只用已收完 bar；快取過期自動退回單檔路徑；1Day bot 保留 per-bot job（300s）。",
        "- 單輪耗時：程式內建量測（目標 <5s），**盤中實測待常駐機器開跑後回填**。",
        "",
    ]


def _sec_overfit(cells: list[dict]) -> list[str]:
    if not cells:
        return ["## 12. IS vs OOS 過擬合分析", "", "（Round 1 未跑）", ""]
    gaps = [r["overfit_gap"] for c in cells for r in c.get("strategies", [])
            if isinstance(r.get("overfit_gap"), (int, float))]
    high = sum(1 for g in gaps if g > settings.OPTIMIZER_MAX_OVERFIT_GAP)
    neg = sum(1 for g in gaps if g < 0)
    lines = [
        "## 12. IS vs OOS 過擬合分析（Round 1 全格）",
        "",
        f"- 可算 gap 的組合 {len(gaps)} 組（gap = (IS−OOS)/|IS|；IS≤0 無意義不計）。",
        f"- gap > {settings.OPTIMIZER_MAX_OVERFIT_GAP}（樣本外掉超過一半，守門沉底）：{high} 組"
        f"（{high / len(gaps) * 100:.0f}%）。" if gaps else "",
        f"- gap < 0（OOS 反而優於 IS，健康）：{neg} 組（{neg / len(gaps) * 100:.0f}%）。" if gaps else "",
        "- 防線：排名守門直接沉底高 gap 組合 + 挑冠軍只看跨折聚合 OOS（樣本 ≥20 筆）"
        "——「1~2 筆 100% 勝率」的假冠軍在 stock-pool 體檢已驗證過是噪音。",
        "",
    ]
    return [x for x in lines if x != ""] + [""] if gaps else lines


def _layer_by_tf(cells: list[dict]) -> dict[str, dict[str, dict]]:
    """Round 3/4 checkpoint → {tf: {layer: {worth, n, sum_imp}}}（逐 timeframe 統計）。"""
    out: dict[str, dict[str, dict]] = {}
    for c in cells:
        for f in c.get("filters", []):
            slot = out.setdefault(c["timeframe"], {}).setdefault(
                f["filter"], {"worth": 0, "n": 0, "sum_imp": 0.0})
            slot["n"] += 1
            slot["worth"] += bool(f.get("worth"))
            if isinstance(f.get("improvement"), (int, float)):
                slot["sum_imp"] += f["improvement"]
    return out


def _recommended_layers(per_tf: dict[str, dict]) -> list[str]:
    """該 timeframe 建議上線的層：worth ≥ SURVIVOR_MIN_PASS **且改善總和 > 0**。

    後者擋掉「全 +0」的無作為層（例如 decision_gate 幾乎沒攔到單——
    形式上 worth（提升 ≥0 含平手）但沒有任何加分證據，不值得付複雜度）。
    """
    return [layer for layer, s in per_tf.items()
            if s["worth"] >= rm.SURVIVOR_MIN_PASS and s["sum_imp"] > 0]


def _sec_final(cells1, cells2, cells3, cells4) -> list[str]:
    lines = ["## 13. 最終建議上線組合", ""]
    if not cells2:
        return lines + ["（Round 2 未跑，無法給建議）", ""]
    champions = []
    r2_dirs = sorted(rm.CHECKPOINT_DIR.glob("m6-round2-*"))
    if r2_dirs:
        champions = rm.load_round2_champions(r2_dirs[-1])
    layers3 = _layer_by_tf(cells3)
    layers4 = _layer_by_tf(cells4)

    # Round 1 的年交易估（PDT 標註原料）
    trades_est: dict[tuple, float] = {}
    for c in cells1:
        for r in c.get("strategies", []):
            key = (c["timeframe"], r["strategy"])
            if r.get("est_trades_per_year"):
                trades_est.setdefault(key, r["est_trades_per_year"])

    lines += [
        "（filter / decision layer 欄 = 該 timeframe「worth ≥3 檔且改善總和 >0」的層；"
        "逐 timeframe 各自判定，加不了分就不掛）",
        "",
        "| timeframe | 策略 | 出場 | filter | decision layer | PDT | 建議 |",
        "|---|---|---|---|---|---|---|",
    ]
    for champ in sorted(champions, key=lambda c: timeframes.ALL_TIMEFRAMES.index(c["timeframe"])):
        tf, strat = champ["timeframe"], champ["strategy"]
        filters_on = ", ".join(_recommended_layers(layers3.get(tf, {}))) or "不掛"
        layer_on = ", ".join(_recommended_layers(layers4.get(tf, {}))) or "不掛"
        est = trades_est.get((tf, strat))
        pdt = "⚠️" if (timeframes.is_intraday(tf) and est and est > rm.PDT_TRADES_PER_YEAR) else "—"
        tier = ("★ 主力" if tf in ("30Min", "1Hour", "2Hour", "4Hour") else "觀察")
        lines.append(f"| {tf} | {strat} | {champ['exit']['label']} | {filters_on} "
                     f"| {layer_on} | {pdt} | {tier} |")
    lines += [
        "",
        "**建議**：",
        "1. **主力 timeframe：1Hour~2Hour**（bollinger/rsi 6 檔普遍通過、OOS EV 200+/筆、"
        "年交易 ~20 次無 PDT）；30Min/4Hour 次之。",
        "2. **出場**：多數組合 baseline（訊號出場）EV 最高，但實盤仍建議掛 champion 出場政策"
        "（swing/atr）供券商端 GTC 保護——付少量 EV 買斷線保護，屬保險費。",
        "3. **池**：先跑 M7 瘦身後 20 檔（等人核准 `.env`）；研究矩陣證據來自核心 6 檔，"
        "擴池後建議重跑 Round 1 驗證外推性。",
        "4. **人在迴路**：以上僅建議，上線與改 `.env` 由人決定；真錢另過董事會核准（Phase 10）。",
        "",
    ]
    return lines


def run(out_dir: Path | None = None) -> str:
    """組報告寫檔，回 markdown 全文（M9 scheduler 相容介面）。"""
    cells1 = _load_cells("m6-round1-*")
    cells2 = _load_cells("m6-round2-*")
    cells3 = _load_cells("m6-round3-*")
    cells4 = _load_cells("m10-layer-*")

    lines = [
        "# Phase 16 最終報告（M12）",
        "",
        f"- 產出日期：{date.today().isoformat()}；資料：核心 6 檔 × 730 天，walk-forward 聚合 OOS",
        "- 漏斗 checkpoint：Round1 "
        f"{len(cells1)} 格 / Round2 {len(cells2)} 格 / Round3 {len(cells3)} 格 / "
        f"Round4(M10) {len(cells4)} 格",
        "",
    ]
    lines += _sec_architecture()
    lines += _sec_files()
    lines += _sec_pipeline()
    lines += _sec_round1(cells1)
    lines += _sec_round2(cells2)
    lines += _sec_pool()
    lines += _sec_scanner()
    lines += _sec_overfit(cells1)

    # Round 3 / 4 摘要（詳表在各自報告檔）
    for title, cells, ref in [
        ("Filters（Round 3）", cells3, "research-matrix-round3.md"),
        ("AI Decision Layer（Round 4 / M10）", cells4, "research-matrix-round4-m10.md"),
    ]:
        lines += [f"### 附：{title} worth 摘要", ""]
        if not cells:
            lines += ["（未跑）", ""]
            continue
        by_tf = _layer_by_tf(cells)
        layer_names = sorted({k for per in by_tf.values() for k in per})
        lines += ["| 層 | 建議上線的 timeframe（worth ≥3 檔且改善總和 >0） |", "|---|---|"]
        for layer in layer_names:
            tfs = [tf for tf in timeframes.ALL_TIMEFRAMES
                   if layer in _recommended_layers(by_tf.get(tf, {}))]
            lines.append(f"| {layer} | {', '.join(tfs) if tfs else '—（全不掛）'} |")
        lines += ["", f"詳表：`{ref}`", ""]

    lines += _sec_final(cells1, cells2, cells3, cells4)

    out_dir = out_dir or (ROOT / "docs" / "reference" / f"analysis-{date.today().isoformat()}")
    out_dir.mkdir(parents=True, exist_ok=True)
    md = "\n".join(lines) + "\n"
    path = out_dir / "final-report.md"
    path.write_text(md, encoding="utf-8")
    print(f"最終報告 → {path.relative_to(ROOT)}")
    return md


if __name__ == "__main__":
    run()
