# sunday_lion_scraper.py
# SUNDAY LION — GLOBAL EDITION ENGINE
# Derived from lion_scraper.py
# Emits: sunday_lion_scraper_output.csv

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
)

TRACKING_QUERY_KEYS = {
    "utm_source","utm_medium","utm_campaign","utm_term","utm_content",
    "utm_id","fbclid","gclid","mc_cid","mc_eid","ocid","cmpid","ito",
}

def here_path(*parts: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts)


def load_cfg() -> Dict[str, Any]:
    cfg_path = os.environ.get("LION_CFG") or here_path("sunday_lion_scraper_config.json")
    if not os.path.exists(cfg_path):
        raise FileNotFoundError(f"Config not found at: {cfg_path}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


CFG = load_cfg()

MAX_AGE_DAYS = int(CFG.get("cutoff_days", 14))
MIN_WORDS = int(CFG.get("min_words", 200))
CONCURRENCY = int(CFG.get("concurrency", 12))
REQ_TIMEOUT = int(CFG.get("timeout_sec", 25))
OUTPUT_CSV = CFG.get("output_csv", "sunday_lion_scraper_output.csv")

KEYWORDS = [str(k).strip() for k in CFG.get("keywords", []) if str(k).strip()]
KW_RE_LIST = [re.compile(re.escape(k), re.IGNORECASE) for k in KEYWORDS]

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
        if k.lower() in TRACKING_QUERY_KEYS:
            continue
        cleaned_query.append((k, v))

    query = urlencode(cleaned_query, doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def parse_datetime(raw: str) -> Optional[datetime]:
    if not raw:
        return None

    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass

    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass

    for fmt in TIME_FORMATS:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue

    return None


async def fetch_text(session, url):
    try:
        async with session.get(url, timeout=REQ_TIMEOUT) as r:
            if r.status != 200:
                return None
            return await r.text()
    except Exception:
        return None


async def collect_rss(session, source):
    name = source["name"]
    url = source["url"]

    _log(f"RSS scan: {name}")

    text = await fetch_text(session, url)
    if not text:
        return []

    soup = BeautifulSoup(text, "xml")

    rows = []

    for item in soup.find_all("item"):
        title = item.title.get_text(strip=True) if item.title else ""
        link = item.link.get_text(strip=True) if item.link else ""

        date_node = item.find("pubDate")
        dt = parse_datetime(date_node.get_text(strip=True)) if date_node else None

        rows.append({
            "title": title,
            "url": normalize_url(link),
            "date": dt.strftime("%Y-%m-%d") if dt else "Undated",
            "host": urlparse(link).netloc,
            "hits": 0,
            "words": len(title.split()),
            "source": name
        })

    return rows


async def collect_static(session, source):
    name = source["name"]
    url = source["url"]
    selector = source.get("article_selector", "article a, h2 a, h3 a")

    _log(f"Static scan: {name}")

    text = await fetch_text(session, url)
    if not text:
        return []

    soup = BeautifulSoup(text, "html.parser")

    rows = []

    for a in soup.select(selector):
        href = a.get("href")
        title = a.get_text(strip=True)

        if not href or not title:
            continue

        link = normalize_url(urljoin(url, href))

        rows.append({
            "title": title,
            "url": link,
            "date": "Undated",
            "host": urlparse(link).netloc,
            "hits": 0,
            "words": len(title.split()),
            "source": name
        })

    return rows


async def scrape():
    sources = CFG["sources"]

    results = []

    connector = aiohttp.TCPConnector(limit=CONCURRENCY, ssl=False)

    async with aiohttp.ClientSession(headers={"User-Agent": UA}, connector=connector) as session:

        for src in sources:
            url = src["url"]

            if "rss" in url.lower() or "feed" in url.lower() or url.endswith(".xml"):
                rows = await collect_rss(session, src)
            else:
                rows = await collect_static(session, src)

            results.extend(rows)

    return results


def write_csv(rows):

    fieldnames = ["title","url","date","host","hits","words","source"]

    output_path = here_path(OUTPUT_CSV)

    with open(output_path,"w",newline="",encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ Sunday Lion Complete | {len(rows)} Articles | {output_path}")


if __name__ == "__main__":

    _log("SUNDAY LION ENGINE ONLINE")

    t0 = time.time()

    rows = asyncio.run(scrape())

    write_csv(rows)

    print(f"⏱ Runtime: {time.time() - t0:.1f}s")
