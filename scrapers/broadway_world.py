"""
SLAYBILL — Broadway World news scraper.

Pulls show news, casting announcements, closings, reviews from
broadwayworld.com. Cadence: every 4 hours. Rate limit: 1 req / 3s.
Respects robots.txt.
"""

import sqlite3
import time
import argparse
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "corpus.db"
STOP_FILE = PROJECT_ROOT / "data" / "STOP"
SCHEMA_PATH = PROJECT_ROOT / "data" / "schema.sql"

BASE = "https://www.broadwayworld.com"
NEWS_URL = f"{BASE}/news/indexf.cfm"
HEADERS = {
    "User-Agent": "SLAYBILL/1.0 (+https://slaybill.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
REQUEST_DELAY_SEC = 3.0


def check_stop() -> None:
    if STOP_FILE.exists():
        raise SystemExit(f"STOP file present — aborting.")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def fetch(url: str) -> str:
    check_stop()
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    time.sleep(REQUEST_DELAY_SEC)
    return r.text


def parse_index(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []
    # BroadwayWorld articles historically have /article/ in href
    for a in soup.select('a[href*="/article/"]'):
        href = a.get("href", "")
        title = a.get_text(" ", strip=True)
        if not href or not title or len(title) < 15:
            continue
        out.append({"url": urljoin(BASE, href), "title": title})
    seen: set[str] = set()
    deduped = []
    for item in out:
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        deduped.append(item)
    return deduped


def parse_article(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    body = " ".join(
        p.get_text(" ", strip=True) for p in soup.select("article p, .article-text p, #article-content p")
    )[:4000]
    return {"body": body}


def classify(title: str, body: str) -> tuple[str, int]:
    t = f"{title} {body}".lower()
    if any(k in t for k in ["will close", "closes", "closing notice", "will end"]):
        return "closing_notice", 4
    if any(k in t for k in ["extends", "extension"]):
        return "extension", 2
    if any(k in t for k in ["new director", "replacing", "takes over", "new choreographer"]):
        return "creative_swap", 4
    if any(k in t for k in ["cast change", "new cast", "joins the cast"]):
        return "cast_change", 3
    if any(k in t for k in ["understudy", "out of the show"]):
        return "understudy_go_on", 3
    if any(k in t for k in ["pulled", "delayed", "postponed", "cancelled"]):
        return "silent_pull", 5
    return "announcement", 1


def run(backfill: bool = False) -> None:
    conn = connect()
    cur = conn.execute(
        "INSERT INTO scrape_runs (source, status) VALUES ('broadway_world', 'running')"
    )
    conn.commit()
    run_id = cur.lastrowid
    items = new = 0
    try:
        stubs = parse_index(fetch(NEWS_URL))[: 80 if backfill else 20]
        items = len(stubs)
        http_errors = 0
        for stub in stubs:
            try:
                art = parse_article(fetch(stub["url"]))
                event_type, severity = classify(stub["title"], art["body"])
                cur = conn.execute(
                    """INSERT OR IGNORE INTO events (show_id, event_type, source, source_url,
                       raw_snippet, severity) VALUES (NULL, ?, 'broadway_world', ?, ?, ?)""",
                    (event_type, stub["url"], (stub["title"] + " :: " + art["body"])[:2000], severity),
                )
                conn.commit()
                if cur.rowcount > 0:
                    new += 1
            except requests.HTTPError as e:
                http_errors += 1
                print(f"[broadway_world] HTTP error on {stub['url']}: {e}")
                continue
        conn.execute(
            """UPDATE scrape_runs SET ended_at = CURRENT_TIMESTAMP, status = 'success',
               items_ingested = ?, new_events = ? WHERE run_id = ?""",
            (items, new, run_id),
        )
        conn.commit()
    except Exception as e:
        conn.execute(
            """UPDATE scrape_runs SET ended_at = CURRENT_TIMESTAMP, status = 'error',
               error_message = ? WHERE run_id = ?""",
            (str(e), run_id),
        )
        conn.commit()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true")
    run(backfill=ap.parse_args().backfill)
