# -*- coding: utf-8 -*-
"""
相對強度 RS + 產業對照 + 週報排程（Phase 16 M7/M9）測試
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.relative_strength import rs_score, rs_scores
from backend.services.sectors import SECTOR_BY_SYMBOL, sector_label, sector_of


def _df(closes):
    return pd.DataFrame({"close": closes})


# ---------- RS 數學 ----------
def test_rs_score_math():
    # 標的 5 根漲 10%（100→110）、基準漲 2%（100→102）→ RS ≈ +8
    sym = _df([100, 102, 104, 106, 108, 110])
    bench = _df([100, 100.4, 100.8, 101.2, 101.6, 102])
    assert rs_score(sym, bench, 5) == pytest.approx(8.0, abs=0.01)
    # 跑輸基準 → 負 RS
    assert rs_score(bench, sym, 5) == pytest.approx(-8.0, abs=0.01)


def test_rs_score_insufficient_data_returns_none():
    assert rs_score(_df([100, 101]), _df([100, 101]), 5) is None
    assert rs_score(_df([100] * 10), _df([100, 101]), 5) is None  # 基準不足也 None


def test_rs_scores_multi_window_and_composite():
    sym = _df(list(range(100, 130)))    # 一路漲
    bench = _df([100.0] * 30)           # 基準不動
    out = rs_scores(sym, bench)
    assert set(out) == {"rs_1", "rs_5", "rs_20", "rs_composite"}
    assert out["rs_1"] > 0 and out["rs_5"] > 0 and out["rs_20"] > 0
    assert out["rs_composite"] == pytest.approx(
        (out["rs_1"] + out["rs_5"] + out["rs_20"]) / 3, abs=0.01)


def test_rs_scores_partial_windows():
    # 只夠 1/5 日窗口（不足 20 根）→ rs_20 None、composite 只平均可用窗口
    sym = _df(list(range(100, 110)))
    bench = _df([100.0] * 10)
    out = rs_scores(sym, bench)
    assert out["rs_20"] is None
    assert out["rs_composite"] is not None


# ---------- 產業對照 ----------
def test_sector_of_manual_dict_no_network():
    assert sector_of("NVDA") == "XLK"
    assert sector_of("nvda") == "XLK"   # 大小寫容錯
    assert sector_of("SPY") == "index"
    assert sector_of("JPM") == "XLF"


def test_sector_labels_cover_all_used_keys():
    from backend.services.sectors import SECTOR_LABELS
    assert set(SECTOR_BY_SYMBOL.values()) <= set(SECTOR_LABELS)
    assert sector_label("XLK") == "科技"
    assert sector_label("不存在") == "不存在"  # 找不到回原 key，不壞報表


# ---------- M9 週報排程 ----------
def test_schedule_weekly_reports_registers_cron_job():
    from backend.bots.bot_manager import BotManager
    mgr = BotManager()
    mgr.schedule_weekly_reports()
    job = mgr.scheduler.get_job("weekly_reports")
    assert job is not None
    trig = str(job.trigger)
    assert "day_of_week='mon'" in trig and "hour='8'" in trig


def test_run_weekly_reports_isolates_failures(monkeypatch):
    """單支報告炸掉不擋後面的，且失敗也推播。"""
    import backend.bots.bot_manager as bm
    from scripts import (
        full_backtest_report, fund_flow_report, scan_frequency_study, stock_pool_report,
    )

    calls, notes = [], []
    monkeypatch.setattr(full_backtest_report, "run",
                        lambda **k: calls.append("full") or "# 全池報告\nok")
    monkeypatch.setattr(fund_flow_report, "run",
                        lambda **k: (_ for _ in ()).throw(RuntimeError("SPY 掛了")))
    monkeypatch.setattr(stock_pool_report, "run",
                        lambda **k: calls.append("pool") or "# 池報告\nok")
    monkeypatch.setattr(scan_frequency_study, "run",
                        lambda **k: calls.append("scan") or "# 掃頻\nok")
    monkeypatch.setattr(bm, "notify", lambda msg: notes.append(msg))

    bm.run_weekly_reports()

    assert calls == ["full", "pool", "scan"]      # 資金流失敗，其餘照跑
    assert len(notes) == 4                        # 三成功 + 一失敗都推播
    assert any("失敗" in n and "SPY 掛了" in n for n in notes)
    assert any("全池回測" in n and "完成" in n for n in notes)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
