"""
市場蒐集員測試（Phase 10 step-04）
====================================
涵蓋：
1. 純函式 parse_rss：解析 RSS 2.0 與 Atom 兩種格式（本地樣本，不連網）。
2. 純函式 parse_html_listing：用 bs4 從靜態 HTML 撿文章連結（過濾太短 / 相對連結）。
3. 純函式 dedup_rows：同 source_url 去重。
4. 純函式 upsert_finds：同 source_url 不重複（冪等）、已存在保留 status。
5. run_collector_scan：沒設 feed 直接跳過；有新料 monkeypatch 抓取 + 攔截通知。
6. GET /collector/finds + PATCH 狀態流轉。

不連網：用臨時 SQLite + monkeypatch fetch_url / notify。

執行方式（專案根目錄）：
    venv\\Scripts\\python.exe -m pytest tests\\test_collector.py -q
"""

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.database import Base, get_db
from backend.models import RawStrategyFind
from backend.services import collector
from backend.services.collector import (
    parse_rss,
    parse_html_listing,
    dedup_rows,
    upsert_finds,
    run_collector_scan,
)


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'collector.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# 本地樣本：RSS 2.0
_RSS = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Algo Blog</title>
    <item>
      <title>A mean-reversion strategy on SPY</title>
      <link>https://blog.example.com/mean-reversion</link>
      <description>Buy when RSI &lt; 30, exit at the 20-day mean.</description>
    </item>
    <item>
      <title>Momentum rotation</title>
      <link>https://blog.example.com/momentum</link>
      <description>Rotate into the top-3 momentum names monthly.</description>
    </item>
  </channel>
</rss>"""

# 本地樣本：Atom（link 在 href、摘要在 summary）
_ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Quant Feed</title>
  <entry>
    <title>Pairs trading basics</title>
    <link href="https://quant.example.com/pairs"/>
    <summary>Cointegration-based pairs on two correlated tickers.</summary>
  </entry>
</feed>"""


# ---------- 1. parse_rss ----------
def test_parse_rss_2_0():
    rows = parse_rss(_RSS, source="algo")
    assert len(rows) == 2
    first = rows[0]
    assert first["title"] == "A mean-reversion strategy on SPY"
    assert first["source_url"] == "https://blog.example.com/mean-reversion"
    assert "RSI" in first["summary"]
    assert first["source"] == "algo"


def test_parse_atom():
    rows = parse_rss(_ATOM)
    assert len(rows) == 1
    assert rows[0]["title"] == "Pairs trading basics"
    # Atom 的網址在 href 屬性，要抓得到
    assert rows[0]["source_url"] == "https://quant.example.com/pairs"
    assert "Cointegration" in rows[0]["summary"]


def test_parse_rss_garbage_returns_empty():
    assert parse_rss("not xml at all") == []
    assert parse_rss("") == []


def test_parse_rss_skips_items_without_link():
    xml = """<rss><channel><item><title>No link here</title></item></channel></rss>"""
    assert parse_rss(xml) == []


# ---------- 2. parse_html_listing ----------
def test_parse_html_listing_picks_article_links():
    html = """
    <html><body>
      <a href="https://site.example.com/article-one">A complete guide to breakout strategies</a>
      <a href="https://site.example.com/article-two">Volatility targeting explained in depth</a>
      <a href="https://site.example.com/x">home</a>        <!-- 文字太短，濾掉 -->
      <a href="/relative/path">Relative link should be skipped</a>  <!-- 相對連結，濾掉 -->
    </body></html>
    """
    rows = parse_html_listing(html, source="site")
    urls = [r["source_url"] for r in rows]
    assert "https://site.example.com/article-one" in urls
    assert "https://site.example.com/article-two" in urls
    # 太短的錨點 / 相對連結都不收
    assert "https://site.example.com/x" not in urls
    assert all(u.startswith("http") for u in urls)


def test_parse_rss_cdata_html_summary():
    # 真實 feed 的 description 常是 CDATA 包 HTML：要解析得出來、不崩，且摘要有截斷上限
    xml = """<rss version="2.0"><channel><item>
      <title>Donchian breakout notes</title>
      <link>https://blog.example.com/donchian</link>
      <description><![CDATA[<p>Buy on a <b>20-day high</b> breakout.</p>]]></description>
    </item></channel></rss>"""
    rows = parse_rss(xml)
    assert len(rows) == 1
    assert "20-day high" in rows[0]["summary"]
    assert len(rows[0]["summary"]) <= 500  # _clip 截斷生效


# ---------- 2.5 collect_from_feeds：單一 feed 失敗不影響其他 ----------
def test_collect_from_feeds_skips_dead_feed(monkeypatch):
    # 第一個 feed 抓不到（回 None）、第二個正常：只收正常那個、不丟例外
    def fake_fetch(url):
        return None if "dead" in url else _RSS

    monkeypatch.setattr(collector, "fetch_url", fake_fetch)
    rows = collector.collect_from_feeds([
        "https://dead.example.com/feed",
        "https://blog.example.com/feed",
    ])
    assert len(rows) == 2  # 只有活 feed 的兩篇
    assert all("blog.example.com" in r["source_url"] for r in rows)


# ---------- 2.6 _parse_feeds：設定字串清洗 ----------
def test_parse_feeds_mixed_separators_and_junk():
    raw = """https://a.com/feed, https://b.com/feed
    not-a-url
    https://a.com/feed"""
    out = collector._parse_feeds(raw)
    # 逗號/換行混用都解析；非 http(s) 行丟掉；重複去重
    assert out == ["https://a.com/feed", "https://b.com/feed"]
    assert collector._parse_feeds("") == []
    assert collector._parse_feeds(None) == []


# ---------- 3. dedup_rows ----------
def test_dedup_rows_by_url():
    rows = [
        {"source_url": "https://a.com/1", "title": "x"},
        {"source_url": "https://a.com/1", "title": "dup"},
        {"source_url": "https://a.com/2", "title": "y"},
        {"source_url": None, "title": "no url"},
    ]
    out = dedup_rows(rows)
    assert [r["source_url"] for r in out] == ["https://a.com/1", "https://a.com/2"]


# ---------- 4. upsert_finds（冪等 + 保留 status） ----------
def test_upsert_idempotent_and_preserves_status(tmp_path):
    db = _session(tmp_path)
    rows = parse_rss(_RSS, source="algo")
    r1 = upsert_finds(db, rows)
    assert r1 == {"inserted": 2, "skipped": 0, "watch_hits": 0}
    assert db.query(RawStrategyFind).count() == 2

    # 把第一筆標成 triaged，再 upsert 同一批：全部已存在 → skip，status 保留
    first = db.query(RawStrategyFind).filter_by(source_url="https://blog.example.com/mean-reversion").first()
    first.status = "triaged"
    db.commit()

    r2 = upsert_finds(db, rows)
    assert r2 == {"inserted": 0, "skipped": 2, "watch_hits": 0}
    assert db.query(RawStrategyFind).count() == 2  # 沒重複堆積
    first = db.query(RawStrategyFind).filter_by(source_url="https://blog.example.com/mean-reversion").first()
    assert first.status == "triaged"  # 保留人工策展結果


# ---------- 5. run_collector_scan ----------
def test_scan_skips_when_no_feeds(monkeypatch, tmp_path):
    # 沒設 feed → 直接 return，不抓網、不寫表、不提醒
    monkeypatch.setattr(collector.settings, "COLLECTOR_RSS_FEEDS", "")
    notes = []
    monkeypatch.setattr(collector.notifier, "notify", lambda msg: notes.append(msg))
    called = {"fetch": 0}
    monkeypatch.setattr(collector, "fetch_url", lambda url: called.__setitem__("fetch", called["fetch"] + 1))

    run_collector_scan()
    assert called["fetch"] == 0
    assert notes == []


def test_scan_fetches_upserts_and_notifies(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'scan.db'}")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    monkeypatch.setattr(collector, "SessionLocal", TestingSession)
    monkeypatch.setattr(collector.settings, "COLLECTOR_RSS_FEEDS", "https://blog.example.com/feed")
    monkeypatch.setattr(collector, "fetch_url", lambda url: _RSS)  # 假抓取，回本地樣本
    notes = []
    monkeypatch.setattr(collector.notifier, "notify", lambda msg: notes.append(msg))

    run_collector_scan()

    db = TestingSession()
    try:
        assert db.query(RawStrategyFind).count() == 2
    finally:
        db.close()
    assert len(notes) == 1 and "2 篇" in notes[0]

    # 再跑一次：全已收過 → 不新增、不提醒（去重）
    run_collector_scan()
    assert len(notes) == 1


# ---------- 6. GET /collector/finds + PATCH ----------
@contextmanager
def _isolated_client(tmp_path):
    from backend.main import app

    engine = create_engine(
        f"sqlite:///{tmp_path / 'app_collector.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    def _override():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    try:
        with TestClient(app) as client:
            yield client, TestingSession
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_finds_api_list_and_status_transition(tmp_path):
    with _isolated_client(tmp_path) as (client, TestingSession):
        db = TestingSession()
        try:
            db.add_all([
                RawStrategyFind(source="a", source_url="https://a.com/1", title="One", status="new"),
                RawStrategyFind(source="b", source_url="https://b.com/2", title="Two", status="triaged"),
            ])
            db.commit()
            fid = db.query(RawStrategyFind).filter_by(source_url="https://a.com/1").first().id
        finally:
            db.close()

        # 列出全部
        rows = client.get("/collector/finds").json()
        assert {r["title"] for r in rows} == {"One", "Two"}

        # status 篩選
        new_only = client.get("/collector/finds?status=new").json()
        assert [r["title"] for r in new_only] == ["One"]

        # PATCH：new → built
        res = client.patch(f"/collector/finds/{fid}", json={"status": "built"})
        assert res.status_code == 200
        assert res.json()["status"] == "built"

        # 不合法 status → 400
        bad = client.patch(f"/collector/finds/{fid}", json={"status": "nonsense"})
        assert bad.status_code == 400

        # 不存在的 id → 404
        missing = client.patch("/collector/finds/99999", json={"status": "built"})
        assert missing.status_code == 404


# ---------- 7. 未上市公司關鍵字監控（watch tags）----------
def test_parse_keywords():
    from backend.services.collector import parse_keywords

    assert parse_keywords("SpaceX, OpenAI ,spacex,") == ["SpaceX", "OpenAI"]  # 去重不分大小寫
    assert parse_keywords("") == []
    assert parse_keywords(None) == []


def test_tag_watch_rows_matches_title_and_summary():
    from backend.services.collector import tag_watch_rows

    rows = [
        {"title": "SpaceX raises new round", "summary": ""},
        {"title": "Some ETF article", "summary": "mentions spacex starship plans"},
        {"title": "Unrelated", "summary": "nothing here"},
    ]
    hits = tag_watch_rows(rows, ["SpaceX"])
    assert hits == 2  # 標題命中 + 摘要命中（不分大小寫）
    assert rows[0]["tags"] == "watch:SpaceX"
    assert rows[1]["tags"] == "watch:SpaceX"
    assert "tags" not in rows[2]
    # 沒關鍵字 → 不動
    assert tag_watch_rows(rows, []) == 0


def test_upsert_writes_tags_and_api_filters_by_tag(tmp_path):
    from backend.services.collector import tag_watch_rows

    with _isolated_client(tmp_path) as (client, TestingSession):
        db = TestingSession()
        try:
            rows = [
                {"source": "x", "source_url": "https://x.com/sx", "title": "SpaceX news", "summary": ""},
                {"source": "x", "source_url": "https://x.com/other", "title": "Plain post", "summary": ""},
            ]
            tag_watch_rows(rows, ["SpaceX"])
            result = upsert_finds(db, rows)
            assert result["inserted"] == 2
            assert result["watch_hits"] == 1
        finally:
            db.close()

        # tag 篩選只回命中監控的素材
        watched = client.get("/collector/finds?tag=watch:SpaceX").json()
        assert [r["title"] for r in watched] == ["SpaceX news"]
        assert watched[0]["tags"] == "watch:SpaceX"
        # 不給 tag → 全部
        assert len(client.get("/collector/finds").json()) == 2


# ---------- 8. run_collector_scan 回統計 + /collector/scan 端點 + triage 欄位（Phase 14） ----------
def test_scan_returns_stats_when_no_feeds(monkeypatch):
    monkeypatch.setattr(collector.settings, "COLLECTOR_RSS_FEEDS", "")
    out = run_collector_scan()
    assert out["inserted"] == 0 and out["feeds"] == 0 and "note" in out


def test_scan_endpoint_and_triage_fields(tmp_path, monkeypatch):
    with _isolated_client(tmp_path) as (client, TestingSession):
        # 種一筆已被探勘橋處理過的素材：serialize 要帶出 triage_note / knowledge_id
        db = TestingSession()
        try:
            db.add(RawStrategyFind(
                source="a", source_url="https://a.com/built", title="Built one",
                status="built", triage_note="探勘橋：提案 rsi", knowledge_id=7,
            ))
            db.commit()
        finally:
            db.close()
        r = client.get("/collector/finds").json()[0]
        assert r["triage_note"] == "探勘橋：提案 rsi" and r["knowledge_id"] == 7

        # POST /collector/scan：沒設 feed → 回統計 dict（note 提示），不報錯
        monkeypatch.setattr(collector.settings, "COLLECTOR_RSS_FEEDS", "")
        res = client.post("/collector/scan")
        assert res.status_code == 200 and "note" in res.json()
