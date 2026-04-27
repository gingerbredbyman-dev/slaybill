"""
Broadway Intelligence System — Master Scraper
Covers all 3 modules: Proven News, Gossip/Tea, Pond Hopper (West End)
Free tier uses: feedparser, BeautifulSoup, PRAW (Reddit)
Pro tier uses: ScraperAPI, Apify, OpenAI GPT-4o-mini for NLP classification

Author: Austin Sprague / Claude
"""

import feedparser
import requests
from bs4 import BeautifulSoup
import praw
import json
import time
import re
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import Optional
import hashlib

# ─── CONFIG ────────────────────────────────────────────────────────────────────

# Reddit API (free personal tier — 100 QPM)
REDDIT_CLIENT_ID     = "YOUR_REDDIT_CLIENT_ID"
REDDIT_CLIENT_SECRET = "YOUR_REDDIT_CLIENT_SECRET"
REDDIT_USER_AGENT    = "broadway-intel-app/1.0 by /u/yourusername"

# [PRO] ScraperAPI key — $49/mo, 100k requests
SCRAPER_API_KEY = "YOUR_SCRAPERAPI_KEY"  # Leave empty for free tier

# [PRO] OpenAI key — for NLP classification & summarization
OPENAI_API_KEY  = "YOUR_OPENAI_API_KEY"  # Leave empty for free tier

USE_PRO = bool(SCRAPER_API_KEY and OPENAI_API_KEY)

# ─── DATA MODEL ────────────────────────────────────────────────────────────────

@dataclass
class BroadwayItem:
    id: str                          # SHA256 hash of url+title
    module: str                      # "proven" | "gossip" | "westend"
    tier: str                        # "Verified Exclusive" | "Confirmed-Adjacent" | "Unverified Rumor"
    headline: str
    summary: str
    source: str
    source_url: str
    scraped_at: str
    confidence: float                # 0.0–1.0
    tags: list = field(default_factory=list)  # show names, people extracted
    show_name: Optional[str] = None


def make_id(url: str, title: str) -> str:
    return hashlib.sha256(f"{url}{title}".encode()).hexdigest()[:16]


# ─── MODULE 1: PROVEN NEWS ─────────────────────────────────────────────────────
# Sources: Broadway Briefing, Broadway.com, Playbill, TheaterMania, OnStage Blog

PROVEN_RSS_FEEDS = [
    {
        "name": "Broadway News",
        "url": "https://www.broadwaynews.com/feed/",
        "tier": "Confirmed-Adjacent",
        "confidence": 0.88,
    },
    {
        "name": "Playbill",
        "url": "https://playbill.com/feed",
        "tier": "Confirmed-Adjacent",
        "confidence": 0.92,
    },
    {
        "name": "TheaterMania",
        "url": "https://www.theatermania.com/rss/news.xml",
        "tier": "Confirmed-Adjacent",
        "confidence": 0.85,
    },
    {
        "name": "OnStage Blog",
        "url": "https://www.onstageblog.com/feeds/posts/default",
        "tier": "Confirmed-Adjacent",
        "confidence": 0.80,
    },
    {
        "name": "BroadwayWorld",
        "url": "https://www.broadwayworld.com/rss/allnews.cfm",
        "tier": "Confirmed-Adjacent",
        "confidence": 0.78,
    },
]

PROVEN_SCRAPE_SOURCES = [
    {
        "name": "NY Post Broadway",
        "url": "https://nypost.com/theater/",
        "byline_filter": ["johnny oleksinski"],
        "phrase_triggers": ["i'm told", "sources say", "exclusively", "according to"],
        "tier": "Confirmed-Adjacent",
        "confidence": 0.87,
    },
    {
        "name": "Broadway Briefing",
        "url": "https://broadwaybriefing.com",
        "tier": "Verified Exclusive",
        "confidence": 0.93,
    },
]


def scrape_rss_feed(source: dict, module: str) -> list[BroadwayItem]:
    """Parse an RSS feed and return BroadwayItem list."""
    items = []
    try:
        feed = feedparser.parse(source["url"])
        for entry in feed.entries[:10]:
            title   = entry.get("title", "").strip()
            link    = entry.get("link", "")
            summary = BeautifulSoup(
                entry.get("summary", entry.get("description", "")), "html.parser"
            ).get_text()[:300].strip()

            item = BroadwayItem(
                id=make_id(link, title),
                module=module,
                tier=source["tier"],
                headline=title,
                summary=summary,
                source=source["name"],
                source_url=link,
                scraped_at=datetime.utcnow().isoformat(),
                confidence=source["confidence"],
            )
            items.append(item)
    except Exception as e:
        print(f"[RSS ERROR] {source['name']}: {e}")
    return items


def scrape_page(url: str, use_proxy: bool = False) -> Optional[BeautifulSoup]:
    """Fetch a page via requests or ScraperAPI proxy."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; broadway-intel/1.0)"}
    try:
        if use_proxy and SCRAPER_API_KEY:
            api_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}"
            r = requests.get(api_url, timeout=15)
        else:
            r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"[SCRAPE ERROR] {url}: {e}")
        return None


def scrape_nypost_broadway() -> list[BroadwayItem]:
    """Scrape NY Post theater section, flag gossip signal phrases."""
    items = []
    soup = scrape_page("https://nypost.com/theater/", use_proxy=USE_PRO)
    if not soup:
        return items

    articles = soup.select("article, .story, h3 a, h2 a")[:15]
    for tag in articles:
        a_tag = tag if tag.name == "a" else tag.find("a")
        if not a_tag:
            continue
        title = a_tag.get_text(strip=True)
        link  = a_tag.get("href", "")
        if not title or not link.startswith("http"):
            continue

        phrases = ["i'm told", "sources say", "exclusively", "according to sources"]
        tier = "Verified Exclusive" if any(p in title.lower() for p in phrases) else "Confirmed-Adjacent"

        items.append(BroadwayItem(
            id=make_id(link, title),
            module="proven",
            tier=tier,
            headline=title,
            summary="",
            source="NY Post Broadway",
            source_url=link,
            scraped_at=datetime.utcnow().isoformat(),
            confidence=0.87,
        ))
    return items


def fetch_broadway_journal() -> list[BroadwayItem]:
    """Scrape Broadway Journal (Substack) via RSS."""
    items = []
    feed = feedparser.parse("https://www.broadwayjournal.com/feed")
    for entry in feed.entries[:5]:
        title   = entry.get("title", "").strip()
        link    = entry.get("link", "")
        summary = BeautifulSoup(
            entry.get("summary", ""), "html.parser"
        ).get_text()[:300].strip()
        tier = "Verified Exclusive" if "exclusive" in title.lower() else "Confirmed-Adjacent"
        items.append(BroadwayItem(
            id=make_id(link, title),
            module="gossip",
            tier=tier,
            headline=title,
            summary=summary,
            source="Broadway Journal (Philip Boroff)",
            source_url=link,
            scraped_at=datetime.utcnow().isoformat(),
            confidence=0.95 if tier == "Verified Exclusive" else 0.88,
        ))
    return items


def run_proven_module() -> list[BroadwayItem]:
    """Collect all Proven: Today's Headlines items."""
    all_items = []
    for src in PROVEN_RSS_FEEDS:
        all_items.extend(scrape_rss_feed(src, "proven"))
        time.sleep(0.5)
    all_items.extend(scrape_nypost_broadway())
    return deduplicate(all_items)


# ─── MODULE 2: GOSSIP & TEA ────────────────────────────────────────────────────
# Sources: BWW Forum, r/Broadway, Broadway Journal, Theatr Insiders, Sweaty Oracle (TikTok titles)

GOSSIP_RSS_FEEDS = [
    {
        "name": "Theatr Insiders (Substack)",
        "url": "https://theatr.substack.com/feed",
        "tier": "Confirmed-Adjacent",
        "confidence": 0.82,
    },
    {
        "name": "notbroadway Substack",
        "url": "https://notbroadway.substack.com/feed",
        "tier": "Unverified Rumor",
        "confidence": 0.65,
    },
]

# BWW Forum rumor keywords
RUMOR_KEYWORDS = [
    "rumor", "rumour", "transfer", "closing", "cancel", "exclusive", "tea",
    "heard", "sources", "whisper", "unannounced", "drama", "fired", "replaced",
    "shutting", "shutdown", "trouble", "issues", "beef", "feud",
]


def scrape_bww_forum() -> list[BroadwayItem]:
    """Scrape BroadwayWorld Forum latest posts."""
    items = []
    url = "https://forum.broadwayworld.com/latest-posts.php"
    soup = scrape_page(url, use_proxy=USE_PRO)
    if not soup:
        return items

    rows = soup.select("tr, .thread-row, .message-row")[:30]
    for row in rows:
        a_tag = row.find("a", href=True)
        if not a_tag:
            continue
        title = a_tag.get_text(strip=True)
        link  = a_tag.get("href", "")
        if not link.startswith("http"):
            link = "https://forum.broadwayworld.com/" + link.lstrip("/")
        if not title:
            continue

        has_rumor = any(kw in title.lower() for kw in RUMOR_KEYWORDS)
        tier = "Unverified Rumor" if has_rumor else "Confirmed-Adjacent"

        items.append(BroadwayItem(
            id=make_id(link, title),
            module="gossip",
            tier=tier,
            headline=title,
            summary="",
            source="BroadwayWorld Forum",
            source_url=link,
            scraped_at=datetime.utcnow().isoformat(),
            confidence=0.55 if tier == "Unverified Rumor" else 0.72,
        ))
    return items


def scrape_reddit_broadway() -> list[BroadwayItem]:
    """Fetch r/Broadway new posts via PRAW (free 100 QPM)."""
    items = []
    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
            check_for_async=False,
        )
        sub = reddit.subreddit("Broadway")
        for post in sub.new(limit=40):
            title = post.title.strip()
            link  = f"https://www.reddit.com{post.permalink}"
            has_rumor = any(kw in title.lower() for kw in RUMOR_KEYWORDS)
            tier = "Unverified Rumor" if has_rumor else "Confirmed-Adjacent"
            items.append(BroadwayItem(
                id=make_id(link, title),
                module="gossip",
                tier=tier,
                headline=title,
                summary=post.selftext[:250].strip() if post.selftext else "",
                source="r/Broadway",
                source_url=link,
                scraped_at=datetime.utcnow().isoformat(),
                confidence=0.50 if tier == "Unverified Rumor" else 0.68,
            ))
    except Exception as e:
        print(f"[REDDIT ERROR]: {e}")
    return items


def run_gossip_module() -> list[BroadwayItem]:
    """Collect all Gossip & Tea items."""
    all_items = []
    for src in GOSSIP_RSS_FEEDS:
        all_items.extend(scrape_rss_feed(src, "gossip"))
        time.sleep(0.5)
    all_items.extend(fetch_broadway_journal())
    all_items.extend(scrape_bww_forum())
    all_items.extend(scrape_reddit_broadway())
    return deduplicate(all_items)


# ─── MODULE 3: POND HOPPER (WEST END) ─────────────────────────────────────────
# Sources: The Stage, WhatsOnStage, TheatreFan.co.uk, r/westend, LondonTheatre.co.uk

WESTEND_RSS_FEEDS = [
    {
        "name": "The Stage",
        "url": "https://www.thestage.co.uk/rss",
        "tier": "Verified Exclusive",
        "confidence": 0.91,
    },
    {
        "name": "WhatsOnStage",
        "url": "https://www.whatsonstage.com/feeds/news/",
        "tier": "Confirmed-Adjacent",
        "confidence": 0.86,
    },
    {
        "name": "LondonTheatre.co.uk",
        "url": "https://www.londontheatre.co.uk/feed",
        "tier": "Confirmed-Adjacent",
        "confidence": 0.82,
    },
    {
        "name": "WestEndTheatre.com",
        "url": "https://www.westendtheatre.com/feed/",
        "tier": "Confirmed-Adjacent",
        "confidence": 0.80,
    },
]

WESTEND_SCRAPE_SOURCES = [
    {
        "name": "TheatreFan Rumours",
        "url": "https://theatrefan.co.uk/category/rumours/",
        "tier": "Unverified Rumor",
        "confidence": 0.63,
    },
]


def scrape_theatrefan_rumours() -> list[BroadwayItem]:
    """Scrape TheatreFan.co.uk rumour category — the West End's BWW Forum."""
    items = []
    soup = scrape_page("https://theatrefan.co.uk/category/rumours/", use_proxy=USE_PRO)
    if not soup:
        return items

    for a_tag in soup.select("h2 a, h3 a, article a")[:15]:
        title = a_tag.get_text(strip=True)
        link  = a_tag.get("href", "")
        if not title or not link.startswith("http"):
            continue
        items.append(BroadwayItem(
            id=make_id(link, title),
            module="westend",
            tier="Unverified Rumor",
            headline=title,
            summary="",
            source="TheatreFan.co.uk",
            source_url=link,
            scraped_at=datetime.utcnow().isoformat(),
            confidence=0.63,
        ))
    return items


def scrape_reddit_westend() -> list[BroadwayItem]:
    """Fetch r/westend posts via PRAW."""
    items = []
    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
            check_for_async=False,
        )
        sub = reddit.subreddit("westend")
        for post in sub.new(limit=25):
            title = post.title.strip()
            link  = f"https://www.reddit.com{post.permalink}"
            has_rumor = any(kw in title.lower() for kw in RUMOR_KEYWORDS)
            tier = "Unverified Rumor" if has_rumor else "Confirmed-Adjacent"
            items.append(BroadwayItem(
                id=make_id(link, title),
                module="westend",
                tier=tier,
                headline=title,
                summary=post.selftext[:250].strip() if post.selftext else "",
                source="r/westend",
                source_url=link,
                scraped_at=datetime.utcnow().isoformat(),
                confidence=0.50 if tier == "Unverified Rumor" else 0.68,
            ))
    except Exception as e:
        print(f"[REDDIT WESTEND ERROR]: {e}")
    return items


def run_westend_module() -> list[BroadwayItem]:
    """Collect all West End (Pond Hopper) items."""
    all_items = []
    for src in WESTEND_RSS_FEEDS:
        all_items.extend(scrape_rss_feed(src, "westend"))
        time.sleep(0.5)
    all_items.extend(scrape_theatrefan_rumours())
    all_items.extend(scrape_reddit_westend())
    return deduplicate(all_items)


# ─── SHOW SCORE ENGINE ─────────────────────────────────────────────────────────

CRITIC_SOURCES = [
    # (source_name, weight)
    ("NY Times",         0.20),
    ("Variety",          0.14),
    ("Hollywood Reporter",0.10),
    ("NY Post",          0.10),
    ("The Guardian",     0.10),
    ("Time Out NY",      0.08),
    ("TheaterMania",     0.08),
    ("BroadwayWorld",    0.06),
    ("Vulture",          0.07),
    ("Associated Press", 0.07),
]

AUDIENCE_SOURCES = [
    # (source_name, weight, scrape_url_template)
    ("Show-Score",          0.35, "https://www.show-score.com/search?q={show_slug}"),
    ("Broadway Scorecard",  0.25, "https://broadwayscorecard.com/shows/{show_slug}"),
    ("Broadway.com",        0.20, "https://www.broadway.com/shows/{show_slug}/"),
    ("Mezzanine",           0.12, None),  # no public API — manual add
    ("Reddit Sentiment",    0.08, "https://www.reddit.com/r/Broadway/search.json?q={show_name}&sort=top"),
]


def compute_show_score(
    show_name: str,
    critic_scores: dict[str, float],     # {"NY Times": 85, "Variety": 72, ...}
    audience_scores: dict[str, float],   # {"Show-Score": 91, "Broadway.com": 88, ...}
    critic_weight: float = 0.55,
    audience_weight: float = 0.45,
) -> dict:
    """
    Compute a 0–100 composite score, Metacritic-style.

    critic_weight: how much professional critics count (default 55%)
    audience_weight: how much audience ratings count (default 45%)

    Returns a dict with: composite_score, critic_score, audience_score, grade, label
    """
    # Weighted critic score
    total_crit_weight = 0.0
    weighted_crit_sum = 0.0
    for src, weight in CRITIC_SOURCES:
        if src in critic_scores:
            weighted_crit_sum  += critic_scores[src] * weight
            total_crit_weight  += weight
    critic_score = (weighted_crit_sum / total_crit_weight) if total_crit_weight else None

    # Weighted audience score
    total_aud_weight = 0.0
    weighted_aud_sum = 0.0
    for src, weight, _ in AUDIENCE_SOURCES:
        if src in audience_scores:
            weighted_aud_sum  += audience_scores[src] * weight
            total_aud_weight  += weight
    audience_score = (weighted_aud_sum / total_aud_weight) if total_aud_weight else None

    # Composite
    if critic_score and audience_score:
        composite = round(critic_score * critic_weight + audience_score * audience_weight, 1)
    elif critic_score:
        composite = round(critic_score, 1)
    elif audience_score:
        composite = round(audience_score, 1)
    else:
        composite = None

    # Grade + label
    def grade(s):
        if s is None: return "N/A", "Not enough data"
        if s >= 91: return "A+", "Must See"
        if s >= 85: return "A",  "Excellent"
        if s >= 80: return "A-", "Great"
        if s >= 75: return "B+", "Very Good"
        if s >= 70: return "B",  "Good"
        if s >= 65: return "B-", "Above Average"
        if s >= 55: return "C+", "Mixed-Positive"
        if s >= 45: return "C",  "Mixed"
        if s >= 35: return "D",  "Weak"
        return "F", "Skip It"

    comp_grade, comp_label = grade(composite)

    return {
        "show_name":      show_name,
        "composite_score": composite,
        "critic_score":    round(critic_score,   1) if critic_score   else None,
        "audience_score":  round(audience_score, 1) if audience_score else None,
        "grade":           comp_grade,
        "label":           comp_label,
        "critic_sources_used":   list(critic_scores.keys()),
        "audience_sources_used": list(audience_scores.keys()),
    }


# ─── DEDUPLICATION ─────────────────────────────────────────────────────────────

def deduplicate(items: list[BroadwayItem]) -> list[BroadwayItem]:
    """Remove duplicate items by ID within 48-hour window."""
    seen = set()
    unique = []
    for item in items:
        if item.id not in seen:
            seen.add(item.id)
            unique.append(item)
    return unique


# ─── PRO: GPT-4o-mini CLASSIFIER ───────────────────────────────────────────────

def classify_and_summarize_pro(item: BroadwayItem) -> BroadwayItem:
    """
    [PRO TIER] Use GPT-4o-mini to:
    - Rewrite headline in gossip-forward style
    - Generate a punchy 2-3 sentence summary
    - Extract show name / people mentioned
    - Upgrade/downgrade tier confidence
    """
    if not OPENAI_API_KEY:
        return item
    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        prompt = f"""You are a Broadway news editor. Given this headline and raw summary, return JSON with:
- "headline": rewritten in punchy, gossip-forward style (max 15 words)
- "summary": 2-3 sentence explanation of what's happening and why it matters
- "show_name": the Broadway/West End show name if mentioned, else null
- "tags": list of key people/shows mentioned

Headline: {item.headline}
Summary: {item.summary}
Source: {item.source}

Respond ONLY with valid JSON."""
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.4,
        )
        data = json.loads(resp.choices[0].message.content)
        item.headline  = data.get("headline", item.headline)
        item.summary   = data.get("summary",  item.summary)
        item.show_name = data.get("show_name")
        item.tags      = data.get("tags", [])
    except Exception as e:
        print(f"[GPT ERROR] {e}")
    return item


# ─── MASTER RUN ────────────────────────────────────────────────────────────────

def run_all_modules() -> dict:
    """Run all three modules and return a combined payload."""
    print("🎭 Running Broadway Intelligence System...")

    proven  = run_proven_module()
    gossip  = run_gossip_module()
    westend = run_westend_module()

    if USE_PRO:
        print("⚡ PRO mode: enriching with GPT-4o-mini...")
        proven  = [classify_and_summarize_pro(i) for i in proven[:20]]
        gossip  = [classify_and_summarize_pro(i) for i in gossip[:20]]
        westend = [classify_and_summarize_pro(i) for i in westend[:20]]

    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "mode": "pro" if USE_PRO else "free",
        "modules": {
            "proven":  [asdict(i) for i in proven],
            "gossip":  [asdict(i) for i in gossip],
            "westend": [asdict(i) for i in westend],
        },
        "counts": {
            "proven":  len(proven),
            "gossip":  len(gossip),
            "westend": len(westend),
        }
    }

    # Save to JSON output
    with open("broadway_intel_output.json", "w") as f:
        json.dump(payload, f, indent=2)
    print(f"✅ Done. Proven: {len(proven)} | Gossip: {len(gossip)} | West End: {len(westend)}")
    return payload


# ─── EXAMPLE: SCORE A SHOW ─────────────────────────────────────────────────────

if __name__ == "__main__":
    # Example: score a show
    score = compute_show_score(
        show_name="Suffs",
        critic_scores={
            "NY Times":           90,
            "Variety":            88,
            "Hollywood Reporter": 85,
            "NY Post":            78,
            "Time Out NY":        92,
        },
        audience_scores={
            "Show-Score":          87,
            "Broadway Scorecard":  89,
            "Broadway.com":        91,
        }
    )
    print("\n🎭 SHOW SCORE RESULT:")
    print(json.dumps(score, indent=2))

    # Run all scraper modules
    # run_all_modules()
