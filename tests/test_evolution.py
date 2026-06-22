"""
自動驗證管線測試（Phase 8 step-04）
=====================================
驗證最關鍵的守門邏輯：判定鍵讀的是**樣本外（walk-forward）**，不是 in-sample。
- monkeypatch 一個「OOS 加分」的候選 → validated。
- monkeypatch 一個「OOS 不加分」的候選 → rejected。

不連網：monkeypatch market_data.get_bars 給合成 K 線、validation.walk_forward 給可控 fold。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_evolution.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import math

import pandas as pd

from backend.services import market_data, validation, evolution
from backend.services.evolution import validate_candidate


class _FakeKnowledge:
    """模擬 StrategyKnowledge ORM 物件（只用到的屬性）。"""
    def __init__(self, strategy_key="rsi", params=None):
        self.id = 1
        self.strategy_key = strategy_key
        self.params = params or {}
        self.status = "candidate"
        self.oos_metrics = None


def _osc_df(n=160):
    closes = [100 + 10 * math.sin(i / 5) + i * 0.1 for i in range(n)]
    return pd.DataFrame({
        "open": closes,
        "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes],
        "close": closes,
        "volume": [1000 + (i % 10) * 50 for i in range(n)],
        "timestamp": pd.date_range("2023-01-01", periods=n, freq="D"),
    })


def _folds(ev_each):
    """造 walk_forward 回傳格式的 fold 清單（只填判定會讀的鍵）。"""
    return [
        {"fold": i, "test_start": 0, "test_end": 1, "expected_value": ev,
         "win_rate_pct": 0.0, "total_return_pct": 0.0, "num_round_trips": 1}
        for i, ev in enumerate(ev_each)
    ]


def test_validate_oos_positive_validated(monkeypatch):
    """OOS（walk-forward）每 fold 都正 EV → validated。"""
    monkeypatch.setattr(market_data, "get_bars", lambda symbol, days, source: _osc_df())
    monkeypatch.setattr(validation, "walk_forward",
                        lambda *a, **k: _folds([10.0, 12.0, 8.0]))
    row = _FakeKnowledge()
    out = validate_candidate(row, "FAKE", days=160)
    assert out["status"] == "validated"
    assert row.status == "validated"
    assert row.oos_metrics["verdict"]["worth"] is True
    assert row.oos_metrics["expected_value"] == 10.0  # (10+12+8)/3


def test_validate_oos_negative_rejected(monkeypatch):
    """OOS 平均為負（輸給不交易）→ rejected。"""
    monkeypatch.setattr(market_data, "get_bars", lambda symbol, days, source: _osc_df())
    monkeypatch.setattr(validation, "walk_forward",
                        lambda *a, **k: _folds([-5.0, -3.0, -8.0]))
    row = _FakeKnowledge()
    out = validate_candidate(row, "FAKE", days=160)
    assert out["status"] == "rejected"
    assert row.status == "rejected"
    assert row.oos_metrics["verdict"]["worth"] is False


def test_validate_too_few_folds_rejected(monkeypatch):
    """fold 數不足（< VALIDATION_MIN_FOLDS）→ 不採信 → rejected（即使 EV 為正）。"""
    monkeypatch.setattr(market_data, "get_bars", lambda symbol, days, source: _osc_df())
    monkeypatch.setattr(validation, "walk_forward", lambda *a, **k: _folds([99.0]))
    row = _FakeKnowledge()
    out = validate_candidate(row, "FAKE", days=160)
    assert out["status"] == "rejected"


def test_validate_empty_data_raises(monkeypatch):
    """抓不到資料 → 明確報錯，不默默通過。"""
    monkeypatch.setattr(market_data, "get_bars", lambda symbol, days, source: pd.DataFrame())
    try:
        validate_candidate(_FakeKnowledge(), "FAKE", days=160)
        assert False, "空資料應 raise ValueError"
    except ValueError:
        pass


# ---------- no-op 守門（Phase 12：零交易排除）----------
def test_is_noop_all_zero_true():
    folds = [{"num_round_trips": 0}, {"num_round_trips": 0}, {"num_round_trips": 0}]
    assert evolution.is_noop(folds) is True


def test_is_noop_any_trade_false():
    folds = [{"num_round_trips": 0}, {"num_round_trips": 2}, {"num_round_trips": 0}]
    assert evolution.is_noop(folds) is False


def test_is_noop_empty_true():
    # 空 folds = 沒有任何交易證據 → 視為 no-op
    assert evolution.is_noop([]) is True


def test_is_noop_missing_key_treated_zero():
    # fold 沒帶 num_round_trips 鍵 → 當 0（防 KeyError）
    assert evolution.is_noop([{}, {}]) is True


def _noop_folds(n=9):
    """所有 fold 零交易（EV 也是 0）── no-op 樣本。"""
    return [
        {"fold": i, "test_start": 0, "test_end": 1, "expected_value": 0.0,
         "win_rate_pct": 0.0, "total_return_pct": 0.0, "num_round_trips": 0}
        for i in range(n)
    ]


def test_validate_noop_rejected(monkeypatch):
    """所有 fold 零交易 → rejected，oos_metrics 含 noop 鍵、無 verdict 鍵（不進判子）。"""
    monkeypatch.setattr(market_data, "get_bars", lambda symbol, days, source: _osc_df())
    monkeypatch.setattr(validation, "walk_forward", lambda *a, **k: _noop_folds(9))
    row = _FakeKnowledge()
    out = validate_candidate(row, "FAKE", days=1100)
    assert out["status"] == "rejected"
    assert row.status == "rejected"
    assert "noop" in row.oos_metrics
    assert "verdict" not in row.oos_metrics
    assert row.oos_metrics["noop"]["total_round_trips"] == 0
    assert len(row.oos_metrics["walk_forward"]) == 9  # 仍保留供稽核


def test_validate_positive_with_trades_unaffected(monkeypatch):
    """有交易（_folds 預設 num_round_trips=1）且 OOS 正 → 守門不誤殺，仍 validated。"""
    monkeypatch.setattr(market_data, "get_bars", lambda symbol, days, source: _osc_df())
    monkeypatch.setattr(validation, "walk_forward",
                        lambda *a, **k: _folds([10.0, 12.0, 8.0]))
    row = _FakeKnowledge()
    out = validate_candidate(row, "FAKE", days=160)
    assert out["status"] == "validated"
    assert "noop" not in row.oos_metrics


# ---------- 多標的籃子驗證（Phase 12：跨產業 OOS 池化）----------
def _folds_rt(ev_each, rt=3):
    """造 walk_forward fold 清單，可指定每 fold 的交易次數（測門檻用）。"""
    return [
        {"fold": i, "test_start": 0, "test_end": 1, "expected_value": ev,
         "win_rate_pct": 0.0, "total_return_pct": 0.0, "num_round_trips": rt}
        for i, ev in enumerate(ev_each)
    ]


def _basket_setup(monkeypatch, folds_by_sym, empty_syms=(), raise_syms=()):
    """
    籃子測試共用 monkeypatch：每檔回不同 fold。
    用 df.attrs 把 symbol 帶給 walk_forward（它本身不收 symbol），以區分每檔結果。
    empty_syms：該檔 get_bars 回空 df；raise_syms：該檔 get_bars 拋例外。
    """
    def fake_get_bars(symbol, days, source):
        if symbol in raise_syms:
            raise RuntimeError(f"離線：{symbol}")
        if symbol in empty_syms:
            return pd.DataFrame()
        df = _osc_df().copy()
        df.attrs["sym"] = symbol
        return df

    def fake_wf(df, *a, **k):
        return folds_by_sym[df.attrs["sym"]]

    monkeypatch.setattr(market_data, "get_bars", fake_get_bars)
    monkeypatch.setattr(validation, "walk_forward", fake_wf)


def test_validate_basket_pooled_validated(monkeypatch):
    """3 檔各正 EV、交易數達標 → 池化 validated；per_symbol 三筆、頭條為等權池化 EV。"""
    _basket_setup(monkeypatch, {
        "AAA": _folds_rt([10.0, 10.0, 10.0]),  # 平均 10，rt 3*3=9 達標
        "BBB": _folds_rt([20.0, 20.0, 20.0]),  # 平均 20
        "CCC": _folds_rt([30.0, 30.0, 30.0]),  # 平均 30
    })
    row = _FakeKnowledge()
    out = validate_candidate(row, ["AAA", "BBB", "CCC"], days=1100)
    assert out["status"] == "validated"
    assert row.oos_metrics["verdict"]["worth"] is True
    assert row.oos_metrics["expected_value"] == 20.0  # (10+20+30)/3 等權
    assert len(row.oos_metrics["per_symbol"]) == 3
    assert row.oos_metrics["symbols"] == ["AAA", "BBB", "CCC"]
    assert all(s["qualified"] for s in row.oos_metrics["per_symbol"])


def test_validate_basket_all_noop_rejected(monkeypatch):
    """整籃無達標檔（全零交易）→ rejected，含 noop 鍵、無 verdict。"""
    _basket_setup(monkeypatch, {
        "AAA": _folds_rt([0.0, 0.0, 0.0], rt=0),
        "BBB": _folds_rt([0.0, 0.0, 0.0], rt=0),
        "CCC": _folds_rt([0.0, 0.0, 0.0], rt=0),
    })
    row = _FakeKnowledge()
    out = validate_candidate(row, ["AAA", "BBB", "CCC"], days=1100)
    assert out["status"] == "rejected"
    assert "noop" in row.oos_metrics
    assert "verdict" not in row.oos_metrics
    assert row.oos_metrics["noop"]["qualified_symbols"] == 0


def test_validate_basket_threshold_excludes_symbol(monkeypatch):
    """一檔交易數低於門檻被排除，剩 3 檔達標 → 仍 validated；被排除檔記 excluded。"""
    _basket_setup(monkeypatch, {
        "AAA": _folds_rt([10.0, 10.0, 10.0]),       # 達標
        "BBB": _folds_rt([10.0, 10.0, 10.0]),       # 達標
        "CCC": _folds_rt([10.0, 10.0, 10.0]),       # 達標
        "LOW": _folds_rt([99.0], rt=1),             # 只 1 fold、rt 1 < 門檻 5 → 排除
    })
    row = _FakeKnowledge()
    out = validate_candidate(row, ["AAA", "BBB", "CCC", "LOW"], days=1100)
    assert out["status"] == "validated"
    low = next(s for s in row.oos_metrics["per_symbol"] if s["symbol"] == "LOW")
    assert low["qualified"] is False
    assert low["excluded"] is not None
    # 池化只看達標 3 檔（不含 LOW 的 99）
    assert row.oos_metrics["expected_value"] == 10.0


def test_validate_basket_too_few_qualified_rejected(monkeypatch):
    """達標檔數 < VALIDATION_MIN_FOLDS(3) → rejected（fold 數語意＝達標標的數）。"""
    _basket_setup(monkeypatch, {
        "AAA": _folds_rt([10.0, 10.0, 10.0]),
        "BBB": _folds_rt([10.0, 10.0, 10.0]),
    })
    row = _FakeKnowledge()
    out = validate_candidate(row, ["AAA", "BBB"], days=1100)
    assert out["status"] == "rejected"
    assert row.oos_metrics["verdict"]["worth"] is False


def test_validate_basket_skips_no_data_symbol(monkeypatch):
    """某檔抓不到資料 → 跳過該檔、用剩餘達標檔判（不 raise）。"""
    _basket_setup(monkeypatch, {
        "AAA": _folds_rt([10.0, 10.0, 10.0]),
        "BBB": _folds_rt([10.0, 10.0, 10.0]),
        "CCC": _folds_rt([10.0, 10.0, 10.0]),
    }, empty_syms=("DEAD",))
    row = _FakeKnowledge()
    out = validate_candidate(row, ["AAA", "BBB", "CCC", "DEAD"], days=1100)
    assert out["status"] == "validated"
    dead = next(s for s in row.oos_metrics["per_symbol"] if s["symbol"] == "DEAD")
    assert dead["folds"] == 0 and dead["excluded"] is not None


def test_validate_basket_all_fail_raises(monkeypatch):
    """全部標的都抓不到資料 → raise（沒有任何證據可判）。"""
    _basket_setup(monkeypatch, {}, empty_syms=("X", "Y", "Z"))
    try:
        validate_candidate(_FakeKnowledge(), ["X", "Y", "Z"], days=1100)
        assert False, "全失敗應 raise ValueError"
    except ValueError:
        pass


def test_validate_single_str_keeps_old_shape(monkeypatch):
    """傳單一 str → 走原路徑：oos_metrics 保留 walk_forward/symbol，無 per_symbol（向後相容）。"""
    monkeypatch.setattr(market_data, "get_bars", lambda symbol, days, source: _osc_df())
    monkeypatch.setattr(validation, "walk_forward",
                        lambda *a, **k: _folds([10.0, 12.0, 8.0]))
    row = _FakeKnowledge()
    out = validate_candidate(row, "FAKE", days=160)
    assert out["status"] == "validated"
    assert "walk_forward" in row.oos_metrics
    assert row.oos_metrics["symbol"] == "FAKE"
    assert "per_symbol" not in row.oos_metrics


if __name__ == "__main__":
    print("（evolution 測試需 pytest 的 monkeypatch，請用 pytest 執行）")
