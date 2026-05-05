"""
SLAYBILL — broadway.com poster fetcher.

For each show in shows.json, attempt to fetch the official poster image from
broadway.com ONLY. broadway.com serves posters via their CDN at
`imaging.broadway.com/images/poster-{id}/w{w}/{img_id}.jpg`. The schema.org
JSON-LD on each show page exposes a clean image[] array including a w480
poster variant — that's what we grab.

URL discovery strategy (in order):
  1. https://www.broadway.com/shows/<slug>-broadway/   (most common pattern)
  2. https://www.broadway.com/shows/<slug>/             (fallback)
  3. https://www.broadway.com/shows/<slug>-musical/     (some musicals)
  4. https://www.broadway.com/shows/<slug>-on-broadway/ (occasional variant)

If none of those resolve, we use broadway.com's own search:
  https://www.broadway.com/search/?q=<title>
and pick the first /shows/* link.

Pulled posters are validated via Pillow (>= 300x400, <= 5MB) before keep.

Run:
    uv run --with requests --with beautifulsoup4 --with Pillow python tools/poster_fetcher.py
    uv run --with requests --with beautifulsoup4 --with Pillow python tools/poster_fetcher.py --slug hamilton
    uv run --with requests --with beautifulsoup4 --with Pillow python tools/poster_fetcher.py --force
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, quote_plus

import requests
from bs4 import BeautifulSoup
from PIL import Image

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
SHOWS_JSON = PROJECT_ROOT / "data" / "shows.json"
POSTERS_DIR = PROJECT_ROOT / "web" / "shows" / "posters"

UA = "SLAYBILL/1.0 poster-fetcher (+https://slaybill.app)"
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}

REQUEST_DELAY_SEC = 1.5
MIN_WIDTH = 300
MIN_HEIGHT = 400
MAX_BYTES = 5 * 1024 * 1024
POSTER_EXTS = (".jpg", ".jpeg", ".png", ".webp")

URL_TEMPLATES = [
    "https://www.broadway.com/shows/{slug}-broadway/",
    "https://www.broadway.com/shows/{slug}/",
    "https://www.broadway.com/shows/{slug}-musical/",
    "https://www.broadway.com/shows/{slug}-on-broadway/",
]


def existing_poster(slug: str) -> Path | None:
    """Check if a poster already exists for the given show slug.

    Args:
        slug: Show slug identifier.

    Returns:
        Path to existing poster file, or None if not found.
    """
    for ext in POSTER_EXTS:
        p = POSTERS_DIR / f"{slug}{ext}"
        if p.exists():
            return p
    return None


def fetch(url: str, timeout: int = 20) -> requests.Response:
    """Fetch URL with SLAYBILL user-agent headers.

    Args:
        url: Target URL to fetch.
        timeout: Request timeout in seconds (default 20).

    Returns:
        requests.Response object.
    """
    return requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)


def discover_show_url(slug: str, title: str) -> str | None:
    """Try predictable URL patterns first, fall back to broadway.com search."""
    DEAD_PATHS = ("/shows/tickets/", "/shows/tickets", "/shows/", "/shows")
    for tpl in URL_TEMPLATES:
        url = tpl.format(slug=slug)
        try:
            r = fetch(url)
            final = r.url
            tail = final.split("broadway.com")[-1] if "broadway.com" in final else ""
            if r.status_code == 200 and "/shows/" in final and tail not in DEAD_PATHS:
                return final
        except requests.RequestException:
            continue
        time.sleep(0.4)
    try:
        r = fetch(f"https://www.broadway.com/search/?q={quote_plus(title)}")
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select('a[href*="/shows/"]'):
                href = a.get("href", "")
                if href and "/shows/" in href and "/shows/" != href.rstrip("/"):
                    return urljoin("https://www.broadway.com/", href)
    except requests.RequestException:
        pass
    return None


def extract_poster_url(page_html: str) -> str | None:
    """Pull the highest-resolution poster from broadway.com markup."""
    soup = BeautifulSoup(page_html, "html.parser")

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("@type") == "Product":
            images = data.get("image") or []
            if isinstance(images, str):
                images = [images]
            poster_candidates = [u for u in images if "/poster-" in u]
            if poster_candidates:
                for u in poster_candidates:
                    if "/w480/" in u:
                        return u
                return poster_candidates[0]
            if images:
                return images[0]

    hero = soup.select_one(".showpage__hero--poster, img.showpage__hero--poster")
    if hero:
        src = hero.get("data-src") or hero.get("src")
        if src and "/poster-" in src:
            return re.sub(r"/w\d+/", "/w480/", src)

    og = soup.select_one('meta[property="og:image"]')
    if og and og.get("content"):
        src = og["content"]
        if "/poster-" in src:
            return re.sub(r"/w\d+/", "/w480/", src)
        # Reject broadway.com's site-wide generic og:image (filename starts
        # with "open-graph" and is the same blob across every show without a
        # real poster). Better to fall back to the SVG palette poster than
        # show the same image on 11 cards.
        if "/open-graph" in src or src.endswith("/open-graph.jpg"):
            return None
        return src

    return None


def download_and_validate(url: str, dest_no_ext: Path) -> tuple[Path | None, str]:
    try:
        r = fetch(url)
    except requests.RequestException as e:
        return None, f"download error: {e}"
    if r.status_code != 200:
        return None, f"download HTTP {r.status_code}"
    body = r.content
    if len(body) > MAX_BYTES:
        return None, f"too large ({len(body)} bytes)"
    try:
        im = Image.open(io.BytesIO(body))
        im.load()
    except Exception as e:
        return None, f"invalid image: {e}"
    if im.width < MIN_WIDTH or im.height < MIN_HEIGHT:
        return None, f"too small ({im.width}x{im.height})"
    fmt = (im.format or "JPEG").lower()
    ext = {"jpeg": ".jpg", "jpg": ".jpg", "png": ".png", "webp": ".webp"}.get(fmt, ".jpg")
    dest = dest_no_ext.with_suffix(ext)
    dest.write_bytes(body)
    return dest, f"saved {im.width}x{im.height} {ext.lstrip('.')}"


def fetch_one(slug: str, title: str, force: bool = False) -> tuple[str, str]:
    if not force:
        existing = existing_poster(slug)
        if existing:
            return "skip", f"already have {existing.name}"

    show_url = discover_show_url(slug, title)
    if not show_url:
        return "fail", "no broadway.com page found"
    time.sleep(REQUEST_DELAY_SEC)

    try:
        r = fetch(show_url)
    except requests.RequestException as e:
        return "fail", f"page fetch error: {e}"
    if r.status_code != 200:
        return "fail", f"page HTTP {r.status_code}"

    poster_url = extract_poster_url(r.text)
    if not poster_url:
        return "fail", f"no poster image on {show_url}"
    time.sleep(0.5)

    dest_no_ext = POSTERS_DIR / slug
    saved, msg = download_and_validate(poster_url, dest_no_ext)
    if saved is None:
        return "fail", f"poster_url={poster_url} :: {msg}"
    return "ok", f"{poster_url.split('/')[-1]} :: {msg}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", help="Fetch only this slug (smoke-test)")
    ap.add_argument("--force", action="store_true", help="Redownload even if poster exists")
    args = ap.parse_args()

    POSTERS_DIR.mkdir(parents=True, exist_ok=True)
    shows = json.loads(SHOWS_JSON.read_text())["shows"]
    if args.slug:
        shows = [s for s in shows if s["slug"] == args.slug]

    results = {"ok": 0, "skip": 0, "fail": 0}
    failures: list[tuple[str, str]] = []

    for show in shows:
        slug = show["slug"]
        title = show["title"]
        status, msg = fetch_one(slug, title, force=args.force)
        results[status] += 1
        marker = {"ok": "[ok]  ", "skip": "[skip]", "fail": "[FAIL]"}[status]
        print(f"{marker} {slug:42} {msg}")
        if status == "fail":
            failures.append((slug, msg))
        sys.stdout.flush()
        time.sleep(REQUEST_DELAY_SEC)

    print()
    print(f"== summary ==  ok: {results['ok']}  skip: {results['skip']}  fail: {results['fail']}")
    if failures:
        print("\n== failures ==")
        for slug, msg in failures:
            print(f"  {slug}: {msg}")


if __name__ == "__main__":
    main()
