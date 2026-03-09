# lion_scraper.py — v1.5.0 — CANONICAL RSS ENGINE
# REFACTOR: strict article hygiene, fresh CSV per run, persistent seen-state,
#           RSS-first metadata capture, aggressive junk suppression
# STATUS: CANONICAL | PRODUCTION READY

from __future__ import annotations

import asyncio
import csv
import json
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse, urldefrag

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
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S %Z",
)

TRACKING_QUERY_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ocid",
    "cmpid",
    "ito",
    "at_medium",
    "at_campaign",
    "rss",
    "output",
}

BANNED_TITLE_PATTERNS = [
    r"^subscribe to read$",
    r"^about us(?:\s*\|.*)?$",
    r"^breaking news headlines today(?:\s*\|.*)?$",
    r"^section icon$",
    r"^ground news(?:\s*[-|].*)?$",
    r"^ground news - frequently asked questions$",
    r"^ground news \| mission$",
    r"^testimonials \| ground news$",
    r"^bulk subscription$",
    r"^careers(?:\s*\|.*)?$",
    r"^affiliate program.*$",
    r"^tech now\s*-\s*.*bbc iPlayer$",
]

BANNED_URL_PATTERNS = [
    r"/about/?$",
    r"/about-us/?$",
    r"/faq/?$",
    r"/frequently-asked-questions/?$",
    r"/mission/?$",
    r"/gift/?$",
    r"/subscribe/?$",
    r"/careers/?$",
    r"/affiliates/?$",
    r"/blog/?$",
    r"/extension/?$",
    r"/group-subscriptions/?$",
    r"/free-trial",
    r"/interest/",
    r"/apps/details",
    r"/iplayer/",
    r"/tag/",
    r"/tags/",
    r"/topic/",
    r"/topics/",
    r"/author/",
    r"/authors/",
    r"/newsletter",
    r"/newsletters",
]

NON_ARTICLE_HOST_RULES = {
    "ground.news": [
        r"^/$",
        r"^/about/?$",
        r"^/blog/?$",
        r"^/gift/?$",
        r"^/mission/?$",
        r"^/subscribe/?$",
        r"^/testimonials/?$",
        r"^/extension/?$",
        r"^/interest/.*$",
        r"^/free-trial-landing/?$",
        r"^/blindspot/?$",
        r"^/group-subscriptions/?$",
        r"^/careers/?$",
        r"^/frequently-asked-questions/?$",
        r"^/affiliates/?$",
    ],
    "www.ft.com": [
        r"^/content/[0-9a-f-]+$",
    ],
}

ALLOWLIST_HOSTS_REQUIRE_PATH_MATCH = {
    "www.ft.com": [r"^/content/[0-9a-f-]+$"],
}

BANNED_TITLE_RES = [re.compile(p, re.IGNORECASE) for p in BANNED_TITLE_PATTERNS]
BANNED_URL_RES = [re.compile(p, re.IGNORECASE) for p in BANNED_URL_PATTERNS]


def here_path(*parts: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts)


def load_cfg() -> Dict[str, Any]:
    cfg_path = os.environ.get("LION_CFG") or here_path("lion_scraper_config.json")
    if not os.path.exists(cfg_path):
        raise FileNotFoundError(f"Config not found at: {cfg_path}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


CFG = load_cfg()
MAX_AGE_DAYS = int(CFG.get("max_age_days", 7))
MIN_WORDS = int(CFG.get("min_words", 300))
CONCURRENCY = int(CFG.get("concurrency", 12))
REQ_TIMEOUT = int(CFG.get("timeout_sec", 25))
REJECT_UNDATED = bool(CFG.get("reject_undated", True))
KEYWORDS = [str(k).strip() for k in CFG.get("keywords", []) if str(k).strip()]
KW_RE_LIST = [re.compile(re.escape(k), re.IGNORECASE) for k in KEYWORDS]
REQUIRE_KEYWORD = bool(CFG.get("require_keyword", False))
OUTPUT_CSV = CFG.get("output_csv", "lion_scraper_output.csv")
SEEN_FILE = CFG.get("seen_file", "lion_seen_urls.txt")
MAX_LINKS_PER_SOURCE = int(CFG.get("max_links_per_source", 50))
MIN_TITLE_LEN = int(CFG.get("min_title_len", 12))
STRICT_ARTICLE_MODE = bool(CFG.get("strict_article_mode", True))
ALLOW_RSS_SUMMARY_WORDS = int(CFG.get("allow_rss_summary_words", 120))
DEFAULT_RETRIES = int(CFG.get("retries", 1))

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def normalize_url(url: str) -> str:
    url, _ = urldefrag(url)
    parsed = urlparse(url)

    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"

    cleaned_query = []
    for k, v in parse_qsl(parsed.query, keep_blank_values=True):
        if k.lower() in TRACKING_QUERY_KEYS or k.lower().startswith("utm_"):
            continue
        cleaned_query.append((k, v))

    query = urlencode(cleaned_query, doseq=True)
    normalized = urlunparse((scheme, netloc, path, "", query, ""))
    return normalized


def safe_href(base_url: str, href: Any) -> Optional[str]:
    if not isinstance(href, str):
        return None

    href = href.strip()
    if not href or href.startswith(("javascript:", "mailto:", "#")):
        return None

    if href.startswith("//"):
        href = "https:" + href

    abs_url = urljoin(base_url if base_url.endswith("/") else base_url + "/", href)
    abs_url = normalize_url(abs_url)

    parsed = urlparse(abs_url)
    path = parsed.path.lower()

    if path in ("", "/"):
        return None

    if path.endswith((".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".pdf", ".xml")):
        return None

    if is_banned_url(abs_url):
        return None

    return abs_url


def host_matches(hostname: str, host_rule: str) -> bool:
    hostname = hostname.lower()
    host_rule = host_rule.lower()
    return hostname == host_rule or hostname.endswith("." + host_rule)


def is_banned_url(url: str) -> bool:
    if any(rx.search(url) for rx in BANNED_URL_RES):
        return True

    parsed = urlparse(url)
    hostname = parsed.netloc.lower()
    path = parsed.path or "/"

    for host_rule, patterns in NON_ARTICLE_HOST_RULES.items():
        if host_matches(hostname, host_rule):
            for pat in patterns:
                if re.search(pat, path, re.IGNORECASE):
                    return True

    for host_rule, patterns in ALLOWLIST_HOSTS_REQUIRE_PATH_MATCH.items():
        if host_matches(hostname, host_rule):
            if not any(re.search(pat, path, re.IGNORECASE) for pat in patterns):
                return True

    return False


def is_banned_title(title: str) -> bool:
    clean = " ".join(title.split()).strip()
    if not clean:
        return True
    if len(clean) < MIN_TITLE_LEN:
        return True
    return any(rx.search(clean) for rx in BANNED_TITLE_RES)


def parse_datetime(raw: str) -> Optional[datetime]:
    raw = raw.strip()
    if not raw:
        return None

    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    for fmt in TIME_FORMATS:
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue

    return None


def extract_date_from_url(url: str) -> Optional[datetime]:
    m = DATE_URL_PAT.search(url)
    if not m:
        return None

    gd = m.groupdict()
    try:
        year = int(gd["y"] or gd["y2"])
        month = int(gd["m"] or gd["m2"])
        day = int(gd["d"] or gd["d2"])
        return datetime(year, month, day, tzinfo=timezone.utc)
    except Exception:
        return None


def extract_date_from_soup(soup: BeautifulSoup, url: str) -> Optional[datetime]:
    candidates: List[str] = []

    selectors = [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"name": "article:published_time"}),
        ("meta", {"property": "og:published_time"}),
        ("meta", {"name": "publish-date"}),
        ("meta", {"name": "pubdate"}),
        ("meta", {"name": "date"}),
        ("meta", {"itemprop": "datePublished"}),
        ("time", {}),
        ("pubDate", {}),
    ]

    for sel, attrs in selectors:
        nodes = soup.find_all(sel, attrs)
        for node in nodes:
            if not isinstance(node, Tag):
                continue
            raw = node.get("content") or node.get("datetime") or node.get_text(" ", strip=True)
            if raw:
                candidates.append(raw.strip())

    for raw in candidates:
        dt = parse_datetime(raw)
        if dt:
            return dt

    return extract_date_from_url(url)


def text_word_count(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


def summarize_rss_description(item: Tag) -> str:
    parts: List[str] = []
    for name in ("description", "summary", "content", "content:encoded"):
        node = item.find(name)
        if node:
            raw = node.get_text(" ", strip=True)
            if raw:
                parts.append(raw)
    return " ".join(parts).strip()


def clean_title(raw_title: str) -> str:
    return " ".join((raw_title or "").split()).strip()


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
    session: aiohttp.ClientSession,
    url: str,
    retries: int = DEFAULT_RETRIES,
) -> Optional[str]:
    for _ in range(retries + 1):
        try:
            async with session.get(url, allow_redirects=True, timeout=REQ_TIMEOUT) as r:
                if r.status != 200:
                    continue
                content_type = (r.headers.get("Content-Type") or "").lower()
                if "html" not in content_type and "xml" not in content_type and "text" not in content_type:
                    continue
                return await r.text()
        except Exception:
            continue
    return None


def build_candidate_from_rss_item(source_name: str, feed_url: str, item: Tag) -> Optional[Dict[str, Any]]:
    link: Optional[str] = None

    for link_node in item.find_all("link"):
        href = link_node.get("href")
        if href:
            link = safe_href(feed_url, href)
            if link:
                break

        text_link = link_node.get_text(" ", strip=True)
        if text_link:
            link = safe_href(feed_url, text_link)
            if link:
                break

    if not link:
        guid = item.find("guid")
        if guid:
            guid_text = guid.get_text(" ", strip=True)
            if guid_text.startswith("http://") or guid_text.startswith("https://"):
                link = safe_href(feed_url, guid_text)

    if not link:
        return None

    title_node = item.find("title")
    title = clean_title(title_node.get_text(" ", strip=True) if title_node else "")
    if is_banned_title(title):
        return None

    raw_date = None
    for tag_name in ("pubDate", "published", "updated", "dc:date"):
        node = item.find(tag_name)
        if node:
            raw_date = node.get_text(" ", strip=True)
            if raw_date:
                break

    dt = parse_datetime(raw_date) if raw_date else None
    if not dt:
        dt = extract_date_from_url(link)

    summary = summarize_rss_description(item)
    words = text_word_count(summary)
    full_text = f"{title} {summary}".strip()
    hits = sum(1 for rx in KW_RE_LIST if rx.search(full_text)) if KW_RE_LIST else 0

    return {
        "title": title,
        "url": link,
        "date_obj": dt,
        "date": dt.strftime("%Y-%m-%d") if dt else "Undated",
        "host": urlparse(link).netloc,
        "hits": hits,
        "words": words,
        "source": source_name,
        "rss_summary": summary,
    }


def dedupe_candidates_preserve_order(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for candidate in candidates:
        url = candidate["url"]
        if url in seen:
            continue
        seen.add(url)
        out.append(candidate)
    return out


def passes_common_filters(
    title: str,
    url: str,
    dt: Optional[datetime],
    words: int,
    hits: int,
    allow_rss_summary: bool = False,
) -> bool:
    if is_banned_title(title):
        return False

    if is_banned_url(url):
        return False

    if REQUIRE_KEYWORD and hits == 0:
        return False

    if REJECT_UNDATED and not dt:
        return False

    if dt and (datetime.now(timezone.utc) - dt).days > MAX_AGE_DAYS:
        return False

    if allow_rss_summary:
        if words < ALLOW_RSS_SUMMARY_WORDS:
            return False
    else:
        if words < MIN_WORDS:
            return False

    return True


async def enrich_article(
    session: aiohttp.ClientSession,
    candidate: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    url = normalize_url(candidate["url"])
    html = await fetch_text(session, url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    try:
        page_title = (
            soup.title.get_text(strip=True)
            if soup.title and soup.title.get_text()
            else candidate["title"]
        )
    except Exception:
        page_title = candidate["title"]

    title = clean_title(page_title) or candidate["title"]
    if is_banned_title(title):
        return None

    dt = extract_date_from_soup(soup, url) or candidate.get("date_obj")

    article_tag = (
        soup.find("article")
        or soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.body
    )

    txt = article_tag.get_text(" ", strip=True) if article_tag else ""
    words = text_word_count(txt)

    if STRICT_ARTICLE_MODE:
        if not soup.find("article") and not dt:
            return None

    full_text = f"{title} {txt}".strip()
    hits = sum(1 for rx in KW_RE_LIST if rx.search(full_text)) if KW_RE_LIST else 0

    if not passes_common_filters(
        title=title,
        url=url,
        dt=dt,
        words=words,
        hits=hits,
        allow_rss_summary=False,
    ):
        return None

    return {
        "title": title,
        "url": url,
        "date_obj": dt,
        "date": dt.strftime("%Y-%m-%d") if dt else "Undated",
        "host": urlparse(url).netloc,
        "hits": hits,
        "words": words,
        "source": candidate["source"],
    }


async def collect_rss_candidates(
    session: aiohttp.ClientSession,
    source: Dict[str, Any],
) -> List[Dict[str, Any]]:
    name = source["name"]
    url = source["url"]

    _log(f"Interrogating {name} (RSS)...")

    content = await fetch_text(session, url)
    if not content:
        _log(f"FAILED {name}: feed unavailable")
        return []

    try:
        soup = BeautifulSoup(content, "xml")
    except Exception:
        soup = BeautifulSoup(content, "html.parser")

    items = soup.find_all("item") or soup.find_all("entry")
    candidates: List[Dict[str, Any]] = []

    for item in items:
        cand = build_candidate_from_rss_item(name, url, item)
        if not cand:
            continue

        if not passes_common_filters(
            title=cand["title"],
            url=cand["url"],
            dt=cand["date_obj"],
            words=cand["words"],
            hits=cand["hits"],
            allow_rss_summary=True,
        ):
            continue

        candidates.append(cand)

    candidates = dedupe_candidates_preserve_order(candidates)[:MAX_LINKS_PER_SOURCE]
    _log(f"Found {len(candidates)} feed candidates. Analyzing...")
    return candidates


async def collect_static_candidates(
    session: aiohttp.ClientSession,
    source: Dict[str, Any],
) -> List[Dict[str, Any]]:
    name = source["name"]
    url = source["url"]

    _log(f"Interrogating {name} (Static)...")

    content = await fetch_text(session, url)
    if not content:
        _log(f"FAILED {name}: page unavailable")
        return []

    try:
        soup = BeautifulSoup(content, "html.parser")
    except Exception:
        _log(f"WRN: Parser error for {name}. Falling back.")
        soup = BeautifulSoup(content, "html.parser")

    selector = source.get("article_selector", "a")
    candidates: List[Dict[str, Any]] = []

    for a in soup.select(selector):
        if a.name != "a":
            continue

        href = a.get("href")
        link = safe_href(url, href)
        if not link:
            continue

        title = clean_title(a.get_text(" ", strip=True))
        if not title or is_banned_title(title):
            continue

        dt = extract_date_from_url(link)
        hits = sum(1 for rx in KW_RE_LIST if rx.search(title)) if KW_RE_LIST else 0

        candidates.append(
            {
                "title": title,
                "url": link,
                "date_obj": dt,
                "date": dt.strftime("%Y-%m-%d") if dt else "Undated",
                "host": urlparse(link).netloc,
                "hits": hits,
                "words": len(title.split()),
                "source": name,
                "rss_summary": "",
            }
        )

    candidates = dedupe_candidates_preserve_order(candidates)[:MAX_LINKS_PER_SOURCE]
    _log(f"Found {len(candidates)} page candidates. Analyzing...")
    return candidates


async def collect_candidates(
    session: aiohttp.ClientSession,
    source: Dict[str, Any],
) -> List[Dict[str, Any]]:
    url = source["url"]
    is_rss = "rss" in url.lower() or url.endswith(".xml") or "feed" in url.lower()

    if is_rss:
        return await collect_rss_candidates(session, source)
    return await collect_static_candidates(session, source)


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
            candidates = await collect_candidates(session, src)
            if not candidates:
                _log(f"Interrogation Complete: 0 candidates retained for {name}.")
                continue

            unseen_candidates = [
                c for c in candidates
                if c["url"] not in seen and c["url"] not in new_seen
            ]

            if not unseen_candidates:
                _log(f"Interrogation Complete: 0 unseen candidates for {name}.")
                continue

            tasks = [enrich_article(session, candidate) for candidate in unseen_candidates]
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
    kept_sorted = sorted(
        kept,
        key=lambda x: (x["source"], x["date"], x["title"].lower()),
    )
    fieldnames = ["title", "url", "date", "host", "hits", "words", "source"]
    output_path = here_path(OUTPUT_CSV)

    cleaned_rows = [{k: row[k] for k in fieldnames} for row in kept_sorted]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    print(f"\n✅ Mission Complete | New Articles: {len(kept)} | 📄 {output_path}")


if __name__ == "__main__":
    _log("LION RECONNAISSANCE ENGINE v1.5.0 ONLINE")
    t0 = time.time()

    try:
        res_kept = asyncio.run(scrape())
        write_csvs(res_kept)
    except KeyboardInterrupt:
        _log("Mission Aborted by Operator.")

    print(f"⏱ Total Mission Time: {time.time() - t0:.1f}s")