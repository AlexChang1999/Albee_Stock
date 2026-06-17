"""
收件匣重排 + 探勘橋抽乾（Phase 12 一次性維運）
================================================
情境：修掉「參數名漏洞」後，要讓修好的探勘橋重跑收件匣。兩件事：
  1) 把 51 筆人工擱置的 status=triaged 改回 new（讓探勘橋碰得到——它只吃 status=new）。
  2) 連續跑 run_discovery_batch 把所有 new 抽乾，看候選參數名是否合法、OOS 通過率。

★ 這支會**寫共用 Neon DB**（另一台機器也讀同一份）。預設 **dry-run 只印不改**；
  真要動手加 `--apply`。抽乾加 `--drain`（會真的呼叫本機 Ollama，每筆數秒～數十秒）。

執行（專案根目錄，需有 .env 指向 Neon + 本機 Ollama 開著）：
    venv\\Scripts\\python.exe scripts\\requeue_and_drain.py            # 只看現況（dry-run）
    venv\\Scripts\\python.exe scripts\\requeue_and_drain.py --apply    # 真的把 triaged 改回 new
    venv\\Scripts\\python.exe scripts\\requeue_and_drain.py --apply --drain  # 改完順手抽乾
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func

from backend.config import settings
from backend.database import SessionLocal
from backend.models import RawStrategyFind
from backend.models.strategy_knowledge import StrategyKnowledge
from backend.services import discovery


def _counts(db):
    rows = (
        db.query(RawStrategyFind.status, func.count())
        .group_by(RawStrategyFind.status)
        .all()
    )
    return dict(rows)


def main() -> int:
    apply = "--apply" in sys.argv
    drain = "--drain" in sys.argv

    db = SessionLocal()
    try:
        before = _counts(db)
        print("收件匣現況 raw_strategy_finds：", before)
        n_triaged = before.get("triaged", 0)

        # ── 1) triaged → new ────────────────────────────────────
        if n_triaged == 0:
            print("沒有 triaged 可重排，跳過。")
        elif not apply:
            print(f"[dry-run] 會把 {n_triaged} 筆 triaged 改回 new（加 --apply 才真的動手）。")
        else:
            updated = (
                db.query(RawStrategyFind)
                .filter(RawStrategyFind.status == "triaged")
                .update({RawStrategyFind.status: "new"}, synchronize_session=False)
            )
            db.commit()
            print(f"✅ 已把 {updated} 筆 triaged 改回 new。新現況：", _counts(db))

        # ── 2) 抽乾 new（連續跑探勘橋直到清空）──────────────────
        if not drain:
            n_new = _counts(db).get("new", 0)
            print(f"未加 --drain：保留 {n_new} 筆 new 給排程慢慢跑（或之後加 --drain 手動抽乾）。")
            return 0
        if not settings.DISCOVERY_ENABLED:
            print("⚠️  DISCOVERY_ENABLED=false：探勘橋會 no-op。臨時開啟本程序內的旗標來抽乾。")
            settings.DISCOVERY_ENABLED = True

        total = {"processed": 0, "built": 0, "discarded": 0, "skipped": 0}
        round_no = 0
        while True:
            round_no += 1
            stats = discovery.run_discovery_batch(db)
            for k in total:
                total[k] += stats[k]
            print(f"  第 {round_no} 輪：{stats}")
            if stats["skipped"]:
                print("  ❌ LLM 連不上，停止抽乾（確認 `ollama serve`）。已處理的不受影響。")
                break
            if stats["processed"] == 0:
                print("  ✅ new 已清空。")
                break

        print("抽乾總計：", total)
        n_cand = db.query(StrategyKnowledge).filter_by(status="candidate").count()
        print(f"知識庫目前 candidate（待自動驗證）：{n_cand} 筆")
        print("→ 接著由 run_auto_validate（排程 / 手動）跑 OOS 閘，validated 再由人晉升 curated。")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
