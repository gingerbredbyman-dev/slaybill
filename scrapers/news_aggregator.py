"""
SLAYBILL — Broadway news module.

Source list per Austin's research doc (NEWS BROADWAY.pages):
  RSS-first, in priority order:
    1. Playbill         — playbill.com/article/playbill-rss-feeds (News)
    2. Broadway News    — broadwaynews.com/rss
    3. Broadway.com     — broadway.com/feeds/buzz/latest
    4. Vulture Theater  — vulture.com/theater/feed/
    5. Hollywood Reporter Theater — hollywoodreporter.com/c/theater/feed/
  HTML scrape (Tuesday cadence):
    6. Broadway League weekly grosses — broadwayleague.com/research/grosses-broadway-nyc/

Skipped tonight (per scope/credentials):
  - NY Times (paywall, no public RSS for theater)
  - Deadline (no native theater RSS — needs custom HTML scrape)
  - Variety (paywall on Pro content)
  - IBDB (archival, not news)

Output: data/news_feed.json — flat list of items, deduplicated, ranked by recency.
Used by web/index.html to render the "Broadway News" home-page section.

Run:
    uv run --with feedparser --with requests --with beautifulsoup4 \
        python scrapers/news_aggregator.py [--max-per-source N] [--no-grosses]
"""
from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
OUT_PATH = PROJECT_ROOT / "web" / "data" / "news_feed.json"

NEWS_SOURCES = [
    # Confirmed live as of 2026-04-27 — Vulture (404) + THR theater feed (empty)
    # were dropped and replaced with Variety + OnStage Blog + WhatsOnStage.
    {"name": "Playbill",          "rss": "https://www.playbill.com/rss/news",          "weight": 1.0,  "tier": "official"},
    {"name": "Broadway News",     "rss": "https://broadwaynews.com/feed/",             "weight": 1.0,  "tier": "independent"},
    {"name": "Broadway.com",      "rss": "https://www.broadway.com/feeds/buzz/latest", "weight": 0.85, "tier": "official"},
    {"name": "Variety",           "rss": "https://variety.com/v/legit/feed/",          "weight": 0.95, "tier": "trade"},
    {"name": "Theatermania",      "rss": "https://www.theatermania.com/news/rss",      "weight": 0.85, "tier": "criticism"},
    {"name": "OnStage Blog",      "rss": "https://www.onstageblog.com/onstage-blog-news?format=rss", "weight": 0.7,  "tier": "independent"},
    {"name": "WhatsOnStage",      "rss": "https://www.whatsonstage.com/news/rss/",     "weight": 0.7,  "tier": "international"},
]

USER_AGENT = "SlaybillNewsBot/1.0 (+https://slaybill.local)"
HEADERS = {"User-Agent": USER_AGENT}


def _item_id(link: str, title: str) -> str:
    base = (urlparse(link).netloc + (urlparse(link).path or "") + title).lower()
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:14]


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "")
    s = html_lib.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def fetch_rss(source: dict, limit: int = 25) -> list[dict]:
    """Fetch and parse RSS feed from a news source.

    Args:
        source: Dict with 'name', 'rss', 'weight', 'tier' keys.
        limit: Max items to fetch (default 25).

    Returns:
        List of normalized news item dicts with title, link, published, etc.
    """
    import feedparser
    parsed = feedparser.parse(source["rss"], request_headers=HEADERS)
    items = []
    for entry in (parsed.entries or [])[:limit]:
        title = (entry.get("title") or "").strip()
        link = entry.get("link") or ""
        if not (title and link):
            continue
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        ts = (
            datetime.fromtimestamp(time.mktime(published), tz=timezone.utc).isoformat()
            if published else None
        )
        summary = _strip_html(entry.get("summary") or entry.get("description") or "")[:400]
        items.append({
            "id": _item_id(link, title),
            "source": source["name"],
            "tier": source["tier"],
            "weight": source["weight"],
            "title": title,
            "link": link,
            "published": ts,
            "summary": summary,
        })
    return items


def fetch_grosses() -> dict | None:
    """Pull the Broadway League weekly grosses landing page; extract the
    week-ending date + headline aggregate. Lightweight — full per-show parse
    happens in scrapers/playbill_grosses.py separately."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return None
    try:
        r = requests.get(
            "https://www.broadwayleague.com/research/grosses-broadway-nyc/",
            headers=HEADERS, timeout=15,
        )
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        # Heuristic: look for "Week ending" text in the body.
        text = soup.get_text(" ", strip=True)
        m = re.search(r"[Ww]eek\s+[Ee]nding[^,]*,?\s+(\w+\s+\d+,\s+\d{4})", text)
        week_ending = m.group(1) if m else None
        return {
            "id": _item_id("broadwayleague-grosses", week_ending or "weekly"),
            "source": "Broadway League",
            "tier": "official",
            "weight": 1.0,
            "title": f"Weekly grosses — week ending {week_ending}" if week_ending else "Weekly Broadway grosses",
            "link": "https://www.broadwayleague.com/research/grosses-broadway-nyc/",
            "published": datetime.now(timezone.utc).isoformat(),
            "summary": "Official weekly box office report from the Broadway League. Updated every Tuesday.",
        }
    except Exception:
        return None


def deduplicate(items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for it in items:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        out.append(it)
    return out


def rank(items: list[dict]) -> list[dict]:
    # Most recent first; missing dates sink to the bottom.
    def key(it):
        return (it.get("published") or "", it["weight"])
    return sorted(items, key=key, reverse=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-per-source", type=int, default=20)
    ap.add_argument("--no-grosses", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    all_items: list[dict] = []
    for source in NEWS_SOURCES:
        try:
            items = fetch_rss(source, limit=args.max_per_source)
            all_items.extend(items)
            if args.verbose:
                print(f"  {source['name']:24} {len(items):3} items")
        except Exception as e:
            print(f"  {source['name']:24} FAILED: {e}", file=sys.stderr)

    if not args.no_grosses:
        grosses = fetch_grosses()
        if grosses:
            all_items.append(grosses)
            if args.verbose:
                print(f"  {'Broadway League':24}   1 item")

    items = rank(deduplicate(all_items))
    payload = {
        "_doc": "Auto-generated by news_aggregator.py. RSS-aggregated Broadway news, ranked recency-desc.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "items": items,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    tmp.replace(OUT_PATH)
    print(f"\nwrote {OUT_PATH.relative_to(PROJECT_ROOT)} — {len(items)} items")


if __name__ == "__main__":
    main()
