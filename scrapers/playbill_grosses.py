"""
SLAYBILL — Playbill weekly grosses scraper.

Pulls the weekly Broadway grosses table from playbill.com/grosses and stores
each show-week into the `grosses` table. Also populates `shows.status='open'`
for any row that hasn't been seen before; classify_status.py refines state
afterward from news-event signals.

Run: weekly, Tuesday morning (Playbill publishes Monday).
"""

import sqlite3
import time
import re
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "corpus.db"
STOP_FILE = PROJECT_ROOT / "data" / "STOP"
SCHEMA_PATH = PROJECT_ROOT / "data" / "schema.sql"

URL = "https://playbill.com/grosses"
HEADERS = {
    "User-Agent": "SLAYBILL/1.0 (+https://slaybill.app)",
}


def check_stop() -> None:
    if STOP_FILE.exists():
        raise SystemExit("STOP file present — aborting.")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


def _to_int(s: str) -> int | None:
    """Parse the FIRST currency figure in s. Stops at the first non-digit/comma
    after the '$' so adjacent cells (e.g. attendance, capacity) don't bleed in."""
    if not s:
        return None
    m = re.search(r"\$([\d,]+)", s)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            return None
    # Fallback: first number in the string
    m = re.search(r"([\d,]{4,})", s)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _parse_week_ending(week_text: str | None) -> str | None:
    """Extract an ISO date from strings like 'Week Ending April 13, 2026'.

    Falls back to None if the page text is unparseable — callers should treat
    None as 'use a conservative default' rather than silently inserting wrong data.
    """
    if not week_text:
        return None
    m = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2}),?\s+(\d{4})",
        week_text,
        re.IGNORECASE,
    )
    if not m:
        return None
    try:
        return datetime.strptime(
            f"{m.group(1).title()} {m.group(2)} {m.group(3)}", "%B %d %Y"
        ).date().isoformat()
    except ValueError:
        return None


def _to_float(s: str) -> float | None:
    s = re.sub(r"[^\d\.\-]", "", s or "")
    try:
        return float(s) if s else None
    except ValueError:
        return None


def fetch() -> str:
    check_stop()
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    time.sleep(2.0)
    return r.text


def parse(html: str) -> list[dict]:
    """Extract one row per show for the current reporting week.

    The Playbill grosses page has evolved over the years; this parser is
    resilient to class-name changes by looking for tabular data that includes
    dollar gross columns and a show name.
    """
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    # Try to find the week-ending date near the top
    week_text = None
    for h in soup.find_all(["h1", "h2", "h3"]):
        txt = h.get_text(" ", strip=True)
        if "week ending" in txt.lower():
            week_text = txt
            break

    # Parse each table row looking for show + dollar figures
    for row in soup.select("table tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 3:
            continue
        # Heuristic: first cell is show, find a cell that looks like a dollar gross
        show = cells[0]
        dollar_cells = [c for c in cells if c.startswith("$")]
        if not dollar_cells:
            continue
        gross = _to_int(dollar_cells[0])
        if not gross or gross < 10000:  # filter out header rows and non-data
            continue

        # attendance + capacity% best-effort
        pct_cells = [c for c in cells if c.endswith("%")]
        capacity_pct = _to_float(pct_cells[0]) if pct_cells else None

        rows.append({
            "show": show,
            "gross_usd": gross,
            "capacity_pct": capacity_pct,
            "week_ending_text": week_text,
        })

    return rows


def upsert_show(conn: sqlite3.Connection, title: str) -> int:
    row = conn.execute("SELECT show_id FROM shows WHERE title = ?", (title,)).fetchone()
    if row:
        return row[0]
    cur = conn.execute("INSERT INTO shows (title, status) VALUES (?, 'live')", (title,))
    conn.commit()
    return cur.lastrowid


def run() -> None:
    """Main entry point: fetch Playbill grosses, parse, and upsert to corpus.db.

    Creates a scrape_run record, fetches the Playbill grosses page, parses each
    show's weekly gross + capacity%, upserts shows and grosses rows, and marks
    the scrape_run as success or error.
    """
    conn = connect()
    cur = conn.execute(
        "INSERT INTO scrape_runs (source, status) VALUES ('playbill_grosses', 'running')"
    )
    conn.commit()
    run_id = cur.lastrowid
    items = new = 0
    try:
        rows = parse(fetch())
        items = len(rows)
        if items == 0:
            # Parser returned nothing — Playbill probably changed their markup.
            # Raise so scrape_runs.status = 'error' instead of silently 'success'.
            raise RuntimeError(
                "playbill_grosses parser returned 0 rows — markup may have changed"
            )
        week_ending_iso = _parse_week_ending(rows[0].get("week_ending_text"))
        for r in rows:
            show_id = upsert_show(conn, r["show"])
            try:
                if week_ending_iso:
                    conn.execute(
                        """INSERT OR IGNORE INTO grosses
                           (show_id, week_ending, gross_usd, capacity_pct, source_url)
                           VALUES (?, ?, ?, ?, ?)""",
                        (show_id, week_ending_iso, r["gross_usd"], r["capacity_pct"], URL),
                    )
                else:
                    # No parseable week header — fall back to last Sunday, but log it.
                    print("[playbill_grosses] week_ending unparseable; using last Sunday")
                    conn.execute(
                        """INSERT OR IGNORE INTO grosses
                           (show_id, week_ending, gross_usd, capacity_pct, source_url)
                           VALUES (?, date('now','weekday 0','-7 days'), ?, ?, ?)""",
                        (show_id, r["gross_usd"], r["capacity_pct"], URL),
                    )
                conn.commit()
                new += 1
            except sqlite3.IntegrityError:
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
    run()
