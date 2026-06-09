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
    :return: {"inserted": 新增數, "skipped": 已存在跳過數}
    """
    inserted = skipped = 0
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
        ))
        inserted += 1
    db.commit()
    return {"inserted": inserted, "skipped": skipped}


def fetch_url(url: str) -> str | None:
    """
    抓單一網址的內容（best-effort）。帶 User-Agent 與逾時；任何錯誤回 None、不丟例外。

    尊重節流：呼叫端逐一抓、別並發猛打，避免被封 IP。
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
    逐一抓 RSS feed 並解析成素材列（best-effort）。單一 feed 失敗不影響其他。

    這裡只走 RSS（最穩、最尊重來源）。HTML 列表頁解析（parse_html_listing）保留給
    確有需求時呼叫，預設不主動爬任意網站。
    """
    rows = []
    for url in feeds or []:
        xml = fetch_url(url)
        if not xml:
            continue
        rows.extend(parse_rss(xml, source=_host(url)))
    return dedup_rows(rows)


def run_collector_scan() -> None:
    """
    排程週期入口：抓設定的 RSS feeds、把新素材 upsert 進收件匣，有新料就提醒一次。

    - 沒設定任何 feed（COLLECTOR_RSS_FEEDS 留空）→ 直接 return，不空轉。
    - best-effort：抓不到 / 解析失敗都不讓排程崩（單篇失敗已在下層吞掉）。
    - **只收料、不建策略、不部署**：後續由人 / strategy-builder + OOS 閘接手。
    """
    feeds = _parse_feeds(settings.COLLECTOR_RSS_FEEDS)
    if not feeds:
        return

    rows = collect_from_feeds(feeds)
    if not rows:
        return

    db = SessionLocal()
    try:
        result = upsert_finds(db, rows)
        if result["inserted"] > 0:
            notifier.notify(
                f"📰 市場蒐集員收到 {result['inserted']} 篇新策略素材"
                f"（跳過 {result['skipped']} 篇已收過）。到「市場蒐集員」頁消化。"
            )
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
