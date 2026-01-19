# lion_scraper.py — v1.3.2 — THE CANONICAL RSS ENGINE
# RECTIFICATION: Robust title extraction (HTML drift hardening)
# STATUS: CANONICAL | PRODUCTION READY

from __future__ import annotations
import asyncio
import csv
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse, urldefrag

import aiohttp
from bs4 import BeautifulSoup, Tag
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="bs4")

# ============================================================
# Runtime flags / Config
# ============================================================
VERBOSE = True


def _log(msg: str) -> None:
    print(f"✶ {msg}")


DATE_URL_PAT = re.compile(
    r"/(?:(?P<y>\d{4})/(?P<m>\d{1,2})/(?P<d>\d{1,2})|"
    r"(?P<m2>\d{1,2})/(?P<d2>\d{1,2})/(?P<y2>\d{4}))(?:/|$)"
)

TIME_FORMATS = (
    "%b %d, %Y",
    "%B %d, %Y",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S%Z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%m/%d/%Y",
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S %Z",
)


def here_path(*parts: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts)


def load_cfg() -> Dict[str, Any]:
    cfg_path = os.environ.get("LION_CFG") or here_path("lion_scraper_config.json")
    if not os.path.exists(cfg_path):
        raise FileNotFoundError(f"Config not found at: {cfg_path}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


CFG = load_cfg()
MAX_AGE_DAYS = int(CFG.get("max_age_days", 14))
MIN_WORDS = int(CFG.get("min_words", 200))
CONCURRENCY = int(CFG.get("concurrency", 12))
REQ_TIMEOUT = int(CFG.get("timeout_sec", 25))
REJECT_UNDATED = bool(CFG.get("reject_undated", False))
KEYWORDS = [str(k).strip() for k in CFG.get("keywords", []) if str(k).strip()]
KW_RE_LIST = [re.compile(re.escape(k), re.IGNORECASE) for k in KEYWORDS]
REQUIRE_KEYWORD = bool(CFG.get("require_keyword", False))
OUTPUT_CSV = CFG.get("output_csv", "lion_scraper_output.csv")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def safe_href(base_url: str, href: Any) -> Optional[str]:
    if not isinstance(href, str):
        return None
    href = href.strip()
    if not href or href.startswith(("javascript:", "mailto:", "#")):
        return None

    href, _ = urldefrag(href)

    if href.startswith("//"):
        href = "https:" + href
    abs_url = urljoin(base_url if base_url.endswith("/") else base_url + "/", href)

    path = urlparse(abs_url).path.lower()
    if path in ("", "/") or path.endswith(
        (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".pdf")
    ):
        return None
    return abs_url


def extract_date(soup: BeautifulSoup, url: str) -> Optional[datetime]:
    for sel, attrs in [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"name": "article:published_time"}),
        ("meta", {"itemprop": "datePublished"}),
        ("meta", {"name": "pubdate"}),
        ("time", {}),
        ("pubDate", {}),
    ]:
        m = soup.find(sel, attrs)
        if isinstance(m, Tag):
            raw = m.get("content") or m.get("datetime") or m.get_text()
            if raw:
                raw_clean = raw.strip()[:25]
                for fmt in TIME_FORMATS:
                    try:
                        return datetime.strptime(
                            raw_clean, fmt[: len(raw_clean)]
                        ).replace(tzinfo=timezone.utc)
                    except Exception:
                        continue

    m = DATE_URL_PAT.search(url)
    if m:
        gd = m.groupdict()
        try:
            year = int(gd["y"] or gd["y2"])
            month = int(gd["m"] or gd["m2"])
            day = int(gd["d"] or gd["d2"])
            return datetime(year, month, day, tzinfo=timezone.utc)
        except Exception:
            pass
    return None


async def fetch_text(
    session: aiohttp.ClientSession, url: str, retries: int = 1
) -> Optional[str]:
    for _ in range(retries + 1):
        try:
            async with session.get(url, allow_redirects=True, timeout=REQ_TIMEOUT) as r:
                if r.status == 200:
                    return await r.text()
                return None
        except Exception:
            continue
    return None


async def enrich_article(
    session: aiohttp.ClientSession, url: str, source_name: str
) -> Optional[dict]:
    html = await fetch_text(session, url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # 🔧 PATCH: robust title extraction (HTML drift safe)
    try:
        title = (
            soup.title.get_text(strip=True)
            if soup.title and soup.title.get_text()
            else "Untitled"
        )
    except Exception:
        title = "Untitled"

    dt = extract_date(soup, url)

    article_tag = soup.find("article") or soup.find("main") or soup.body
    txt = article_tag.get_text(" ") if article_tag else ""
    words = len([w for w in txt.split() if w])

    full_text = f"{title} {txt}"
    hits = sum(1 for rx in KW_RE_LIST if rx.search(full_text)) if KW_RE_LIST else 0

    if REQUIRE_KEYWORD and hits == 0:
        return None
    if REJECT_UNDATED and not dt:
        return None
    if dt and (datetime.now(timezone.utc) - dt).days > MAX_AGE_DAYS:
        return None
    if words < MIN_WORDS:
        return None

    return {
        "title": " ".join(title.split()),
        "url": url,
        "date": dt.strftime("%Y-%m-%d") if dt else "Undated",
        "host": urlparse(url).netloc,
        "hits": hits,
        "words": words,
        "source": source_name,
    }


async def scrape():
    sources = CFG.get("sources", [])
    kept = []

    async with aiohttp.ClientSession(headers={"User-Agent": UA}) as session:
        for src in sources:
            name, url = src["name"], src["url"]
            is_rss = (
                "rss" in url.lower() or url.endswith(".xml") or "feed" in url.lower()
            )
            _log(f"Interrogating {name} ({'RSS' if is_rss else 'Static'})...")

            try:
                async with session.get(url, timeout=REQ_TIMEOUT) as r:
                    content = await r.text()
            except Exception:
                _log(f"FAILED {name}: Connection Timeout")
                continue

            try:
                parser = "xml" if is_rss else "html.parser"
                soup = BeautifulSoup(content, parser)
            except Exception:
                _log(f"WRN: Parser error for {name}. Falling back.")
                soup = BeautifulSoup(content, "html.parser")

            links = []
            if is_rss:
                items = soup.find_all("item") or soup.find_all("entry")
                for item in items:
                    link_node = item.find("link")
                    if link_node:
                        u = (
                            link_node.text
                            if not link_node.has_attr("href")
                            else link_node["href"]
                        )
                        if u:
                            links.append(u.strip())
            else:
                selector = src.get("article_selector", "a")
                for a in soup.select(selector):
                    if a.name == "a" and a.get("href"):
                        u = safe_href(url, a["href"])
                        if u:
                            links.append(u)

            links = list(set(links))[:25]
            _log(f"Found {len(links)} potential targets. Analyzing...")

            tasks = [enrich_article(session, u, name) for u in links]
            results = await asyncio.gather(*tasks)

            count = 0
            for res in results:
                if res:
                    kept.append(res)
                    count += 1
            _log(f"Interrogation Complete: {count} assets stabilized.")

    return kept


def write_csvs(kept: List[Dict[str, Any]]):
    kept_sorted = sorted(kept, key=lambda x: (x["source"], x["date"]))
    fieldnames = ["title", "url", "date", "host", "hits", "words", "source"]
    output_path = here_path(OUTPUT_CSV)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(kept_sorted)

    print(f"\n✅ Mission Complete | Kept: {len(kept)} | 📄 {output_path}")


if __name__ == "__main__":
    _log("LION RECONNAISSANCE ENGINE v1.3.2 ONLINE")
    t0 = time.time()
    try:
        res_kept = asyncio.run(scrape())
        write_csvs(res_kept)
    except KeyboardInterrupt:
        _log("Mission Aborted by Operator.")

    print(f"⏱ Total Mission Time: {time.time() - t0:.1f}s")
