"""
no-op 重判（Phase 12 一次性維運）
==================================
情境：修掉「no-op 漏洞」（evolution.is_noop 守門）後，要把**既有** status=validated 裡
「所有 fold 零交易」的列退回 rejected——它們當初純因 EV=0 跟「不出手」基準打平而假性過閘。

做法：**不重跑回測**。walk-forward folds 才剛於 2026-06-17 算過、存在 oos_metrics["walk_forward"]，
直接套同一支 evolution.is_noop 重判即可（判準與 validate_candidate 共用，零分岔）。

★ 這支會**寫共用 Neon DB**（另一台機器也讀同一份）。預設 **dry-run 只印不改**；
  真要動手加 `--apply`。

退掉的列會就地重建 oos_metrics 掛上 "noop" 標記（與 validate_candidate 的 no-op reject 同形），
保留原 walk_forward / single_split 供稽核。缺 walk_forward 的（手動建的舊列）跳過不動。

★ JSON 欄位陷阱：Column(JSON) 沒掛 MutableDict，就地 mutate 不會被 SQLAlchemy 偵測、
  不會持久化——一律**重建 dict 後重新賦值**（比照 auto_validate.record_validation_failure）。

執行（專案根目錄，需有 .env 指向 Neon）：
    venv\\Scripts\\python.exe scripts\\rejudge_noop.py            # 只看報告（dry-run）
    venv\\Scripts\\python.exe scripts\\rejudge_noop.py --apply    # 真的把 no-op 退成 rejected
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import SessionLocal
from backend.models.strategy_knowledge import StrategyKnowledge
from backend.services.evolution import is_noop


def _ev_of(row) -> float:
    ev = (row.oos_metrics or {}).get("expected_value")
    return ev if isinstance(ev, (int, float)) else float("nan")


def _mark_noop(row) -> None:
    """把一筆 validated 退成 rejected(no-op)；整顆重建 oos_metrics 才會持久化。"""
    prev = row.oos_metrics or {}
    row.oos_metrics = {
        "expected_value": 0.0,
        "noop": {
            "reason": "所有 fold 零交易（num_round_trips 全 0）＝沒下場的 no-op，非真加分",
            "total_round_trips": 0,
            "rejudged": True,  # 標明是重判腳本退的（非 validate_candidate 當下判的）
        },
        "walk_forward": prev.get("walk_forward", []),
        "single_split": prev.get("single_split"),
        "symbol": prev.get("symbol"),
        "days": prev.get("days"),
    }
    row.status = "rejected"


def main() -> int:
    apply = "--apply" in sys.argv

    db = SessionLocal()
    try:
        rows = (
            db.query(StrategyKnowledge)
            .filter(StrategyKnowledge.status == "validated")
            .order_by(StrategyKnowledge.id)
            .all()
        )
        print(f"目前 status=validated 共 {len(rows)} 筆，逐筆重判 no-op…\n")

        noop_rows, keep_rows, skipped = [], [], []
        for r in rows:
            folds = (r.oos_metrics or {}).get("walk_forward")
            if folds is None:
                skipped.append(r)  # 沒 walk_forward（手動建的舊列）不動
            elif is_noop(folds):
                noop_rows.append(r)
            else:
                keep_rows.append(r)

        print(f"── no-op（將退成 rejected）：{len(noop_rows)} 筆 ──")
        for r in noop_rows:
            print(f"  #{r.id} {r.name}（{r.strategy_key}）EV={_ev_of(r)}")
        print(f"\n── 保留 validated（B 可晉升）：{len(keep_rows)} 筆 ──")
        for r in sorted(keep_rows, key=_ev_of, reverse=True):
            print(f"  #{r.id} {r.name}（{r.strategy_key}）EV={_ev_of(r)}")
        if skipped:
            print(f"\n── 跳過（無 walk_forward，不動）：{len(skipped)} 筆 ──")
            for r in skipped:
                print(f"  #{r.id} {r.name}（{r.strategy_key}）")

        if not noop_rows:
            print("\n沒有 no-op 需要退回，結束。")
            return 0

        if not apply:
            print(f"\n[dry-run] 會把上列 {len(noop_rows)} 筆 no-op 退成 rejected（加 --apply 才真的動手）。")
            return 0

        for r in noop_rows:
            _mark_noop(r)
        db.commit()
        print(f"\n✅ 已把 {len(noop_rows)} 筆 no-op 退成 rejected。")
        print(f"→ 現在 validated 剩 {len(keep_rows)} 筆，去 LibraryPage 逐筆人工晉升 curated。")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
