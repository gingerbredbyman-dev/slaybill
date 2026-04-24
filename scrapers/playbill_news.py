"""
SLAYBILL — Playbill News scraper.

Pulls show announcements, cast changes, closing notices, preview extensions
from Playbill's public news feed. Writes new items to the `events` table.
classify_status.py reads these events afterward and back-propagates status
changes (preview_change -> in_previews, closing_notice -> closed, etc.) to
the `shows` table.

Run cadence: every 2 hours.
Rate limit: 1 request per 3 seconds, respects robots.txt.

Usage:
    python playbill_news.py              # incremental run
    python playbill_news.py --backfill   # backfill last 30 days
"""

import json
import sqlite3
import time
import hashlib
import argparse
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "corpus.db"
STOP_FILE = PROJECT_ROOT / "data" / "STOP"
SCHEMA_PATH = PROJECT_ROOT / "data" / "schema.sql"

BASE = "https://playbill.com"
NEWS_INDEX = f"{BASE}/news"
HEADERS = {
    "User-Agent": "SLAYBILL/1.0 (+https://slaybill.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
REQUEST_DELAY_SEC = 3.0


def check_stop() -> None:
    if STOP_FILE.exists():
        raise SystemExit(f"STOP file present at {STOP_FILE} — aborting.")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def start_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO scrape_runs (source, status) VALUES (?, 'running')",
        ("playbill_news",),
    )
    conn.commit()
    return cur.lastrowid


def finish_run(conn: sqlite3.Connection, run_id: int, status: str,
               items: int, new_events: int, error: str | None = None) -> None:
    conn.execute(
        """UPDATE scrape_runs SET ended_at = CURRENT_TIMESTAMP, status = ?,
           items_ingested = ?, new_events = ?, error_message = ? WHERE run_id = ?""",
        (status, items, new_events, error, run_id),
    )
    conn.commit()


def fetch(url: str) -> str:
    check_stop()
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    time.sleep(REQUEST_DELAY_SEC)
    return r.text


def parse_news_index(html: str) -> list[dict]:
    """Extract article stubs from the news index page. Structure-tolerant."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []

    # Playbill article cards typically have h2/h3 links with /news/article/ in href.
    for a in soup.select('a[href*="/news/article/"]'):
        href = a.get("href", "")
        title = a.get_text(strip=True)
        if not href or not title:
            continue
        out.append({
            "url": urljoin(BASE, href),
            "title": title,
        })

    # Deduplicate by URL preserving order
    seen: set[str] = set()
    deduped: list[dict] = []
    for item in out:
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        deduped.append(item)
    return deduped


def classify_event_type(title: str, body: str) -> tuple[str, int]:
    """Heuristic classifier. Returns (event_type, severity 1-5).

    LLM-based classifier slots in here once we're ready; for now, keyword rules
    that are explainable and debuggable.
    """
    t = f"{title} {body}".lower()

    if any(k in t for k in ["will close", "closing notice", "closes", "will end"]):
        return "closing_notice", 4
    if any(k in t for k in ["extends", "extension", "extended through"]):
        return "extension", 2
    if any(k in t for k in ["new director", "replacing", "takes over", "new choreographer"]):
        return "creative_swap", 4
    if any(k in t for k in ["cast change", "new cast", "joins the cast", "takes over the role"]):
        return "cast_change", 3
    if any(k in t for k in ["out of the show", "understudy", "will not perform"]):
        return "understudy_go_on", 3
    if any(k in t for k in ["new producer", "producer change"]):
        return "producer_change", 4
    if any(k in t for k in ["pulled", "delayed", "postponed", "cancelled"]):
        return "silent_pull", 5
    if any(k in t for k in ["preview", "begins performances"]):
        return "preview_change", 2
    return "announcement", 1


def stable_event_id(url: str, title: str) -> str:
    return hashlib.sha256(f"{url}|{title}".encode()).hexdigest()[:16]


def parse_article(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    body_parts = [p.get_text(" ", strip=True) for p in soup.select("article p, .article-body p")]
    body = " ".join(body_parts)[:4000]
    dt_tag = soup.find("time")
    pub_date = None
    if dt_tag and dt_tag.get("datetime"):
        try:
            pub_date = datetime.fromisoformat(dt_tag["datetime"].replace("Z", "+00:00")).date().isoformat()
        except Exception:
            pub_date = None
    return {"body": body, "pub_date": pub_date}


def upsert_event(conn: sqlite3.Connection, stub: dict, article: dict) -> bool:
    event_type, severity = classify_event_type(stub["title"], article["body"])
    event_hash = stable_event_id(stub["url"], stub["title"])

    cur = conn.execute(
        """INSERT OR IGNORE INTO events (show_id, event_type, event_date, source,
           source_url, raw_snippet, severity, parsed_fields)
           VALUES (NULL, ?, ?, 'playbill_news', ?, ?, ?, ?)""",
        (
            event_type,
            article["pub_date"],
            stub["url"],
            (stub["title"] + " :: " + article["body"])[:2000],
            severity,
            json.dumps({"hash": event_hash}),
        ),
    )
    conn.commit()
    return cur.rowcount > 0


def run(backfill: bool = False) -> None:
    conn = connect()
    run_id = start_run(conn)
    items = 0
    new_events = 0
    try:
        index_html = fetch(NEWS_INDEX)
        stubs = parse_news_index(index_html)
        # Limit to first 20 on incremental, first 100 on backfill
        stubs = stubs[: 100 if backfill else 20]
        items = len(stubs)

        http_errors = 0
        for stub in stubs:
            try:
                art_html = fetch(stub["url"])
                article = parse_article(art_html)
                if upsert_event(conn, stub, article):
                    new_events += 1
            except requests.HTTPError as e:
                http_errors += 1
                print(f"[playbill_news] HTTP error on {stub['url']}: {e}")
                continue

        status = "partial" if http_errors and new_events else ("success" if not http_errors else "error")
        err = f"{http_errors} article(s) failed to fetch" if http_errors else None
        finish_run(conn, run_id, status, items, new_events, err)
    except Exception as e:
        finish_run(conn, run_id, "error", items, new_events, str(e))
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true")
    args = ap.parse_args()
    run(backfill=args.backfill)
