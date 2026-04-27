"""
SLAYBILL — Tier 2 detail page renderer.

Reads data/shows.json, renders web/shows/<slug>.html from
web/shows/_template.html for each show. Includes:
  * palette extraction from posters/<slug>.jpg (via Pillow) if present,
    else uses the palette from shows.json
  * derived ink/surface tones (auto light-on-dark vs dark-on-light)
  * cast / creatives / producers as <li> rows
  * money metrics (weekly gross, avg ticket, capacity) with pending
    placeholders when the source data is null
  * ticket links table: one <tr> per configured vendor
  * critic + audience sentiment with "coming soon" tooltip when null
  * status pill mirroring the bucket color

Run:
    uv run --with Pillow python builders/build_show_pages.py
"""

import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
SHOWS_JSON = PROJECT_ROOT / "data" / "shows.json"
TEMPLATE = PROJECT_ROOT / "web" / "shows" / "_template.html"
SHOWS_DIR = PROJECT_ROOT / "web" / "shows"
POSTERS_DIR = SHOWS_DIR / "posters"
SCORE_CACHE_DIR = PROJECT_ROOT / "scrapers" / "cache"

POSTER_EXTS = (".jpg", ".jpeg", ".png", ".webp")

STATUS_CHIP_TEXT = {
    "coming_soon": "Coming Soon",
    "in_previews": "In Previews",
    "live":        "Live",
    "closed":      "Closed",
    "closed_early": "Closed",
    "cancelled":   "Cancelled",
    "announced":   "Announced",
}

VENDOR_DISPLAY = {
    "telecharge":      "Telecharge",
    "todaytix":        "TodayTix",
    "tkts":            "TKTS (day-of)",
    "seatgeek":        "SeatGeek",
    "broadway_direct": "Broadway Direct",
    "official":        "Official Site",
}

VENDOR_BLURB = {
    "telecharge":      "Full-price official box office",
    "todaytix":        "Mobile discounts + lottery",
    "tkts":            "Same-day half-price booth",
    "seatgeek":        "Resale marketplace",
    "broadway_direct": "Official Broadway Direct",
    "official":        "Show's official site",
}

VALID_FIRM_ROLES = {
    "lead_agency", "press", "digital", "creative",
    "oo_h", "social", "pr", "media_buy",
}

FIRM_ROLE_DISPLAY = {
    "lead_agency": "Lead Agency",
    "press":       "Press",
    "digital":     "Digital",
    "creative":    "Creative",
    "oo_h":        "OOH",
    "social":      "Social",
    "pr":          "PR",
    "media_buy":   "Media Buy",
}


def _find_poster(slug: str) -> Path | None:
    for ext in POSTER_EXTS:
        p = POSTERS_DIR / f"{slug}{ext}"
        if p.exists():
            return p
    return None


def _hex(rgb): r, g, b = rgb; return f"#{r:02x}{g:02x}{b:02x}"


def _luminance(rgb):
    r, g, b = rgb
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def _parse_hex(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def extract_palette(poster: Path, k: int = 5):
    """Extract dominant color palette from a poster image using k-means quantization.

    Args:
        poster: Path to the poster image file.
        k: Number of dominant colors to extract (default 5).

    Returns:
        List of hex color strings (e.g., ['#ff0000', ...]), or None if Pillow unavailable.
    """
    if Image is None:
        return None
    im = Image.open(poster).convert("RGB")
    im.thumbnail((200, 200))
    q = im.quantize(colors=k, method=Image.Quantize.FASTOCTREE)
    pal = q.getpalette()[: k * 3]
    return [_hex((pal[i], pal[i + 1], pal[i + 2])) for i in range(0, k * 3, 3)]


def derive_tones(palette):
    rgbs = [_parse_hex(c) for c in palette]
    lums = [_luminance(c) for c in rgbs]
    avg = sum(lums) / len(lums)
    paired = sorted(zip(lums, rgbs, palette))
    darkest, median, lightest = paired[0], paired[len(paired) // 2], paired[-1]
    # Higher contrast for muted ink — old values (#5a5a5a / #9c9c9c) were too
    # faded to read for small caption / methodology / source-list copy.
    if avg > 0.55:
        return {"ink": "#0a0a0a", "ink_muted": "#3a3a3a",
                "stage": lightest[2], "surface": median[2]}
    return {"ink": "#fbfaf3", "ink_muted": "#d4d4d4",
            "stage": darkest[2], "surface": median[2]}


def render_placeholder_svg(show, palette):
    title = html.escape(show["title"].upper())
    subtitle = html.escape(show.get("subtitle", ""))
    c1, c2, c3, c4, c5 = palette
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 400" preserveAspectRatio="xMidYMid slice" role="img" aria-label="{html.escape(show['title'])} placeholder poster">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="55%" stop-color="{c2}"/>
      <stop offset="100%" stop-color="{c3}"/>
    </linearGradient>
    <radialGradient id="spot" cx="30%" cy="20%" r="70%">
      <stop offset="0%" stop-color="{c4}" stop-opacity="0.45"/>
      <stop offset="100%" stop-color="{c4}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="300" height="400" fill="url(#bg)"/>
  <rect width="300" height="400" fill="url(#spot)"/>
  <rect x="20" y="20" width="260" height="360" fill="none" stroke="{c5}" stroke-opacity="0.4" stroke-width="1"/>
  <text x="150" y="190" text-anchor="middle" font-family="Times New Roman, Georgia, serif" font-weight="900" font-size="32" fill="{c5}" letter-spacing="-1">{title}</text>
  <text x="150" y="215" text-anchor="middle" font-family="Times New Roman, Georgia, serif" font-style="italic" font-size="11" fill="{c5}" fill-opacity="0.8">{subtitle}</text>
  <text x="150" y="370" text-anchor="middle" font-family="Courier New, monospace" font-size="8" letter-spacing="3" fill="{c5}" fill-opacity="0.5">POSTER PLACEHOLDER</text>
</svg>"""


def _list_items(rows, roleless=False):
    """Render <li> rows for cast/creatives/producers. Returns '' if empty so
    the template can show 'TBA' itself."""
    if not rows:
        return '<li class="empty">TBA</li>'
    out = []
    for r in rows:
        if isinstance(r, str):
            out.append(f'<li><span class="n">{html.escape(r)}</span></li>')
            continue
        name = html.escape(r.get("name", ""))
        role = html.escape(r.get("role", ""))
        if role and not roleless:
            out.append(f'<li><span class="n">{name}</span><span class="r">{role}</span></li>')
        else:
            out.append(f'<li><span class="n">{name}</span></li>')
    return "\n        ".join(out)


def _ticket_rows(links: dict):
    if not links:
        return (
            '<tr><td colspan="3" class="pending">Ticket links pending — '
            'check your favorite vendor directly.</td></tr>'
        )
    rows = []
    # Preferred display order.
    order = ["telecharge", "todaytix", "tkts", "broadway_direct", "seatgeek", "official"]
    keys = sorted(links.keys(), key=lambda k: order.index(k) if k in order else 99)
    for vendor in keys:
        url = links[vendor]
        display = VENDOR_DISPLAY.get(vendor, vendor.replace("_", " ").title())
        blurb = VENDOR_BLURB.get(vendor, "")
        rows.append(
            f'<tr>'
            f'<td class="vendor">{html.escape(display)}</td>'
            f'<td>{html.escape(blurb)}</td>'
            f'<td><a class="go" href="{html.escape(url)}" target="_blank" rel="noopener">Check prices &rarr;</a></td>'
            f'</tr>'
        )
    return "\n          ".join(rows)


def _fmt_money(n):
    if n is None:
        return ("—", "pending")
    if n >= 1_000_000:
        return (f"${n/1_000_000:.2f}M", "")
    if n >= 1_000:
        return (f"${n//1_000}K", "")
    return (f"${n}", "")


def _fmt_avg(n):
    return ("—", "pending") if n is None else (f"${n}", "")


def _fmt_pct(p):
    return ("—", "pending") if p is None else (f"{p:.0f}%", "")


import re

_AKA_RE = re.compile(r"\bAKA\b", re.IGNORECASE)


def _firms_markup(raw_firms):
    """Render the marketing-firms panel body.

    Only the AKA-as-AOR case gets the gold/sparkle 'primary-row' treatment.
    Every other firm — even AORs from other agencies — renders as a flat
    'others' chip. Empty array -> 'No firms tracked'.
    """
    if not raw_firms:
        return '<div class="empty">No marketing firms tracked yet for this show.</div>'

    aka_aor = None  # the single AKA-AOR row, if it exists
    others: list[dict] = []
    aor_seen = False
    for entry in raw_firms:
        firm = (entry.get("firm") or "").strip()
        role = entry.get("role")
        if not firm or role not in VALID_FIRM_ROLES:
            continue
        is_primary = bool(entry.get("is_primary")) and not aor_seen
        if is_primary:
            aor_seen = True
        item = {
            "firm": firm,
            "role": role,
            "role_display": FIRM_ROLE_DISPLAY[role],
            "is_primary": is_primary,
        }
        if is_primary and _AKA_RE.search(firm):
            aka_aor = item
        else:
            others.append(item)

    # Sort others: AOR first (if non-AKA), then alphabetical.
    others.sort(key=lambda o: (not o["is_primary"], o["firm"].lower()))

    blocks: list[str] = []
    if aka_aor:
        blocks.append(
            f'<div class="primary-row">'
            f'<div class="lhs">'
            f'<span class="firm-name">{html.escape(aka_aor["firm"])}</span>'
            f'<span class="firm-role">{html.escape(aka_aor["role_display"])}</span>'
            f'</div>'
            f'<span class="aor-mark">★ Agency of Record</span>'
            f'</div>'
        )
    if others:
        rows = "\n        ".join(
            f'<div class="firm-row{" is-aor" if o["is_primary"] else ""}">'
            f'<span class="firm-name">{html.escape(o["firm"])}</span>'
            f'<span class="firm-role">{html.escape(o["role_display"])}{" · AOR" if o["is_primary"] else ""}</span>'
            f'</div>'
            for o in others
        )
        blocks.append(f'<div class="others">\n        {rows}\n      </div>')
    if not blocks:
        return '<div class="empty">No marketing firms tracked yet for this show.</div>'
    return "\n      ".join(blocks)


SOCIAL_PLATFORMS = [
    ("instagram", "Instagram"),
    ("tiktok",    "TikTok"),
    ("x",         "X (Twitter)"),
    ("threads",   "Threads"),
    ("facebook",  "Facebook"),
]
SOCIAL_ICONS = {
    "instagram": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line></svg>',
    "tiktok":    '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-5.2 1.74 2.89 2.89 0 0 1 2.31-4.64 2.93 2.93 0 0 1 .88.13V9.4a6.84 6.84 0 0 0-1-.05A6.33 6.33 0 0 0 5.6 20.1a6.34 6.34 0 0 0 10.86-4.43V8.62a8.16 8.16 0 0 0 4.77 1.52V6.69h-1.64z"/></svg>',
    "x":         '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>',
    "threads":   '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12.186 24h-.007c-3.581-.024-6.334-1.205-8.184-3.509C2.35 18.44 1.5 15.586 1.472 12.01v-.017c.03-3.579.879-6.43 2.525-8.482C5.845 1.205 8.6.024 12.18 0h.014c2.746.02 5.043.725 6.826 2.098 1.677 1.29 2.858 3.13 3.509 5.467l-2.04.569c-1.104-3.96-3.898-5.984-8.304-6.015-2.91.022-5.11.936-6.54 2.717C4.307 6.504 3.616 8.914 3.589 12c.027 3.086.718 5.496 2.057 7.164 1.43 1.783 3.631 2.698 6.54 2.717 2.623-.02 4.358-.631 5.8-2.045 1.647-1.613 1.618-3.593 1.09-4.798-.31-.71-.873-1.3-1.634-1.75-.192 1.352-.622 2.446-1.284 3.272-.886 1.102-2.14 1.704-3.73 1.79-1.202.065-2.361-.218-3.259-.801-1.063-.689-1.685-1.74-1.752-2.964-.065-1.19.408-2.285 1.33-3.082.88-.76 2.119-1.207 3.583-1.291a13.853 13.853 0 0 1 3.02.142c-.126-.742-.375-1.332-.74-1.757-.503-.585-1.281-.882-2.312-.89h-.024c-.806 0-1.901.218-2.6 1.247L7.4 7.156c.939-1.382 2.466-2.143 4.302-2.143h.034c3.06.022 4.881 1.882 5.063 5.122.103.043.205.087.305.132 1.4.654 2.426 1.65 2.967 2.879.755 1.706.825 4.486-1.435 6.69-1.726 1.687-3.82 2.47-6.79 2.494v-.01z"/></svg>',
    "facebook":  '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>',
}


def _socials_markup(socials):
    """Render social channels grid for a show. socials is a dict like
    {instagram: 'https://instagram.com/...', tiktok: '...', etc.}"""
    if not socials:
        return '<div class="socials-grid"><div class="empty">No social channels tracked yet.</div></div>'
    out = ['<div class="socials-grid">']
    for key, label in SOCIAL_PLATFORMS:
        url = socials.get(key)
        if not url:
            continue
        icon = SOCIAL_ICONS[key]
        out.append(
            f'<a class="social-link" href="{html.escape(url)}" target="_blank" rel="noopener" '
            f'data-platform="{key}" aria-label="{html.escape(label)}" title="{html.escape(label)}">{icon}</a>'
        )
    out.append('</div>')
    if len(out) == 2:  # only opening + closing div = no actual links
        return '<div class="socials-grid"><div class="empty">No social channels tracked yet.</div></div>'
    return "\n".join(out)


def _build_per_outlet_table(slug: str) -> str:
    """Render the per-outlet score table from the LLM aggregator cache.
    Returns HTML for a 2-col grid: critics left, audience right.
    Empty if the cache file is missing or has no scores."""
    cache_path = SCORE_CACHE_DIR / f"scores_{slug}.json"
    if not cache_path.exists():
        return '<div class="outlet-empty">Per-outlet scores will appear once aggregation lands.</div>'
    try:
        data = json.loads(cache_path.read_text())
    except json.JSONDecodeError:
        return '<div class="outlet-empty">Score data unreadable.</div>'
    crit = data.get("critic_scores") or {}
    aud = data.get("audience_scores") or {}
    crit_just = data.get("critic_justifications") or {}
    aud_just = data.get("audience_justifications") or {}
    parts = []
    # Critics column
    parts.append('<div><h4>Critics</h4>')
    if crit:
        for outlet, score in sorted(crit.items(), key=lambda kv: -kv[1]):
            j = html.escape(crit_just.get(outlet, ""))
            tooltip = f' title="{j}"' if j else ''
            parts.append(
                f'<div class="outlet-row"{tooltip}>'
                f'<span class="outlet-name">{html.escape(outlet)}</span>'
                f'<span class="outlet-score">{int(round(score))}</span></div>'
            )
    else:
        parts.append('<div class="outlet-empty">No critic data yet.</div>')
    parts.append('</div>')
    # Audience column
    parts.append('<div><h4>Audience</h4>')
    if aud:
        for outlet, score in sorted(aud.items(), key=lambda kv: -kv[1]):
            j = html.escape(aud_just.get(outlet, ""))
            tooltip = f' title="{j}"' if j else ''
            parts.append(
                f'<div class="outlet-row"{tooltip}>'
                f'<span class="outlet-name">{html.escape(outlet)}</span>'
                f'<span class="outlet-score">{int(round(score))}</span></div>'
            )
    else:
        parts.append('<div class="outlet-empty">No audience data yet.</div>')
    parts.append('</div>')
    return "\n".join(parts)


def build_one(show, template):
    slug = show["slug"]
    poster_path = _find_poster(slug)

    # Palette.
    if poster_path:
        extracted = extract_palette(poster_path)
        palette = extracted if extracted else list(show.get("palette", ["#333", "#666", "#999", "#ccc", "#fff"]))
        poster_markup = (
            f'<img src="posters/{poster_path.name}" alt="{html.escape(show["title"])} poster" '
            f'loading="lazy">'
        )
    else:
        palette = list(show.get("palette", ["#333", "#666", "#999", "#ccc", "#fff"]))
        # Pad to exactly 5 before rendering so the unpack in render_placeholder_svg works.
        padded = palette[:5] if len(palette) >= 5 else palette + ["#fff"] * (5 - len(palette))
        poster_markup = render_placeholder_svg(show, padded)

    while len(palette) < 5:
        palette.append(palette[-1])
    palette = palette[:5]
    tones = derive_tones(palette)

    gross_text, gross_class = _fmt_money(show.get("weekly_gross_usd"))
    avg_text, avg_class = _fmt_avg(show.get("avg_ticket_usd"))
    cap_text, cap_class = _fmt_pct(show.get("capacity_pct"))

    critic = show.get("critic_score")
    sentiment = show.get("sentiment_score")
    composite = show.get("composite_score")
    grade = show.get("grade") or "N/A"
    score_label = show.get("score_label") or "Coming soon"
    critic_sources = show.get("critic_sources_used") or []
    audience_sources = show.get("audience_sources_used") or []
    crit_count = len(critic_sources)
    aud_count = len(audience_sources)
    critic_methodology = (
        f"Weighted average across {crit_count} critic outlets (NYT, Variety, HR, Guardian, Vulture, AP, Time Out NY, TheaterMania, NY Post, BroadwayWorld). LLM-aggregated for v1."
        if crit_count else
        "Scoring soon — reviews still landing or production too new to aggregate."
    )
    audience_methodology = (
        f"Weighted aggregate across {aud_count} audience platforms (Show-Score, Broadway Scorecard, Broadway.com). Refreshes weekly."
        if aud_count else
        "Scoring soon — audience platforms still gathering ratings for this run."
    )
    critic_sources_list = ", ".join(critic_sources) if critic_sources else "—"
    audience_sources_list = ", ".join(audience_sources) if audience_sources else "—"
    grade_pill_class = "" if grade and grade != "N/A" else "grade-na"

    # Per-outlet score table — read from the cache file for this show
    per_outlet_html = _build_per_outlet_table(slug)

    replacements = {
        "{{TITLE}}": html.escape(show["title"]),
        "{{SUBTITLE}}": html.escape(show.get("subtitle", "")),
        "{{THEATRE}}": html.escape(show.get("theatre", "—")),
        "{{THEATRE_CAPACITY}}": f'{show["theatre_capacity"]:,}' if show.get("theatre_capacity") else "—",
        "{{FIRST_PREVIEW_DATE}}": html.escape(show.get("first_preview_date") or "—"),
        "{{OPENING_DATE}}": html.escape(show.get("opening_date") or "—"),
        "{{SYNOPSIS}}": html.escape(show.get("synopsis", "") or "—"),
        "{{STATUS_CHIP}}": html.escape(STATUS_CHIP_TEXT.get(show.get("status", "announced"), show.get("status", ""))),
        "{{POSTER_MARKUP}}": poster_markup,
        "{{CAST_LIST}}": _list_items(show.get("cast", [])),
        "{{CREATIVES_LIST}}": _list_items(show.get("creatives", [])),
        "{{PRODUCERS_LIST}}": _list_items([{"name": p} for p in show.get("producers", [])], roleless=True),
        "{{WEEKLY_GROSS}}": gross_text,
        "{{WEEKLY_GROSS_CLASS}}": gross_class,
        "{{AVG_TICKET}}": avg_text,
        "{{AVG_TICKET_CLASS}}": avg_class,
        "{{CAPACITY_PCT}}": cap_text,
        "{{CAPACITY_CLASS}}": cap_class,
        "{{TICKET_ROWS}}": _ticket_rows(show.get("ticket_links", {})),
        "{{FIRMS_MARKUP}}": _firms_markup(show.get("marketing_firms", [])),
        "{{SOCIALS_MARKUP}}": _socials_markup(show.get("socials", {})),
        "{{CRITIC_SCORE}}": str(critic) if critic is not None else "—",
        "{{CRITIC_CLASS}}": "" if critic is not None else "pending",
        "{{CRITIC_NOTE}}": f"{crit_count} critic outlets" if critic is not None else "Aggregation not yet available",
        "{{CRITIC_METHODOLOGY}}": critic_methodology,
        "{{CRITIC_SOURCES_LIST}}": html.escape(critic_sources_list),
        "{{SENTIMENT_SCORE}}": str(sentiment) if sentiment is not None else "—",
        "{{SENTIMENT_CLASS}}": "" if sentiment is not None else "pending",
        "{{SENTIMENT_NOTE}}": f"{aud_count} audience platforms" if sentiment is not None else "Aggregation not yet available",
        "{{AUDIENCE_METHODOLOGY}}": audience_methodology,
        "{{AUDIENCE_SOURCES_LIST}}": html.escape(audience_sources_list),
        "{{PER_OUTLET_TABLE}}": per_outlet_html,
        "{{COMPOSITE_SCORE}}": str(composite) if composite is not None else "—",
        "{{COMPOSITE_CLASS}}": "" if composite is not None else "pending",
        "{{COMPOSITE_GRADE}}": grade,
        "{{COMPOSITE_LABEL}}": score_label,
        "{{GRADE_PILL_CLASS}}": grade_pill_class,
        "{{C1}}": palette[0],
        "{{C2}}": palette[1],
        "{{C3}}": palette[2],
        "{{C4}}": palette[3],
        "{{C5}}": palette[4],
        "{{INK}}": tones["ink"],
        "{{INK_MUTED}}": tones["ink_muted"],
        "{{STAGE}}": tones["stage"],
        "{{SURFACE}}": tones["surface"],
        "{{LAST_UPDATED}}": datetime.now(timezone.utc).date().isoformat(),
        "{{SLUG}}": slug,
    }
    page = template
    for k, v in replacements.items():
        page = page.replace(k, v)

    out = SHOWS_DIR / f"{slug}.html"
    out.write_text(page)
    return out


def main():
    """Render web/shows/<slug>.html for each show in shows.json.

    Reads shows.json and _template.html, extracts poster palette (via Pillow),
    derives ink/surface tones, and emits one detail page per show with all
    metrics, cast/crew, ticket links, and marketing firms.
    """
    POSTERS_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(SHOWS_JSON.read_text())
    template = TEMPLATE.read_text()
    count = 0
    for show in data["shows"]:
        out = build_one(show, template)
        count += 1
        print(f"  {show['slug']:25} -> {out.relative_to(PROJECT_ROOT)}")
    print(f"rendered {count} show pages")


if __name__ == "__main__":
    main()
