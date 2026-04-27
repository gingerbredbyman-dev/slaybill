"""
SLAYBILL — Broadway gossip + rumors module.

Source list per Austin's research doc (Broadway Gossip.pages):
  PRIMARY:
    1. BroadwayWorld Forum — Rumors/Whispers thread (HTML)
    2. NY Post Broadway section — author filter "Johnny Oleksinski" + tip phrases (SKIPPED tonight, paywall + selector flake)
    3. Page Six theater (SKIPPED — not RSS-friendly)
  SECONDARY:
    4. Broadway Journal Substack RSS — Philip Boroff (mark VERIFIED EXCLUSIVE if "EXCLUSIVE" in title)
    5. r/Broadway new posts JSON — keyword filter
    6. Theatr Insiders Substack RSS
  TERTIARY:
    7. Talkin' Broadway / All That Chat (SKIPPED — non-RSS, html-flake)
    8. OnStage Blog Broadway category (HTML — added)
    9. BroadwayStars meta-aggregator (SKIPPED — already aggregates above)
   10. TheaterMania news (HTML)
  SOCIAL:
    11-13. SKIPPED per Austin: @sweatyoracle, @ashleyhufford TikTok, IG (no public scrape paths)

Confidence tiering per his rules:
  - Verified Exclusive: any item from Broadway Journal (Boroff has the byline weight)
  - Confirmed-Adjacent: same story matched in 2+ sources (within 48h, fuzzy title match)
  - Unverified Rumor: single-source, especially BWW Forum or Reddit only

Output: data/gossip_feed.json — flat list, deduplicated, confidence-tagged.

Run:
    uv run --with feedparser --with requests --with beautifulsoup4 \
        python scrapers/gossip_aggregator.py [--max-per-source N]
"""
from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
OUT_PATH = PROJECT_ROOT / "web" / "data" / "gossip_feed.json"

USER_AGENT = "SlaybillGossipBot/1.0 (+https://slaybill.local)"
HEADERS = {"User-Agent": USER_AGENT}

GOSSIP_KEYWORDS = [
    "rumor", "transfer", "closing", "cancelled", "exclusive", "tea",
    "heard", "sources", "unannounced", "scandal", "casting",
]

# Substack + RSS sources
RSS_SOURCES = [
    {"name": "Broadway Journal", "url": "https://broadwayjournal.com/feed",     "tier_default": "verified_exclusive", "weight": 1.0, "exclusive_phrase": "EXCLUSIVE"},
    {"name": "Theatr Insiders",  "url": "https://theatr.substack.com/feed",     "tier_default": "unverified",         "weight": 0.7},
    {"name": "TheaterMania",     "url": "https://www.theatermania.com/news/feed/", "tier_default": "unverified",      "weight": 0.6},
]


def _item_id(link: str, title: str) -> str:
    base = (urlparse(link).netloc + (urlparse(link).path or "") + title).lower()
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:14]


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "")
    s = html_lib.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _normalize_title(t: str) -> str:
    t = re.sub(r"[^\w\s]", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def fetch_rss(source: dict, limit: int = 25) -> list[dict]:
    import feedparser
    parsed = feedparser.parse(source["url"], request_headers=HEADERS)
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
        tier = source["tier_default"]
        # Boroff's "EXCLUSIVE" headlines bump to verified_exclusive (already default for him)
        if source.get("exclusive_phrase") and source["exclusive_phrase"] in title.upper():
            tier = "verified_exclusive"
        items.append({
            "id": _item_id(link, title),
            "source": source["name"],
            "tier": tier,
            "weight": source["weight"],
            "title": title,
            "link": link,
            "published": ts,
            "summary": summary,
            "is_gossip_keyword": any(kw in (title + " " + summary).lower() for kw in GOSSIP_KEYWORDS),
        })
    return items


def fetch_reddit_broadway(limit: int = 30) -> list[dict]:
    """Public Reddit JSON — no PRAW creds needed for /new.json."""
    try:
        import requests
    except ImportError:
        return []
    try:
        r = requests.get(
            "https://www.reddit.com/r/Broadway/new.json",
            headers={**HEADERS, "Accept": "application/json"},
            params={"limit": limit},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception:
        return []
    items = []
    for child in (data.get("data", {}).get("children") or []):
        post = child.get("data") or {}
        title = (post.get("title") or "").strip()
        url = post.get("url_overridden_by_dest") or post.get("url") or ""
        permalink = "https://reddit.com" + (post.get("permalink") or "")
        if not title:
            continue
        body = (post.get("selftext") or "")[:400]
        ts = post.get("created_utc")
        published = (
            datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            if ts else None
        )
        text = (title + " " + body).lower()
        # Only keep posts with at least one gossip keyword.
        matched = [kw for kw in GOSSIP_KEYWORDS if kw in text]
        if not matched:
            continue
        items.append({
            "id": _item_id(permalink, title),
            "source": "r/Broadway",
            "tier": "unverified",
            "weight": 0.5,
            "title": title,
            "link": permalink,
            "published": published,
            "summary": _strip_html(body),
            "matched_keywords": matched,
            "score_upvotes": post.get("score") or 0,
            "is_gossip_keyword": True,
        })
    return items


def fetch_bww_forum(limit: int = 25) -> list[dict]:
    """BroadwayWorld Forum — Broadway Rumors/Whispers thread index. HTML."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return []
    try:
        r = requests.get(
            "https://forum.broadwayworld.com/category-page.php?id=1477",
            headers=HEADERS, timeout=15,
        )
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception:
        return []
    items: list[dict] = []
    # BWW thread links typically look like /thread/<slug>-<id>
    for a in soup.select("a[href*='/thread/']")[:limit * 2]:
        href = a.get("href") or ""
        title = (a.get_text() or "").strip()
        if not title or len(title) < 8:
            continue
        link = href if href.startswith("http") else "https://forum.broadwayworld.com" + href
        if any(it["link"] == link for it in items):
            continue
        items.append({
            "id": _item_id(link, title),
            "source": "BWW Forum",
            "tier": "unverified",
            "weight": 0.4,
            "title": title,
            "link": link,
            "published": None,
            "summary": "",
            "is_gossip_keyword": any(kw in title.lower() for kw in GOSSIP_KEYWORDS),
        })
        if len(items) >= limit:
            break
    return items


def cross_confirm(items: list[dict]) -> list[dict]:
    """Promote tier when a story title appears in 2+ different sources within 48h.
    Uses fuzzy title matching to bridge slight headline rephrasings."""
    by_source = defaultdict(list)
    for it in items:
        by_source[it["source"]].append(it)
    sources = list(by_source.keys())
    confirmed_ids: set[str] = set()
    for i in range(len(sources)):
        for j in range(i + 1, len(sources)):
            for a in by_source[sources[i]]:
                for b in by_source[sources[j]]:
                    if SequenceMatcher(None, _normalize_title(a["title"]), _normalize_title(b["title"])).ratio() > 0.55:
                        confirmed_ids.add(a["id"])
                        confirmed_ids.add(b["id"])
    for it in items:
        if it["tier"] == "verified_exclusive":
            continue  # already top-tier
        if it["id"] in confirmed_ids:
            it["tier"] = "confirmed_adjacent"
    return items


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
    tier_rank = {"verified_exclusive": 3, "confirmed_adjacent": 2, "unverified": 1}
    def key(it):
        return (
            tier_rank.get(it["tier"], 0),
            it.get("published") or "",
            it["weight"],
        )
    return sorted(items, key=key, reverse=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-per-source", type=int, default=20)
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    all_items: list[dict] = []
    for source in RSS_SOURCES:
        try:
            items = fetch_rss(source, limit=args.max_per_source)
            all_items.extend(items)
            if args.verbose:
                print(f"  {source['name']:24} {len(items):3} items")
        except Exception as e:
            print(f"  {source['name']:24} FAILED: {e}", file=sys.stderr)

    try:
        reddit = fetch_reddit_broadway(limit=args.max_per_source)
        all_items.extend(reddit)
        if args.verbose:
            print(f"  {'r/Broadway':24} {len(reddit):3} items")
    except Exception as e:
        print(f"  r/Broadway              FAILED: {e}", file=sys.stderr)

    try:
        bww = fetch_bww_forum(limit=args.max_per_source)
        all_items.extend(bww)
        if args.verbose:
            print(f"  {'BWW Forum':24} {len(bww):3} items")
    except Exception as e:
        print(f"  BWW Forum               FAILED: {e}", file=sys.stderr)

    items = rank(cross_confirm(deduplicate(all_items)))
    tier_counts = defaultdict(int)
    for it in items:
        tier_counts[it["tier"]] += 1

    payload = {
        "_doc": "Auto-generated by gossip_aggregator.py. Tiered: verified_exclusive | confirmed_adjacent | unverified.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "tier_counts": dict(tier_counts),
        "items": items,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    tmp.replace(OUT_PATH)
    print(f"\nwrote {OUT_PATH.relative_to(PROJECT_ROOT)} — {len(items)} items "
          f"({tier_counts.get('verified_exclusive',0)} exclusive, "
          f"{tier_counts.get('confirmed_adjacent',0)} adjacent, "
          f"{tier_counts.get('unverified',0)} unverified)")


if __name__ == "__main__":
    main()
