"""
探討檔案記憶服務測試 ── Phase 5
================================================
純檔案 IO，完全不需 LLM/連線。用 pytest 的 tmp_path 把探討資料夾指到暫存區，
驗證：寫檔 + 路標、同 run_id 不重覆、防路徑穿越、路標解析、回退挑檔。

執行（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_explorations.py -q
"""

import sys
from pathlib import Path
from types import SimpleNamespace

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from backend.config import settings
from backend.services import explorations


def _make_run(rid, strategy="williams_r", symbol="AAPL", ev=-3.2):
    """造一個假的回測紀錄物件（只要有這些屬性即可）。"""
    return SimpleNamespace(
        id=rid,
        strategy_key=strategy,
        symbol=symbol,
        params={"period": 14},
        metrics={"expected_value": ev, "profit_factor": 0.7, "win_rate_pct": 80.0},
    )


@pytest.fixture
def expdir(tmp_path, monkeypatch):
    """把探討資料夾指到暫存目錄，測試彼此隔離、不污染真資料。"""
    monkeypatch.setattr(settings, "EXPLORATIONS_DIR", str(tmp_path))
    return tmp_path


def test_write_and_read_roundtrip(expdir):
    """寫一筆檢討 → 檔案出現、路標多一行、能讀回內容。"""
    run = _make_run(12)
    fname = explorations.write_exploration(run, "EV 為負，疑似過擬合。建議放寬參數。")
    assert fname == "run-0012-williams_r-aapl.md"

    # 檔案存在且含 frontmatter
    content = explorations.read_exploration(fname)
    assert content is not None
    assert "run_id: 12" in content
    assert "strategy: williams_r" in content

    # 路標索引含這一行
    idx = explorations.read_index()
    assert "run#12" in idx
    assert fname in idx
    print("✅ 寫檔 + 路標 + 讀回 往返測試通過")


def test_upsert_no_duplicate(expdir):
    """同一個 run_id 檢討兩次 → 路標只有一行（取代，不重覆）、內容被覆寫。"""
    run = _make_run(7, strategy="rsi", symbol="AAPL")
    explorations.write_exploration(run, "第一版檢討。")
    explorations.write_exploration(run, "第二版檢討（修正）。")

    idx = explorations.read_index()
    fname = explorations.filename_for_run(run)
    assert idx.count(fname) == 1, f"路標應只有一行，實際：\n{idx}"

    content = explorations.read_exploration(fname)
    assert "第二版檢討" in content
    assert "第一版檢討" not in content
    print("✅ 同 run_id 不重覆（取代）測試通過")


def test_read_exploration_path_traversal_guard(expdir):
    """防路徑穿越：任何想跳出資料夾或非 .md 的名稱都回 None。"""
    # 先寫一個合法檔，確認正常讀得到
    run = _make_run(1)
    fname = explorations.write_exploration(run, "正常內容。")
    assert explorations.read_exploration(fname) is not None

    # 各種惡意/無效輸入都應回 None
    assert explorations.read_exploration("../secret.md") is None
    assert explorations.read_exploration("..\\secret.md") is None
    assert explorations.read_exploration("/etc/passwd") is None
    assert explorations.read_exploration("sub/dir/x.md") is None
    assert explorations.read_exploration("notes.txt") is None   # 非 .md
    assert explorations.read_exploration("nonexistent.md") is None
    assert explorations.read_exploration("") is None
    print("✅ 防路徑穿越測試通過")


def test_list_index_entries_parse(expdir):
    """路標能被解析成結構化清單，strategy/symbol 從檔名正確還原。"""
    explorations.write_exploration(_make_run(3, strategy="rsi", symbol="TSLA"), "甲")
    explorations.write_exploration(_make_run(4, strategy="williams_r", symbol="NVDA"), "乙")

    entries = explorations.list_index_entries()
    by_id = {e["run_id"]: e for e in entries}
    assert set(by_id) == {3, 4}
    assert by_id[3]["strategy"] == "rsi"
    assert by_id[3]["symbol"] == "tsla"
    assert by_id[4]["file"] == "run-0004-williams_r-nvda.md"
    print("✅ 路標解析測試通過")


def test_select_candidates_by_meta(expdir):
    """回退挑檔：同策略優先、排除自己、最多 limit 個。"""
    explorations.write_exploration(_make_run(10, strategy="rsi", symbol="AAPL"), "a")
    explorations.write_exploration(_make_run(11, strategy="rsi", symbol="TSLA"), "b")
    explorations.write_exploration(_make_run(12, strategy="macd", symbol="NVDA"), "c")

    target = _make_run(99, strategy="rsi", symbol="AAPL")
    entries = explorations.list_index_entries()
    picked = explorations.select_candidates_by_meta(target, entries, limit=3)

    # 同策略（rsi）的兩筆要排在前面，macd 那筆排後面
    assert picked[0].startswith("run-00")
    assert "rsi" in picked[0] and "rsi" in picked[1]
    assert picked[-1] == "run-0012-macd-nvda.md"
    # 不含自己（run 99 根本沒寫檔，本來就不會在）
    assert all("0099" not in f for f in picked)
    print("✅ 回退挑檔（同策略優先）測試通過")


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        settings.EXPLORATIONS_DIR = d
        run = _make_run(12)
        f = explorations.write_exploration(run, "手動測試內容。")
        assert explorations.read_exploration(f) is not None
        assert explorations.read_exploration("../x.md") is None
        print("✅ 手動驗證通過")
    print("\n🎉 explorations 測試通過！")
