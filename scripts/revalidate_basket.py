"""
多標的籃子全庫重驗（Phase 12 一次性維運）
==========================================
情境：驗證從「單檔 SPY」升級成「跨產業一籃子」（evolution._validate_basket）後，要把**既有**
知識庫所有列用新籃子**重跑回測**重判。這次必須重跑（不像 rejudge_noop 只重套判準），
因為換了驗證標的、folds 要重算。

對象：status in (candidate, validated, curated) 逐筆 validate_candidate(row, 籃子)。
結果自然流轉：
  - candidate / validated → 照 verdict 變 validated / rejected。
  - ★ curated 過不了 → **降級**（curated 是人晉升的，降級前印明顯警告行）。

★ 這支會**寫共用 Neon DB**（另一台機器也讀同一份）。預設 **dry-run 只印不改**；
  真要動手加 `--apply`。dry-run 會逐筆跑回測（吃 CPU）但跑完 rollback、不留痕。

失敗隔離（單筆炸不擋整批）：比照 auto_validate.record_validation_failure——
  apply 模式下單筆例外記失敗計數、維持原狀、繼續下一筆；dry-run 只印。

★ JSON 欄位陷阱：validate_candidate 內部已整顆重建 oos_metrics 再賦值（持久化正確）。

執行（專案根目錄，需有 .env 指向 Neon）：
    venv\\Scripts\\python.exe scripts\\revalidate_basket.py            # 只看報告（dry-run）
    venv\\Scripts\\python.exe scripts\\revalidate_basket.py --apply    # 真的重驗 + 寫 DB
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import settings
from backend.database import SessionLocal
from backend.models.strategy_knowledge import StrategyKnowledge
from backend.services import auto_validate
from backend.services.evolution import validate_candidate

# 要重驗的狀態（rejected 不重驗——已淘汰；如需復活由人改回 candidate）
_TARGET_STATUSES = ("candidate", "validated", "curated")


def _ev_of(oos: dict) -> float:
    ev = (oos or {}).get("expected_value")
    return ev if isinstance(ev, (int, float)) else float("nan")


def _per_symbol_brief(oos: dict) -> str:
    """把 per_symbol 分布壓成一行（達標檔 / 被排除檔）。單檔路徑沒有 per_symbol。"""
    per = (oos or {}).get("per_symbol")
    if not per:
        sym = (oos or {}).get("symbol")
        return f"單檔 {sym}" if sym else "（無 per_symbol）"
    ok = [f"{s['symbol']}={s['mean_ev']}" for s in per if s.get("qualified")]
    excl = [f"{s['symbol']}({s.get('excluded') or '排除'})" for s in per if not s.get("qualified")]
    parts = [f"達標 {len(ok)}：{', '.join(ok) or '無'}"]
    if excl:
        parts.append(f"排除 {len(excl)}：{', '.join(excl)}")
    return " ｜ ".join(parts)


def main() -> int:
    apply = "--apply" in sys.argv
    symbols = settings.auto_validate_symbols
    days = settings.AUTO_VALIDATE_DAYS

    print(f"重驗籃子：{symbols}（每檔 days={days}，門檻 X="
          f"{settings.AUTO_VALIDATE_MIN_TRADES_PER_SYMBOL}）")
    print(f"模式：{'APPLY（會寫 Neon）' if apply else 'dry-run（只印不改，跑完 rollback）'}\n")

    db = SessionLocal()
    try:
        rows = (
            db.query(StrategyKnowledge)
            .filter(StrategyKnowledge.status.in_(_TARGET_STATUSES))
            .order_by(StrategyKnowledge.id)
            .all()
        )
        print(f"待重驗 {len(rows)} 筆（{', '.join(_TARGET_STATUSES)}）…\n")

        downgraded_curated = []  # 過不了的 curated（最需人注意）
        changed = []             # 其他狀態變動
        unchanged = []
        failed = []

        for r in rows:
            old = r.status
            name, key, kid = r.name, r.strategy_key, r.id
            try:
                summary = validate_candidate(r, symbols, days=days)
            except Exception as e:
                failed.append((kid, name, key, str(e)[:120]))
                if apply:
                    # 失敗隔離：記失敗計數、維持原狀、逐筆 commit（防中途斷）
                    auto_validate.record_validation_failure(r, str(e))
                    db.commit()
                else:
                    db.rollback()
                continue

            new = summary["status"]
            oos = summary["oos_metrics"]
            line = (f"#{kid} {name}（{key}）{old}→{new} "
                    f"EV={_ev_of(oos)} ｜ {_per_symbol_brief(oos)}")

            if old == "curated" and new != "curated":
                downgraded_curated.append(line)
            elif old != new:
                changed.append(line)
            else:
                unchanged.append(line)

            if apply:
                db.commit()          # 逐筆 commit，防中途斷
            else:
                db.rollback()        # dry-run：丟棄記憶體變動，不留痕

        # ---- 報告 ----
        if downgraded_curated:
            print("⚠️⚠️ curated 降級（人晉升過的、這次沒過閘，務必確認）⚠️⚠️")
            for ln in downgraded_curated:
                print(f"  {ln}")
            print()
        print(f"── 狀態變動（非 curated 降級）：{len(changed)} 筆 ──")
        for ln in changed:
            print(f"  {ln}")
        print(f"\n── 狀態不變：{len(unchanged)} 筆 ──")
        for ln in unchanged:
            print(f"  {ln}")
        if failed:
            print(f"\n── 失敗（隔離，不擋整批）：{len(failed)} 筆 ──")
            for kid, name, key, err in failed:
                print(f"  #{kid} {name}（{key}）：{err}")

        if apply:
            print(f"\n✅ 已重驗並寫入 Neon。curated 降級 {len(downgraded_curated)} 筆、"
                  f"其他變動 {len(changed)} 筆、不變 {len(unchanged)} 筆、失敗 {len(failed)} 筆。")
            print("→ 新 validated 去 LibraryPage 由人逐筆晉升 curated。")
        else:
            print(f"\n[dry-run] 以上為預演（已 rollback、未寫 DB）。確認合理後加 --apply 真的重驗。")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
