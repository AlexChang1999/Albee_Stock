"""
探討（檢討）檔案記憶服務 ── Phase 5
================================================
把思考助手的每次「事後檢討」存成 markdown 檔，並用一個 INDEX.md 當「路標索引」。
寫新檢討前，助手會先讀路標、挑相關的過去探討來參考——讓記憶看得見、可版本控管、
可隨專案搬遷（就是「索引檔 + 內容檔」記憶模式）。

設計重點：
- 真實來源是「檔案」。DB 的 BacktestRun.claude_postmortem 只留一份摘要供前端顯示。
- 檔名用 run_id 連結回 DB（run-0012-williams_r-aapl.md），不需改資料庫 schema。
- read_exploration 嚴格防「路徑穿越」：助手會自己給檔名，必須擋住它讀到資料夾外的檔。

這個模組刻意只做純檔案 IO（不碰 LLM），方便單元測試。
"""

import json
import re
from datetime import datetime
from pathlib import Path

from backend.config import settings

# INDEX.md 的標題（首次建立時寫入）
_INDEX_HEADER = (
    "# 探討主檔案（路標索引）\n\n"
    "> 思考助手的長期記憶路標。每次事後檢討會在這裡新增一行，"
    "並把完整內容寫成同名 md 檔。\n"
    "> 寫新檢討前，助手會先讀這份清單、挑相關的過去探討來參考。\n\n"
)

# 路標每一行的樣子：- [run#12 · 2026-06-02 · williams_r/AAPL · EV -3.2](檔名.md) — 摘要
_INDEX_LINE_RE = re.compile(
    r"^- \[run#(?P<run_id>\d+).*?\]\((?P<file>[^)]+)\)(?: — (?P<summary>.*))?$"
)


def _dir() -> Path:
    """目前的探討資料夾（每次從 settings 讀，方便測試 monkeypatch）。"""
    return Path(settings.EXPLORATIONS_DIR)


def _index_path() -> Path:
    return _dir() / "INDEX.md"


def _safe(text: str) -> str:
    """把字串清成可放進檔名的安全字元（英數、底線、減號）。"""
    return re.sub(r"[^0-9A-Za-z_-]", "", text or "")


def filename_for_run(run) -> str:
    """依回測紀錄產生檔名：run-{id:04d}-{strategy}-{symbol_lower}.md。"""
    strat = _safe(run.strategy_key)
    sym = _safe((run.symbol or "").lower())
    return f"run-{int(run.id):04d}-{strat}-{sym}.md"


def ensure_dir() -> None:
    """確保資料夾與 INDEX.md 存在（首次自動建立 + 寫標題）。"""
    d = _dir()
    d.mkdir(parents=True, exist_ok=True)
    idx = _index_path()
    if not idx.exists():
        idx.write_text(_INDEX_HEADER, encoding="utf-8")


def read_index() -> str:
    """讀整份路標索引文字（不存在回空字串）。"""
    idx = _index_path()
    return idx.read_text(encoding="utf-8") if idx.exists() else ""


def list_index_entries() -> list[dict]:
    """
    解析路標每一行，回成結構化清單（給回退挑檔用）。
    每筆：{run_id, file, strategy, symbol, summary}
    strategy/symbol 從檔名解析（run-0012-williams_r-aapl → williams_r / aapl）。
    """
    entries = []
    for line in read_index().splitlines():
        m = _INDEX_LINE_RE.match(line.strip())
        if not m:
            continue
        fname = m.group("file")
        strategy, symbol = _parse_strategy_symbol(fname)
        entries.append({
            "run_id": int(m.group("run_id")),
            "file": fname,
            "strategy": strategy,
            "symbol": symbol,
            "summary": m.group("summary") or "",
        })
    return entries


def _parse_strategy_symbol(filename: str) -> tuple[str, str]:
    """從 run-0012-williams_r-aapl.md 解析出 (strategy, symbol)。"""
    stem = Path(filename).stem  # run-0012-williams_r-aapl
    m = re.match(r"^run-\d+-(?P<rest>.+)$", stem)
    if not m:
        return ("", "")
    rest = m.group("rest")  # williams_r-aapl
    # 策略代號是 snake_case（含底線、無減號），標的只有字母 → 用最後一個減號切開
    if "-" in rest:
        strategy, symbol = rest.rsplit("-", 1)
    else:
        strategy, symbol = rest, ""
    return (strategy, symbol)


def read_exploration(name: str) -> str | None:
    """
    安全讀取某個探討檔內容。**防路徑穿越**：
    - 只取 basename（去掉任何目錄成分），且必須是 .md
    - 解析後的父目錄必須就是探討資料夾本身，否則拒絕
    助手會自己給檔名，這層 guard 確保它不可能讀到資料夾外的任何檔。
    """
    if not name:
        return None
    safe_name = Path(name).name  # 去掉 ../、絕對路徑等目錄成分
    if not safe_name.endswith(".md"):
        return None
    target = _dir() / safe_name
    try:
        resolved = target.resolve()
    except Exception:
        return None
    if resolved.parent != _dir().resolve():
        return None
    if not resolved.is_file():
        return None
    return resolved.read_text(encoding="utf-8")


def _summary_from(analysis: str, limit: int = 60) -> str:
    """取分析文字的第一句非空行當路標摘要（去掉 markdown 記號、截斷）。"""
    for raw in (analysis or "").splitlines():
        line = raw.strip().lstrip("#").strip()
        if line:
            return (line[:limit] + "…") if len(line) > limit else line
    return "（無摘要）"


def write_exploration(run, analysis: str, references: list[str] | None = None) -> str:
    """
    把一次檢討寫成 md 檔（frontmatter + 內文），並更新路標索引。
    同一個 run_id 重覆檢討 → 覆寫同檔、取代同一行路標（不重覆）。
    回傳寫出的檔名。
    """
    ensure_dir()
    references = references or []
    m = run.metrics or {}
    fname = filename_for_run(run)
    date = datetime.now().strftime("%Y-%m-%d")
    summary = _summary_from(analysis)

    frontmatter = (
        "---\n"
        f"run_id: {run.id}\n"
        f"date: {date}\n"
        f"strategy: {run.strategy_key}\n"
        f"symbol: {run.symbol}\n"
        f"ev: {m.get('expected_value')}\n"
        f"profit_factor: {m.get('profit_factor')}\n"
        f"win_rate_pct: {m.get('win_rate_pct')}\n"
        f"references: {json.dumps(references, ensure_ascii=False)}\n"
        "---\n\n"
    )
    body = f"# 檢討：{run.strategy_key} / {run.symbol}（run #{run.id}）\n\n{analysis.strip()}\n"
    (_dir() / fname).write_text(frontmatter + body, encoding="utf-8")

    # 路標行：- [run#12 · 2026-06-02 · williams_r/AAPL · EV -3.2](檔名) — 摘要
    ev = m.get("expected_value")
    line = (
        f"- [run#{run.id} · {date} · {run.strategy_key}/{run.symbol} · EV {ev}]"
        f"({fname}) — {summary}"
    )
    _upsert_index_line(fname, line)
    return fname


def _upsert_index_line(filename: str, new_line: str) -> None:
    """路標索引裡，同檔名的行用 new_line 取代；沒有就附加到最後。"""
    ensure_dir()
    idx = _index_path()
    text = idx.read_text(encoding="utf-8")
    marker = f"]({filename})"
    lines = text.splitlines()
    replaced = False
    for i, line in enumerate(lines):
        if marker in line:
            lines[i] = new_line
            replaced = True
            break
    if not replaced:
        # 確保標題與內容間留空行，附加在最後
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append(new_line)
    idx.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def filename_for_knowledge(knowledge_id: int, strategy_key: str) -> str:
    """策展決定檔名：knowledge-{id:04d}-{strategy}.md（與回測檢討的 run- 前綴區隔，不撞檔）。"""
    return f"knowledge-{int(knowledge_id):04d}-{_safe(strategy_key)}.md"


def write_knowledge_note(
    knowledge_id: int, strategy_key: str, decision: str, reason: str,
    references: list[str] | None = None,
) -> str:
    """
    把一次「策展決定」（晉升 / 退回）的理由寫成 md 檔並更新路標索引 ── Phase 8 step-06。

    沿用既有檔案記憶機制（同資料夾 / 同 INDEX 路標 / 同防穿越讀取），只是檔名前綴用
    knowledge- 與回測檢討區隔。形成「採用 / 淘汰理由」的可追溯軌跡，連結 knowledge id。
    同一個 knowledge id 重覆決定 → 覆寫同檔、取代同一行路標（不重覆）。

    :param decision: 'promote'（晉升 curated）或 'reject'（退回）等決定字串
    :return: 寫出的檔名
    """
    ensure_dir()
    references = references or []
    fname = filename_for_knowledge(knowledge_id, strategy_key)
    date = datetime.now().strftime("%Y-%m-%d")
    summary = _summary_from(reason)

    frontmatter = (
        "---\n"
        f"knowledge_id: {knowledge_id}\n"
        f"date: {date}\n"
        f"strategy: {strategy_key}\n"
        f"decision: {decision}\n"
        f"references: {json.dumps(references, ensure_ascii=False)}\n"
        "---\n\n"
    )
    body = (
        f"# 策展決定：{decision}（knowledge #{knowledge_id} · {strategy_key}）\n\n"
        f"{reason.strip()}\n"
    )
    (_dir() / fname).write_text(frontmatter + body, encoding="utf-8")

    # 路標行：- [knowledge#3 · 2026-06-08 · rsi · promote](檔名) — 摘要
    line = (
        f"- [knowledge#{knowledge_id} · {date} · {strategy_key} · {decision}]"
        f"({fname}) — {summary}"
    )
    _upsert_index_line(fname, line)
    return fname


def select_candidates_by_meta(run, entries: list[dict], limit: int = 3) -> list[str]:
    """
    回退挑檔（當 LLM 挑檔失敗時用）：同策略優先，再補最近的其他探討，
    排除當前 run 自己，最多回 limit 個檔名。
    """
    current = filename_for_run(run)
    same, others = [], []
    # entries 依 INDEX 由舊到新；要「最近優先」就反轉
    for e in reversed(entries):
        if e["file"] == current:
            continue
        if e["strategy"] == run.strategy_key:
            same.append(e["file"])
        else:
            others.append(e["file"])
    picked = (same + others)[:limit]
    return picked
