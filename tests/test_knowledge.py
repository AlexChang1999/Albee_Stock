"""
策略知識庫 API 測試（Phase 8 step-01 / 05 / 06）
==================================================
1. step-01：CRUD 往返、status 流轉、404。
2. step-05：ranking 依 OOS EV 排序、篩 status；usage_note 寫入往返（monkeypatch LLM + 狀態圖）。
3. step-06：promote / reject 狀態流轉；理由寫入 explorations 往返；**無自動晉升路徑**
   （candidate 不可直接 promote → 400，斷言系統不會自動 validated→curated）。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests/test_knowledge.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

import backend.routers.knowledge as kr
from backend.config import settings
from backend.database import SessionLocal
from backend.models import StrategyKnowledge, Bot
from backend.services import explorations, llm
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def _delete(kid):
    db = SessionLocal()
    obj = db.query(StrategyKnowledge).filter(StrategyKnowledge.id == kid).first()
    if obj:
        db.delete(obj)
        db.commit()
    db.close()


# ========== step-01 ==========
def test_knowledge_crud_and_status():
    """建立 → 列出 → 編輯（改 status）→ 刪除 完整往返。"""
    payload = {
        "name": "RSI 震盪反轉",
        "strategy_key": "rsi",
        "theory": "均值回歸",
        "scenario": "盤整盤",
        "params": {"period": 14},
    }
    r = client.post("/knowledge", json=payload)
    assert r.status_code == 200, r.text
    created = r.json()
    kid = created["id"]
    assert created["status"] == "candidate"

    try:
        # 列出（含剛建的）
        r = client.get("/knowledge")
        assert any(k["id"] == kid for k in r.json())

        # 篩 status
        r = client.get("/knowledge", params={"status": "candidate"})
        assert any(k["id"] == kid for k in r.json())

        # 編輯：流轉 status 到 validated
        upd = {**payload, "status": "validated"}
        r = client.put(f"/knowledge/{kid}", json=upd)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "validated"
    finally:
        r = client.delete(f"/knowledge/{kid}")
        assert r.status_code == 200, r.text
    # 確認已刪
    r = client.get(f"/knowledge/{kid}")
    assert r.status_code == 404


def test_get_missing_404():
    r = client.get("/knowledge/999999")
    assert r.status_code == 404


def test_invalid_status_400():
    r = client.post("/knowledge", json={"name": "x", "strategy_key": "rsi", "status": "亂填"})
    assert r.status_code == 400


# ========== step-05 ==========
def test_ranking_sorted_by_oos_ev():
    """塞兩筆 validated（OOS EV 高/低）→ ranking 依 EV 由高到低；篩 status 生效。"""
    db = SessionLocal()
    low = StrategyKnowledge(name="低", strategy_key="rsi", status="validated",
                            params={}, oos_metrics={"expected_value": 5.0})
    high = StrategyKnowledge(name="高", strategy_key="rsi", status="validated",
                             params={}, oos_metrics={"expected_value": 88.0})
    cand = StrategyKnowledge(name="候選", strategy_key="rsi", status="candidate",
                             params={}, oos_metrics={"expected_value": 999.0})
    db.add_all([low, high, cand])
    db.commit()
    low_id, high_id, cand_id = low.id, high.id, cand.id
    db.close()

    try:
        r = client.get("/knowledge/ranking")  # 預設 status=validated
        assert r.status_code == 200, r.text
        ids = [k["id"] for k in r.json()]
        assert high_id in ids and low_id in ids
        assert cand_id not in ids, "candidate 不該出現在 validated 排行"
        assert ids.index(high_id) < ids.index(low_id), "高 OOS EV 應排前"
    finally:
        for kid in (low_id, high_id, cand_id):
            _delete(kid)


def test_usage_note_writeback(monkeypatch):
    """產生 usage_note：monkeypatch 狀態圖 + LLM，驗證寫回 usage_note / regime_affinity。"""
    # 建一筆 validated 知識
    r = client.post("/knowledge", json={"name": "唐奇安突破", "strategy_key": "donchian"})
    kid = r.json()["id"]

    # monkeypatch：狀態→策略對照表的 stats（含本策略在 trending 的 OOS 表現）
    fake_map = {
        "stats": {
            "trending": {"donchian": {"ev": 42.0, "win_rate_pct": 60.0, "n": 20}},
            "ranging": {"donchian": {"ev": -3.0, "win_rate_pct": 40.0, "n": 12}},
        }
    }
    monkeypatch.setattr(kr, "build_regime_strategy_map", lambda symbol: fake_map)
    monkeypatch.setattr(llm, "cloud_blocked", lambda: False)
    monkeypatch.setattr(llm, "get_client", lambda: object())
    monkeypatch.setattr(llm, "complete",
                        lambda client, messages, max_tokens=200: "趨勢盤突破時使用。")

    try:
        r = client.post(f"/knowledge/{kid}/usage-note", json={"symbol": "AAPL"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["usage_note"] == "趨勢盤突破時使用。"
        assert body["regime_affinity"]["best_regime"] == "trending"
        assert "trending" in body["regime_affinity"]["by_regime"]
    finally:
        _delete(kid)


# ========== step-06 ==========
def test_promote_requires_validated(monkeypatch):
    """candidate 不可直接 promote（無自動晉升路徑）→ 400；validated 才能 → curated。"""
    monkeypatch.setattr(settings, "EXPLORATIONS_DIR", str(Path(__file__).parent / "_tmp_expl_promote"))

    r = client.post("/knowledge", json={"name": "待審", "strategy_key": "macd"})
    kid = r.json()["id"]
    try:
        # candidate 直接 promote → 擋下
        r = client.post(f"/knowledge/{kid}/promote")
        assert r.status_code == 400, "candidate 不該能直接晉升"

        # 先流轉成 validated（模擬驗證通過），再 promote
        client.put(f"/knowledge/{kid}", json={"name": "待審", "strategy_key": "macd", "status": "validated"})
        r = client.post(f"/knowledge/{kid}/promote")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "curated"

        # 理由已寫進 explorations 記憶
        fname = explorations.filename_for_knowledge(kid, "macd")
        assert explorations.read_exploration(fname) is not None
    finally:
        _delete(kid)


def test_reject_writes_reason(monkeypatch):
    """reject → rejected，理由寫入 explorations。"""
    monkeypatch.setattr(settings, "EXPLORATIONS_DIR", str(Path(__file__).parent / "_tmp_expl_reject"))

    r = client.post("/knowledge", json={"name": "淘汰", "strategy_key": "momentum"})
    kid = r.json()["id"]
    try:
        r = client.post(f"/knowledge/{kid}/reject", json={"reason": "OOS 不加分"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "rejected"
        fname = explorations.filename_for_knowledge(kid, "momentum")
        content = explorations.read_exploration(fname)
        assert content is not None and "OOS 不加分" in content
    finally:
        _delete(kid)


# ========== Phase 8 改善：step-02 propose 端點 + composite 寫入把關 + reject 冪等 ==========
def test_propose_writes_candidates(monkeypatch):
    """POST /knowledge/propose：mock LLM 回兩組參數 → 寫成兩筆 candidate。"""
    monkeypatch.setattr(llm, "cloud_blocked", lambda: False)
    monkeypatch.setattr(llm, "get_client", lambda: object())
    monkeypatch.setattr(
        kr.strategy_generator, "propose_params",
        lambda client, strategy_key, scenario, n: [{"period": 14}, {"period": 21}],
    )

    r = client.post("/knowledge/propose",
                    json={"strategy_key": "rsi", "scenario": "震盪盤", "n": 2})
    assert r.status_code == 200, r.text
    created = r.json()["created"]
    assert len(created) == 2
    assert all(k["status"] == "candidate" for k in created)
    try:
        for k in created:
            assert k["strategy_key"] == "rsi"
    finally:
        for k in created:
            _delete(k["id"])


def test_propose_composite_blocked():
    """組合策略不支援 LLM 草擬 → 400（請手動建立）。"""
    r = client.post("/knowledge/propose",
                    json={"strategy_key": "composite", "scenario": "x", "n": 1})
    assert r.status_code == 400


def test_create_composite_invalid_params_400():
    """建 composite 帶非法子鍵 → 寫入前被擋（400），不進庫。"""
    r = client.post("/knowledge", json={
        "name": "壞組合",
        "strategy_key": "composite",
        "params": {"method": "vote", "members": [{"strategy_key": "不存在"}]},
    })
    assert r.status_code == 400, r.text


def test_create_composite_valid_ok():
    """建合法 composite → 200，可正常進庫。"""
    r = client.post("/knowledge", json={
        "name": "好組合",
        "strategy_key": "composite",
        "params": {
            "method": "vote",
            "members": [{"strategy_key": "rsi"}, {"strategy_key": "donchian"}],
        },
    })
    assert r.status_code == 200, r.text
    kid = r.json()["id"]
    _delete(kid)


def test_reject_idempotent(monkeypatch):
    """已 rejected 的再 reject → 400（冪等，不重複寫 explorations）。"""
    monkeypatch.setattr(settings, "EXPLORATIONS_DIR", str(Path(__file__).parent / "_tmp_expl_idem"))
    r = client.post("/knowledge", json={"name": "重退", "strategy_key": "rsi"})
    kid = r.json()["id"]
    try:
        r = client.post(f"/knowledge/{kid}/reject", json={"reason": "第一次"})
        assert r.status_code == 200, r.text
        r = client.post(f"/knowledge/{kid}/reject", json={"reason": "第二次"})
        assert r.status_code == 400, "已 rejected 不該能重複退回"
    finally:
        _delete(kid)


# ========== 部署：curated → Paper Bot（補斷層） ==========
def _delete_bots(bot_ids):
    db = SessionLocal()
    for bid in bot_ids:
        obj = db.query(Bot).filter(Bot.id == bid).first()
        if obj:
            db.delete(obj)
    db.commit()
    db.close()


def test_deploy_curated_creates_paper_bots(monkeypatch):
    """curated 策略 deploy 2 檔 → 2 個 Paper Bot（inactive、strategy/params 正確映射）。"""
    monkeypatch.setattr(settings, "EXPLORATIONS_DIR", str(Path(__file__).parent / "_tmp_expl_deploy"))
    r = client.post("/knowledge", json={
        "name": "RSI 反轉", "strategy_key": "rsi",
        "params": {"period": 14}, "status": "curated",
    })
    kid = r.json()["id"]
    bot_ids = []
    try:
        r = client.post(f"/knowledge/{kid}/deploy", json={
            "symbols": ["aapl", "MSFT"], "trade_amount": 2000.0,
            "stop_loss_pct": 0.05,
        })
        assert r.status_code == 200, r.text
        deployed = r.json()["deployed"]
        bot_ids = [d["bot_id"] for d in deployed]
        assert len(deployed) == 2
        # 驗證建出的 Bot：strategy/params 映射、Paper、未啟用、symbol 大寫
        db = SessionLocal()
        bots = db.query(Bot).filter(Bot.id.in_(bot_ids)).all()
        by_sym = {b.symbol: b for b in bots}
        db.close()
        assert set(by_sym) == {"AAPL", "MSFT"}
        for b in by_sym.values():
            assert b.strategy == "rsi"
            assert b.params == {"period": 14}
            assert b.trade_amount == 2000.0
            assert b.stop_loss_pct == 0.05
            assert b.is_active is False
            assert b.promotion_status == "paper"
    finally:
        _delete_bots(bot_ids)
        _delete(kid)


def test_deploy_non_curated_400():
    """非 curated（candidate）deploy → 400（守人在迴路：須先驗證 + 晉升）。"""
    r = client.post("/knowledge", json={"name": "未策展", "strategy_key": "macd"})
    kid = r.json()["id"]
    try:
        r = client.post(f"/knowledge/{kid}/deploy", json={"symbols": ["AAPL"]})
        assert r.status_code == 400, "candidate 不該能直接部署成 Bot"
    finally:
        _delete(kid)


def test_deploy_dedups_symbols(monkeypatch):
    """重複 symbol 去重 → 只建一個 Bot。"""
    monkeypatch.setattr(settings, "EXPLORATIONS_DIR", str(Path(__file__).parent / "_tmp_expl_deploy2"))
    r = client.post("/knowledge", json={
        "name": "去重測試", "strategy_key": "rsi", "status": "curated",
    })
    kid = r.json()["id"]
    bot_ids = []
    try:
        r = client.post(f"/knowledge/{kid}/deploy", json={"symbols": ["AAPL", "aapl", " AAPL "]})
        assert r.status_code == 200, r.text
        deployed = r.json()["deployed"]
        bot_ids = [d["bot_id"] for d in deployed]
        assert len(deployed) == 1 and deployed[0]["symbol"] == "AAPL"
    finally:
        _delete_bots(bot_ids)
        _delete(kid)


if __name__ == "__main__":
    test_knowledge_crud_and_status()
    test_get_missing_404()
    test_invalid_status_400()
    test_ranking_sorted_by_oos_ev()
    print("（usage_note / promote / reject / propose 需 pytest monkeypatch，請用 pytest 執行）")
    print("\n🎉 知識庫 API 測試通過！")
