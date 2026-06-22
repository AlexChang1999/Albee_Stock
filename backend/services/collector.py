"""
市場蒐集員 — 爬蟲收料（Phase 10 step-04）
============================================
定時從網路收「策略描述文字」進 raw_strategy_finds 表，當人 / strategy-builder skill
把它寫成可跑策略的素材。**爬蟲只負責收料、不負責驗證**——收回來的點子一律走既有引擎
（OOS 閘 / optimizer / validation）證明自己，本檔不寫策略碼、不部署、不下單。

來源優先序（守 robots/ToS、加 User-Agent 與節流，best-effort 連不上不阻斷）：
  1. RSS / Atom feed（Reddit、部落格）——標準 XML，用 stdlib 解析，零重依賴。
  2. 靜態 HTML 列表頁——用 beautifulsoup4 撿文章連結（次要備援）。

股價**不爬**（反模式：慢 / 易封 / 髒）——歷史 / 即時資料一律走既有 market_data。

設計：
- parse_rss / parse_html_listing / dedup_rows / upsert_finds 都是純函式，
  用本地樣本測（不連網）。fetch_url / run_collector_scan 才碰網路 / DB。
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urlparse
from xml.etree import ElementTree

from backend.config import settings
from backend.database import SessionLocal
from backend.models import RawStrategyFind
from backend.services import notifier

# 抓取逾時（秒）：收料是背景工作，給寬一點但不無限等
_FETCH_TIMEOUT_SEC = 15


def _strip_ns(tag: str) -> str:
    """去掉 XML 標籤的命名空間前綴（Atom 會有 {http://www.w3.org/2005/Atom}）。"""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _text(el) -> str:
    """安全取元素文字（None / 空白都回空字串）。"""
    return (el.text or "").strip() if el is not None else ""


def _clip(s: str, limit: int = 500) -> str:
    """摘要太長截斷，避免 DB 塞一整篇文章。"""
    s = (s or "").strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


def parse_rss(xml_text: str, *, source: str = "") -> list[dict]:
    """
    解析 RSS 2.0 / Atom feed 的 XML，抽出每篇文章為素材 dict。純函式、不碰網路。

    同時支援：
    - RSS 2.0：<channel><item><title/><link/><description/></item>
    - Atom   ：<feed><entry><title/><link href=.../><summary/></entry>

    :return: [{source, source_url, title, summary}, ...]；解析失敗回空清單（best-effort）。
    """
    try:
        root = ElementTree.fromstring(xml_text)
    except Exception:
        return []

    rows = []
    # RSS 用 <item>、Atom 用 <entry>；用去命名空間後的標籤名一起找
    for node in root.iter():
        tag = _strip_ns(node.tag)
        if tag not in ("item", "entry"):
            continue
        title = url = summary = ""
        for child in node:
            ctag = _strip_ns(child.tag)
            if ctag == "title":
                title = _text(child)
            elif ctag == "link":
                # RSS：文字就是網址；Atom：網址在 href 屬性
                url = _text(child) or child.attrib.get("href", "").strip()
            elif ctag in ("description", "summary", "content"):
                summary = summary or _text(child)
        if not url:
            continue  # 沒網址 → 無法去重 / 回溯來源，略過
        rows.append({
            "source": source or _host(url),
            "source_url": url,
            "title": _clip(title, 300),
            "summary": _clip(summary),
        })
    return rows


def parse_html_listing(html: str, *, source: str = "", min_text_len: int = 12) -> list[dict]:
    """
    從靜態 HTML 列表頁撿出文章連結（次要備援）。純函式、不碰網路。

    用 beautifulsoup4 撿所有 <a href>，把「連結文字夠長、看起來像標題」的當素材。
    刻意保守（只收 http(s) 絕對網址、過濾太短的錨點），避免把導覽列雜訊都收進來。

    :return: [{source, source_url, title, summary}, ...]；沒裝 bs4 / 解析失敗回空清單。
    """
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return []
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return []

    rows, seen = [], set()
    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        text = a.get_text(strip=True)
        if not href.startswith(("http://", "https://")):
            continue  # 只收絕對網址（相對連結無來源上下文，略過）
        if len(text) < min_text_len:
            continue  # 太短的錨點多半是導覽 / 標籤，不是文章標題
        if href in seen:
            continue
        seen.add(href)
        rows.append({
            "source": source or _host(href),
            "source_url": href,
            "title": _clip(text, 300),
            "summary": "",
        })
    return rows


def _host(url: str) -> str:
    """從網址取網域當來源標籤；解析不出來回空字串。"""
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def parse_keywords(raw: str) -> list[str]:
    """把逗號分隔的監控關鍵字字串清成清單（去空白、去重、保留原大小寫供顯示）。純函式。"""
    seen, out = set(), []
    for part in (raw or "").split(","):
        kw = part.strip()
        if kw and kw.lower() not in seen:
            seen.add(kw.lower())
            out.append(kw)
    return out


def tag_watch_rows(rows: list[dict], keywords: list[str]) -> int:
    """
    未上市公司關鍵字監控：對每列素材比對標題+摘要（不分大小寫），
    命中就在 row["tags"] 寫入 "watch:<關鍵字>"（多個用逗號接）。純函式、就地標記。

    :return: 命中的列數（給通知用）。
    """
    if not keywords:
        return 0
    hits = 0
    for row in rows or []:
        text = f"{row.get('title', '')} {row.get('summary', '')}".lower()
        matched = [kw for kw in keywords if kw.lower() in text]
        if matched:
            row["tags"] = ",".join(f"watch:{kw}" for kw in matched)
            hits += 1
    return hits


def dedup_rows(rows: list[dict]) -> list[dict]:
    """同一批內依 source_url 去重（保留第一筆）。純函式。"""
    seen, out = set(), []
    for r in rows or []:
        url = r.get("source_url")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(r)
    return out


def upsert_finds(db, rows: list[dict]) -> dict:
    """
    把素材列寫進 raw_strategy_finds：同 source_url 視為同一篇，**已存在就跳過**
    （保留既有 status，避免把人已 triaged/discarded 的東西又打回 new）。

    冪等：同一批 rows 連跑兩次，第二次全部跳過、不重複堆積。
    :return: {"inserted": 新增數, "skipped": 已存在跳過數, "watch_hits": 新增中命中監控標籤數}
    """
    inserted = skipped = watch_hits = 0
    for row in dedup_rows(rows):
        url = row.get("source_url")
        if not url:
            continue
        exists = (
            db.query(RawStrategyFind)
            .filter(RawStrategyFind.source_url == url)
            .first()
        )
        if exists is not None:
            skipped += 1
            continue
        db.add(RawStrategyFind(
            source=row.get("source") or _host(url),
            source_url=url,
            title=row.get("title") or "",
            summary=row.get("summary") or "",
            fetched_at=datetime.now(),
            status="new",
            tags=row.get("tags"),  # 監控關鍵字命中標籤（tag_watch_rows 寫入，可空）
        ))
        inserted += 1
        if row.get("tags"):
            watch_hits += 1
    db.commit()
    return {"inserted": inserted, "skipped": skipped, "watch_hits": watch_hits}


def fetch_url(url: str) -> str | None:
    """
    抓單一網址的內容（best-effort）。帶 User-Agent 與逾時；任何錯誤回 None、不丟例外。

    尊重節流：同一個網域每輪只打一次（feed 清單本身就一站一條）；
    並行只發生在「不同網域之間」（collect_from_feeds 的小 ThreadPool），不對單站猛打。
    """
    import requests

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": settings.COLLECTOR_USER_AGENT},
            timeout=_FETCH_TIMEOUT_SEC,
        )
        if resp.status_code != 200:
            return None
        return resp.text
    except Exception:
        return None


def collect_from_feeds(feeds: list[str]) -> list[dict]:
    """
    抓 RSS feed 並解析成素材列（best-effort）。單一 feed 失敗不影響其他。

    多條 feed 用小 ThreadPool「並行」抓（不同網域互不打擾；同站每輪仍只一次請求），
    N 條 feed 的網路往返疊在一起。解析（parse_rss）回主執行緒做，純 CPU 很快。

    這裡只走 RSS（最穩、最尊重來源）。HTML 列表頁解析（parse_html_listing）保留給
    確有需求時呼叫，預設不主動爬任意網站。
    """
    feeds = list(feeds or [])
    if not feeds:
        return []
    workers = max(1, min(settings.FETCH_MAX_WORKERS, len(feeds)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pages = pool.map(fetch_url, feeds)  # 失敗的 feed 回 None（fetch_url 已吞錯）
    rows = []
    for url, xml in zip(feeds, pages):
        if not xml:
            continue
        rows.extend(parse_rss(xml, source=_host(url)))
    return dedup_rows(rows)


def run_collector_scan() -> dict:
    """
    排程週期入口（也是手動「跑一次」端點入口）：抓設定的 RSS feeds、把新素材 upsert
    進收件匣，有新料就提醒一次。

    - 沒設定任何 feed（COLLECTOR_RSS_FEEDS 留空）→ 不空轉，回 note 提示（手動端點才看得到）。
    - best-effort：抓不到 / 解析失敗都不讓排程崩（單篇失敗已在下層吞掉）。
    - **只收料、不建策略、不部署**：後續由探勘橋（discovery）/ 人接手。

    :return: {"feeds", "fetched", "inserted", "skipped", "watch_hits", "note"} 統計
             （手動端點用來回報；排程呼叫忽略回傳即可）。
    """
    feeds = _parse_feeds(settings.COLLECTOR_RSS_FEEDS)
    if not feeds:
        return {"feeds": 0, "fetched": 0, "inserted": 0, "skipped": 0,
                "watch_hits": 0, "note": "未設定 COLLECTOR_RSS_FEEDS，未收料"}

    rows = collect_from_feeds(feeds)
    if not rows:
        return {"feeds": len(feeds), "fetched": 0, "inserted": 0, "skipped": 0,
                "watch_hits": 0, "note": "feed 抓不到新內容"}

    # 未上市公司關鍵字監控：收料順手比對（SpaceX 等回不了測的公司，留檔追蹤）
    tag_watch_rows(rows, parse_keywords(settings.PRIVATE_WATCH_KEYWORDS))

    db = SessionLocal()
    try:
        result = upsert_finds(db, rows)
        if result["inserted"] > 0:
            # 收件匣累計總筆數（DB 全表）。舊版顯示的「跳過 N 篇已收過」是「這一輪 RSS
            # 抓回的批次裡有幾篇重複」，每輪 feed 都抓最新固定幾篇 → 收齊後永遠卡同一個
            # 死數字、又跟實際總收數對不上，會誤導。改顯示累計總數，真實且會成長。
            inbox_total = db.query(RawStrategyFind).count()
            msg = (
                f"📰 市場蒐集員收到 {result['inserted']} 篇新策略素材"
                f"（收件匣目前共 {inbox_total} 篇）。到「市場蒐集員」頁消化。"
            )
            if result.get("watch_hits"):
                msg += f"\n🛰️ 其中 {result['watch_hits']} 篇命中監控關鍵字（{settings.PRIVATE_WATCH_KEYWORDS}）。"
            notifier.notify(msg)
        return {"feeds": len(feeds), "fetched": len(rows), "inserted": result["inserted"],
                "skipped": result["skipped"], "watch_hits": result.get("watch_hits", 0),
                "note": "收料完成"}
    finally:
        db.close()


def _parse_feeds(raw: str) -> list[str]:
    """把逗號 / 換行分隔的 feed 網址字串清成清單（去空白、去重、只留 http(s)）。"""
    seen, out = set(), []
    for part in (raw or "").replace("\n", ",").split(","):
        url = part.strip()
        if url.startswith(("http://", "https://")) and url not in seen:
            seen.add(url)
            out.append(url)
    return out
