"""
SLAYBILL — emit shows_live.json from the curated shows.json source of truth.

v1 strategy: shows.json is authoritative. This builder normalizes it into the
format the front-end expects (split by tier + status bucket, computed rank
fields, safe defaults for missing metrics).

v1.5 will layer DB grosses + news-event overlays on top (date refresh + live
capacity_pct from the latest grosses row).

Run:
    python builders/build_live_shows.py

Output shape:
    {
      "_doc": "...",
      "generated_at": "...",
      "buckets": {
        "coming_soon":   [show, ...],   # previews start within 42 days
        "in_previews":   [show, ...],   # currently previewing
        "live":          [show, ...],   # officially opened
        "closed":        [show, ...]    # archived, shown only on archive page
      },
      "off_broadway":    [show, ...]    # ALL off-Broadway regardless of bucket
    }

Rationale for splitting off-Broadway from the buckets: the UI renders it as a
separate horizontal-scroll row, not inside the bucket stacks. Easier to emit
once here than to filter client-side.
"""

import json
import re
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
SHOWS_JSON = PROJECT_ROOT / "data" / "shows.json"
# Write the generated JSON into web/data/ so the static server can reach it
# via a sibling path (fetch('data/shows_live.json') from web/index.html).
OUT_PATH = PROJECT_ROOT / "web" / "data" / "shows_live.json"
NEWS_FEED = PROJECT_ROOT / "web" / "data" / "news_feed.json"
POSTERS_DIR = PROJECT_ROOT / "web" / "shows" / "posters"
POSTER_EXTS = (".jpg", ".jpeg", ".png", ".webp")

COMING_SOON_WINDOW_DAYS = 42  # 6 weeks

VALID_FIRM_ROLES = {
    "lead_agency", "press", "digital", "creative",
    "oo_h", "social", "pr", "media_buy",
}

ROLE_DISPLAY = {
    "lead_agency": "Lead Agency",
    "press":       "Press",
    "digital":     "Digital",
    "creative":    "Creative",
    "oo_h":        "OOH",
    "social":      "Social",
    "pr":          "PR",
    "media_buy":   "Media Buy",
}


def _normalize_firms(raw):
    """Filter to valid roles, enforce single is_primary, attach role_display.
    Returns (firms_list, primary_firm_or_none)."""
    out = []
    primary = None
    for entry in (raw or []):
        firm = (entry.get("firm") or "").strip()
        role = entry.get("role")
        if not firm or role not in VALID_FIRM_ROLES:
            continue
        is_primary = bool(entry.get("is_primary")) and primary is None
        item = {
            "firm": firm,
            "role": role,
            "role_display": ROLE_DISPLAY[role],
            "is_primary": is_primary,
        }
        if is_primary:
            primary = item
        out.append(item)
    # Primary first, then alpha by firm name.
    out.sort(key=lambda f: (not f["is_primary"], f["firm"].lower()))
    return out, primary


_TITLE_NOISE = re.compile(r"[^a-z0-9 ]+")


def _norm_title(t: str) -> str:
    return _TITLE_NOISE.sub(" ", (t or "").lower()).strip()


def _load_news_index() -> list[dict]:
    """Best-effort load of news_feed.json. Empty list if missing."""
    if not NEWS_FEED.exists():
        return []
    try:
        payload = json.loads(NEWS_FEED.read_text())
    except json.JSONDecodeError:
        return []
    return payload.get("items") or []


def resolve_source_url(show: dict, news_items: list[dict]) -> str | None:
    """For a show without confirmed grosses (coming_soon / in_previews), find
    the best news article that mentions the show. Falls back to ticket_links.official
    or a Playbill production URL guess. Returns None if nothing reasonable found."""
    title_norm = _norm_title(show.get("title", ""))
    if not title_norm:
        return show.get("ticket_links", {}).get("official")

    # Try a substring match against news headlines.
    best = None
    title_words = [w for w in title_norm.split() if len(w) > 2]
    for item in news_items:
        head = _norm_title(item.get("title", ""))
        if title_norm in head:
            return item.get("link")  # exact substring beats partial
        # Word-overlap heuristic — at least 2 distinctive words match
        matches = sum(1 for w in title_words if w in head)
        if matches >= max(2, len(title_words) // 2):
            if not best or item.get("published", "") > (best.get("published") or ""):
                best = item
    if best:
        return best.get("link")

    # Fallback: official ticket link if any.
    official = (show.get("ticket_links") or {}).get("official")
    if official:
        return official
    # Last resort: Playbill search URL — Austin can curate later.
    slug_q = (show.get("slug") or "").replace("-", "+")
    if slug_q:
        return f"https://playbill.com/searchpage/search?q={slug_q}"
    return None


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def derive_status(show: dict, today: date) -> str:
    """If shows.json already has a status, trust it. Otherwise derive from dates."""
    if show.get("status"):
        return show["status"]
    closing = _parse_date(show.get("closing_date"))
    opening = _parse_date(show.get("opening_date"))
    first_preview = _parse_date(show.get("first_preview_date"))

    if closing and closing < today:
        return "closed"
    if opening and opening <= today:
        if not closing or closing >= today:
            return "live"
    if first_preview and first_preview <= today:
        if not opening or today < opening:
            return "in_previews"
    if first_preview and today < first_preview <= today + timedelta(days=COMING_SOON_WINDOW_DAYS):
        return "coming_soon"
    return "announced"


def normalize(show: dict, today: date, news_items: list[dict] | None = None) -> dict:
    """Flatten into the exact contract the front-end expects. Keeping the
    in-memory JS simple means all fields have the SAME name across every
    show, and always present (null when unknown)."""
    slug = show["slug"]
    poster_path = next(
        (
            f"shows/posters/{slug}{ext}"
            for ext in POSTER_EXTS
            if (POSTERS_DIR / f"{slug}{ext}").exists()
        ),
        None,
    )

    firms, primary_firm = _normalize_firms(show.get("marketing_firms"))

    return {
        "slug": slug,
        "title": show["title"],
        "subtitle": show.get("subtitle", ""),
        "tier": show.get("tier", "broadway"),
        "category": show.get("category", "unknown"),
        "status": derive_status(show, today),
        "theatre": show.get("theatre", ""),
        "theatre_capacity": show.get("theatre_capacity"),
        "first_preview_date": show.get("first_preview_date"),
        "opening_date": show.get("opening_date"),
        "closing_date": show.get("closing_date"),
        "synopsis": show.get("synopsis", ""),
        "cast": show.get("cast", []),
        "creatives": show.get("creatives", []),
        "producers": show.get("producers", []),
        "avg_ticket_usd": show.get("avg_ticket_usd"),
        "capacity_pct": show.get("capacity_pct"),
        "weekly_gross_usd": show.get("weekly_gross_usd"),
        "critic_score": show.get("critic_score"),
        "sentiment_score": show.get("sentiment_score"),
        "composite_score": show.get("composite_score"),
        "grade": show.get("grade"),
        "score_label": show.get("score_label"),
        "critic_sources_used": show.get("critic_sources_used", []),
        "audience_sources_used": show.get("audience_sources_used", []),
        "scores_meta": show.get("scores_meta"),
        "flags": show.get("flags") or {"gross_warning": False, "sentiment_warning": False},
        "palette": show.get("palette", ["#333333", "#666666", "#999999", "#cccccc", "#ffffff"]),
        "poster_path": poster_path,
        "ticket_links": show.get("ticket_links", {}),
        "marketing_firms": firms,
        "primary_firm": primary_firm,
        "source_url": resolve_source_url(show, news_items or []),
    }


def build() -> dict:
    data = json.loads(SHOWS_JSON.read_text())
    today = date.today()
    news_items = _load_news_index()

    buckets: dict[str, list[dict]] = {
        "coming_soon": [],
        "in_previews": [],
        "live": [],
        "closed": [],
    }
    off_broadway: list[dict] = []

    for show in data["shows"]:
        normalized = normalize(show, today, news_items)
        if normalized["tier"] == "off_broadway":
            off_broadway.append(normalized)
            continue
        bucket = normalized["status"]
        if bucket == "closed_early" or bucket == "cancelled":
            bucket = "closed"
        if bucket in buckets:
            buckets[bucket].append(normalized)
        # announced shows are omitted from main page; they'd live on an
        # upcoming-season view later.

    # Sort each Broadway bucket by weekly gross desc (nulls last).
    def sort_key(s):
        return (-(s["weekly_gross_usd"] or 0), s["title"].lower())

    for key in buckets:
        buckets[key].sort(key=sort_key)
    off_broadway.sort(key=lambda s: (-(s["weekly_gross_usd"] or 0), s["title"].lower()))

    out = {
        "_doc": (
            "Auto-generated by build_live_shows.py from shows.json. "
            "buckets[*] lists Broadway shows grouped by status; off_broadway "
            "is flat regardless of bucket. Do NOT edit by hand — edit "
            "shows.json and re-run the builder."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "buckets": buckets,
        "off_broadway": off_broadway,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    data = build()
    counts = {k: len(v) for k, v in data["buckets"].items()}
    counts["off_broadway"] = len(data["off_broadway"])
    print(f"Wrote {OUT_PATH.name}")
    for k, v in counts.items():
        print(f"  {k:14} {v}")
