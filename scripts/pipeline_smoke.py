"""
探勘管線端到端 smoke（Phase 12）
=================================
既有 scripts/smoke_test.sh 只打 HTTP 端點（看服務活著），**不碰探勘管線**。
這支補上：在一個**臨時 SQLite**（不碰 Neon、不污染雲端資料）上，把一筆合成素材
餵完整條水管，逐段印 verdict，確認：

  1) 本機 Ollama 連得上（探勘橋真的會呼叫 LLM）。
  2) LLM 提案的**參數名合法**（修品質漏洞後，不再出現 short_ma 這種假名 → 靜默吃預設）。
  3) 自動驗證（OOS 閘）接得上、會跑出 verdict（或在抓不到行情時優雅記失敗）。

用途：開排程常駐前一鍵體檢。**唯讀雲端**——只寫臨時檔，跑完即刪。

執行（專案根目錄）：
    venv\\Scripts\\python.exe scripts\\pipeline_smoke.py

退出碼：0 = 管線接通；1 = 有環節斷掉（印出哪一段、為什麼）。
"""

import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 讓 backend.* 匯入解析到本 repo（scripts/ 的上一層）
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import settings
from backend.database import Base
from backend.models import RawStrategyFind
from backend.models.strategy_knowledge import StrategyKnowledge
from backend.services import auto_validate, discovery, evolution, llm
from backend.strategies import param_spec


def _line(msg):
    print(msg, flush=True)


def main() -> int:
    _line("=" * 56)
    _line("探勘管線 smoke（臨時 SQLite，唯讀雲端）")
    _line("=" * 56)

    # ── 0) 臨時 SQLite session（與 Neon 完全隔離）────────────────
    tmp_db = Path(tempfile.gettempdir()) / "albee_pipeline_smoke.db"
    if tmp_db.exists():
        tmp_db.unlink()
    engine = create_engine(f"sqlite:///{tmp_db}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    # 強制開閘（不管 .env 怎麼設，smoke 本來就是要實跑一遍水管）
    settings.DISCOVERY_ENABLED = True
    settings.AUTO_VALIDATE_ENABLED = True
    settings.DISCOVERY_BATCH_SIZE = 1
    settings.AUTO_VALIDATE_BATCH_SIZE = 1

    ok = True

    # ── 1) Ollama 連線體檢 ──────────────────────────────────────
    _line("\n[1/4] 檢查本機 LLM（Ollama）")
    if llm.cloud_blocked():
        _line("  ❌ LLM 指向雲端且未開外送閘（LLM_ALLOW_CLOUD）。探勘橋會整批跳過。")
        _line("     → 本機跑請把 LLM_BASE_URL 設回 http://localhost:11434/v1")
        return 1
    client = llm.get_client()
    if client is None:
        _line("  ❌ LLM 未設定（LLM_BASE_URL / LLM_MODEL）。")
        return 1
    _line(f"  ✅ LLM 就緒：model={settings.LLM_MODEL} base={settings.LLM_BASE_URL}")

    # ── 2) 塞一筆合成素材（明確在講 RSI 超賣反彈）──────────────────
    _line("\n[2/4] 塞 1 筆合成素材（status=new）")
    db.add(RawStrategyFind(
        source="smoke", source_url="https://smoke.example.com/rsi",
        title="RSI oversold bounce strategy",
        summary="Buy when RSI(14) falls below 30 (oversold), sell above 70 (overbought).",
        status="new",
    ))
    db.commit()
    _line("  ✅ 已塞入")

    # ── 3) 跑探勘橋 → 驗候選參數名合法 ──────────────────────────
    _line("\n[3/4] 跑探勘橋 run_discovery_batch（真的呼叫 Ollama）")
    stats = discovery.run_discovery_batch(db)
    _line(f"  stats={stats}")
    if stats["skipped"]:
        _line("  ❌ LLM 呼叫失敗（連不上 / 逾時），整批跳過。確認 `ollama serve` 有開。")
        return 1
    if stats["built"]:
        cand = db.query(StrategyKnowledge).filter_by(status="candidate").first()
        spec = param_spec(cand.strategy_key)
        bad = [k for k in (cand.params or {}) if k not in spec]
        _line(f"  ✅ 生出候選：{cand.strategy_key} params={cand.params}")
        if bad:
            ok = False
            _line(f"  ❌ 參數名漏洞未修：{bad} 不在 {cand.strategy_key} 合法參數內")
        else:
            _line(f"  ✅ 參數名全部合法（∈ {list(spec.keys())}）")
    else:
        # discard 不算錯（LLM 判定不相關是合法結果）；但 smoke 素材很明確，提醒一下
        _line("  ⚠️  LLM 把這筆判為 discarded（與既有策略無關 / 回覆無法解析）。")
        _line("     管線有通，但這顆模型對明確的 RSI 素材都認不出——品質偏弱，可換模型。")

    # ── 4) 跑自動驗證（OOS 閘）──────────────────────────────────
    _line("\n[4/4] 跑自動驗證 run_auto_validate（含成本回測 + walk-forward OOS）")
    cand = db.query(StrategyKnowledge).filter_by(status="candidate").first()
    if cand is None:
        _line("  ⏭️  沒有 candidate 可驗（上一步未產出），跳過。")
    else:
        vstats = auto_validate.run_auto_validate(db)
        _line(f"  stats={vstats}")
        row = db.get(StrategyKnowledge, cand.id)
        verdict = (row.oos_metrics or {}).get("verdict")
        if verdict is not None:
            _line(f"  ✅ OOS 閘跑完：status={row.status} "
                  f"candidate_mean={verdict.get('candidate_mean')} worth={verdict.get('worth')}")
        elif vstats["failed"]:
            _line(f"  ⚠️  驗證抓不到行情而記失敗（status 維持 {row.status}）。")
            _line("     管線接線 OK，但需要 Alpaca/yfinance 行情才能跑完 OOS。")
        else:
            _line(f"  ℹ️  status={row.status}")

    # ── 收尾：刪臨時檔 ──────────────────────────────────────────
    db.close()
    engine.dispose()
    if tmp_db.exists():
        tmp_db.unlink()

    _line("\n" + "=" * 56)
    if ok:
        _line("🎉 管線接通：素材 → 探勘橋 → 候選 → OOS 閘 全程走通")
        return 0
    _line("🔥 管線有環節異常（見上方 ❌）")
    return 1


if __name__ == "__main__":
    sys.exit(main())
