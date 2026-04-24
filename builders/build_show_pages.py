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
    if avg > 0.55:
        return {"ink": "#121212", "ink_muted": "#5a5a5a",
                "stage": lightest[2], "surface": median[2]}
    return {"ink": "#f5f1e6", "ink_muted": "#9c9c9c",
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
        "{{CRITIC_SCORE}}": str(critic) if critic is not None else "—",
        "{{CRITIC_CLASS}}": "" if critic is not None else "pending",
        "{{CRITIC_NOTE}}": "Aggregated from critic reviews" if critic is not None else "Coming soon — aggregation not yet live",
        "{{SENTIMENT_SCORE}}": str(sentiment) if sentiment is not None else "—",
        "{{SENTIMENT_CLASS}}": "" if sentiment is not None else "pending",
        "{{SENTIMENT_NOTE}}": "Social listening aggregate" if sentiment is not None else "Coming soon — social-listening pipeline pending",
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
    }
    page = template
    for k, v in replacements.items():
        page = page.replace(k, v)

    out = SHOWS_DIR / f"{slug}.html"
    out.write_text(page)
    return out


def main():
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
