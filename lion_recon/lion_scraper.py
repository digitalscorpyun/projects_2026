# lion_scraper.py — v1.4.0 — CANONICAL RSS ENGINE
# REFACTOR: Fresh CSV per run, persistent seen-state across runs
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
    if VERBOSE:
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
SEEN_FILE = CFG.get("seen_file", "lion_seen_urls.txt")
MAX_LINKS_PER_SOURCE = int(CFG.get("max_links_per_source", 25))

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def normalize_url(url: str) -> str:
    """
    Normalize URLs so harmless drift doesn't create false 'new article' hits.
    Drops common tracking params and fragments, preserves meaningful path/query.
    """
    parsed = urlparse(url)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"

    kept_params: List[str] = []
    if parsed.query:
        for pair in parsed.query.split("&"):
            if not pair.strip():
                continue
            key = pair.split("=", 1)[0].lower()
            if key.startswith("utm_"):
                continue
            if key in {"fbclid", "gclid", "mc_cid", "mc_eid"}:
                continue
            kept_params.append(pair)

    normalized = f"{scheme}://{netloc}{path}"
    if kept_params:
        normalized += "?" + "&".join(kept_params)
    return normalized


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
    abs_url = normalize_url(abs_url)

    path = urlparse(abs_url).path.lower()
    if path in ("", "/") or path.endswith(
        (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".pdf")
    ):
        return None

    return abs_url


def parse_datetime(raw: str) -> Optional[datetime]:
    raw = raw.strip()
    if not raw:
        return None

    # Try ISO first. Handles many modern meta datetime values.
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    # Then known formats.
    for fmt in TIME_FORMATS:
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue

    # Some pages include extra trailing text; trim and retry.
    trimmed = raw[:25]
    for fmt in TIME_FORMATS:
        try:
            dt = datetime.strptime(trimmed, fmt[: len(trimmed)])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue

    return None


def extract_date(soup: BeautifulSoup, url: str) -> Optional[datetime]:
    candidates: List[str] = []

    for sel, attrs in [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"name": "article:published_time"}),
        ("meta", {"property": "og:published_time"}),
        ("meta", {"name": "pubdate"}),
        ("meta", {"name": "publish-date"}),
        ("meta", {"name": "date"}),
        ("meta", {"itemprop": "datePublished"}),
        ("time", {}),
        ("pubDate", {}),
    ]:
        nodes = soup.find_all(sel, attrs)
        for node in nodes:
            if isinstance(node, Tag):
                raw = node.get("content") or node.get("datetime") or node.get_text(" ")
                if raw:
                    candidates.append(raw.strip())

    for raw in candidates:
        dt = parse_datetime(raw)
        if dt:
            return dt

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


def load_seen() -> set[str]:
    path = here_path(SEEN_FILE)
    if not os.path.exists(path):
        return set()

    try:
        with open(path, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}
    except Exception:
        return set()


def save_seen(seen: set[str]) -> None:
    path = here_path(SEEN_FILE)
    with open(path, "w", encoding="utf-8") as f:
        for url in sorted(seen):
            f.write(url + "\n")


async def fetch_text(
    session: aiohttp.ClientSession, url: str, retries: int = 1
) -> Optional[str]:
    for _ in range(retries + 1):
        try:
            async with session.get(
                url, allow_redirects=True, timeout=REQ_TIMEOUT
            ) as r:
                if r.status == 200:
                    return await r.text()
                return None
        except Exception:
            continue
    return None


async def enrich_article(
    session: aiohttp.ClientSession, url: str, source_name: str
) -> Optional[Dict[str, Any]]:
    norm_url = normalize_url(url)
    html = await fetch_text(session, norm_url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    try:
        title = (
            soup.title.get_text(strip=True)
            if soup.title and soup.title.get_text()
            else "Untitled"
        )
    except Exception:
        title = "Untitled"

    dt = extract_date(soup, norm_url)

    article_tag = soup.find("article") or soup.find("main") or soup.body
    txt = article_tag.get_text(" ", strip=True) if article_tag else ""
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
        "url": norm_url,
        "date": dt.strftime("%Y-%m-%d") if dt else "Undated",
        "host": urlparse(norm_url).netloc,
        "hits": hits,
        "words": words,
        "source": source_name,
    }


def dedupe_preserve_order(values: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


async def collect_source_links(
    session: aiohttp.ClientSession, source: Dict[str, Any]
) -> List[str]:
    name = source["name"]
    url = source["url"]
    is_rss = "rss" in url.lower() or url.endswith(".xml") or "feed" in url.lower()

    _log(f"Interrogating {name} ({'RSS' if is_rss else 'Static'})...")

    try:
        async with session.get(url, timeout=REQ_TIMEOUT) as r:
            content = await r.text()
    except Exception:
        _log(f"FAILED {name}: Connection Timeout")
        return []

    try:
        parser = "xml" if is_rss else "html.parser"
        soup = BeautifulSoup(content, parser)
    except Exception:
        _log(f"WRN: Parser error for {name}. Falling back.")
        soup = BeautifulSoup(content, "html.parser")

    links: List[str] = []

    if is_rss:
        items = soup.find_all("item") or soup.find_all("entry")
        for item in items:
            # RSS <link>https://...</link>
            link_node = item.find("link")
            if link_node:
                raw = (
                    link_node.text.strip()
                    if not link_node.has_attr("href")
                    else str(link_node["href"]).strip()
                )
                safe = safe_href(url, raw)
                if safe:
                    links.append(safe)

            # Atom <link rel="alternate" href="...">
            for alt_link in item.find_all("link"):
                href = alt_link.get("href")
                if href:
                    safe = safe_href(url, href)
                    if safe:
                        links.append(safe)
    else:
        selector = source.get("article_selector", "a")
        for a in soup.select(selector):
            if a.name == "a" and a.get("href"):
                safe = safe_href(url, a["href"])
                if safe:
                    links.append(safe)

    links = dedupe_preserve_order(links)[:MAX_LINKS_PER_SOURCE]
    _log(f"Found {len(links)} potential targets. Analyzing...")
    return links


async def scrape() -> List[Dict[str, Any]]:
    sources = CFG.get("sources", [])
    kept: List[Dict[str, Any]] = []

    seen = load_seen()
    new_seen: set[str] = set()

    connector = aiohttp.TCPConnector(limit=CONCURRENCY, ssl=False)
    timeout = aiohttp.ClientTimeout(total=REQ_TIMEOUT)

    async with aiohttp.ClientSession(
        headers={"User-Agent": UA},
        connector=connector,
        timeout=timeout,
    ) as session:
        for src in sources:
            name = src["name"]
            links = await collect_source_links(session, src)
            if not links:
                continue

            tasks = [enrich_article(session, u, name) for u in links]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            stabilized_count = 0
            new_count = 0

            for res in results:
                if isinstance(res, Exception) or not res:
                    continue

                stabilized_count += 1
                article_url = res["url"]

                if article_url in seen or article_url in new_seen:
                    continue

                kept.append(res)
                new_seen.add(article_url)
                new_count += 1

            _log(
                f"Interrogation Complete: {stabilized_count} assets stabilized | "
                f"{new_count} new."
            )

    seen.update(new_seen)
    save_seen(seen)
    return kept


def write_csvs(kept: List[Dict[str, Any]]) -> None:
    kept_sorted = sorted(kept, key=lambda x: (x["source"], x["date"], x["title"]))
    fieldnames = ["title", "url", "date", "host", "hits", "words", "source"]
    output_path = here_path(OUTPUT_CSV)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(kept_sorted)

    print(f"\n✅ Mission Complete | New Articles: {len(kept)} | 📄 {output_path}")


if __name__ == "__main__":
    _log("LION RECONNAISSANCE ENGINE v1.4.0 ONLINE")
    t0 = time.time()

    try:
        res_kept = asyncio.run(scrape())
        write_csvs(res_kept)
    except KeyboardInterrupt:
        _log("Mission Aborted by Operator.")

    print(f"⏱ Total Mission Time: {time.time() - t0:.1f}s")