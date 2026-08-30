"""
SLAYBILL — Playbill weekly grosses scraper.

Pulls the weekly Broadway grosses table from playbill.com/grosses and stores
each show-week into the `grosses` table. Also populates `shows.status='open'`
for any row that hasn't been seen before; classify_status.py refines state
afterward from news-event signals.

v1.5: captures the full 8-column table — gross, week-over-week gross diff,
average + top ticket, attendance, performance count, capacity %, and
week-over-week capacity diff. The diff columns power the front page's
Standing O's / Oh No's board.

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
    """Check for STOP file and abort scraper if present.

    Raises:
        SystemExit: If data/STOP file exists.
    """
    if STOP_FILE.exists():
        raise SystemExit("STOP file present — aborting.")


def connect() -> sqlite3.Connection:
    """Open connection to corpus.db, ensure schema + v1.5 columns exist.

    Returns:
        sqlite3.Connection: Database connection with schema applied.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text())
    existing = {r[1] for r in conn.execute("PRAGMA table_info(grosses)")}
    for col, decl in (
        ("gross_diff_usd", "INTEGER"),
        ("capacity_diff_pct", "REAL"),
        ("performances", "INTEGER"),
    ):
        if col not in existing:
            conn.execute(f"ALTER TABLE grosses ADD COLUMN {col} {decl}")
    conn.commit()
    return conn


def _signed_usd(s: str) -> int | None:
    """Parse a currency figure keeping its sign: '-$90,307.55' -> -90307."""
    if not s:
        return None
    m = re.search(r"(-?)\s*\$\s*([\d,]+)", s)
    if not m:
        return None
    try:
        val = int(m.group(2).replace(",", ""))
        return -val if m.group(1) == "-" else val
    except ValueError:
        return None


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


def _first_int(s: str) -> int | None:
    """First plain integer in a cell like '6,619 1,026' -> 6619."""
    m = re.search(r"([\d,]+)", s or "")
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
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
    """Fetch Playbill weekly grosses page HTML.

    Returns:
        str: Raw HTML content of the grosses page.

    Raises:
        SystemExit: If STOP file present.
        requests.HTTPError: If HTTP request fails.
    """
    check_stop()
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    time.sleep(2.0)
    return r.text


def parse(html: str) -> list[dict]:
    """Extract one row per show for the current reporting week.

    The current Playbill table is 8 positional columns:
        0 show + theatre · 1 gross · 2 gross diff · 3 avg + top ticket
        4 attendance + house size · 5 perfs + previews · 6 cap % · 7 cap diff
    Rows with a different shape fall back to the old dollar-cell heuristic so
    a markup change degrades to partial data instead of zero rows.
    """
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    # Week-ending date: try headings first, then anywhere in the page text.
    week_text = None
    for h in soup.find_all(["h1", "h2", "h3"]):
        txt = h.get_text(" ", strip=True)
        if "week ending" in txt.lower():
            week_text = txt
            break
    if not week_text:
        m = re.search(r"week\s+ending\s+[^<\n]{0,40}", soup.get_text(" ", strip=True),
                      re.IGNORECASE)
        if m:
            week_text = m.group(0)

    for row in soup.select("table tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 3:
            continue
        show = cells[0]

        if len(cells) == 8:
            gross = _to_int(cells[1])
            if not gross or gross < 10000:
                continue
            rows.append({
                "show": show,
                "gross_usd": gross,
                "gross_diff_usd": _signed_usd(cells[2]),
                "average_ticket_usd": _to_float((cells[3] or "").split()[0]) if cells[3] else None,
                "attendance": _first_int(cells[4]),
                "performances": _first_int(cells[5]),
                "capacity_pct": _to_float(cells[6]),
                "capacity_diff_pct": _to_float(cells[7]),
                "week_ending_text": week_text,
            })
            continue

        # Fallback heuristic for unexpected shapes.
        dollar_cells = [c for c in cells if c.startswith("$")]
        if not dollar_cells:
            continue
        gross = _to_int(dollar_cells[0])
        if not gross or gross < 10000:
            continue
        pct_cells = [c for c in cells if c.endswith("%")]
        rows.append({
            "show": show,
            "gross_usd": gross,
            "gross_diff_usd": None,
            "average_ticket_usd": None,
            "attendance": None,
            "performances": None,
            "capacity_pct": _to_float(pct_cells[0]) if pct_cells else None,
            "capacity_diff_pct": None,
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
    show's weekly figures, upserts shows and grosses rows (re-scrapes update the
    same show-week in place), and marks the scrape_run as success or error.
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
        if not week_ending_iso:
            print("[playbill_grosses] week_ending unparseable; using last Sunday")
        for r in rows:
            show_id = upsert_show(conn, r["show"])
            conn.execute(
                """INSERT INTO grosses
                       (show_id, week_ending, gross_usd, attendance, capacity_pct,
                        average_ticket_usd, gross_diff_usd, capacity_diff_pct,
                        performances, source_url)
                   VALUES (?, COALESCE(?, date('now','weekday 0','-7 days')),
                           ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(show_id, week_ending) DO UPDATE SET
                       gross_usd = excluded.gross_usd,
                       attendance = excluded.attendance,
                       capacity_pct = excluded.capacity_pct,
                       average_ticket_usd = excluded.average_ticket_usd,
                       gross_diff_usd = excluded.gross_diff_usd,
                       capacity_diff_pct = excluded.capacity_diff_pct,
                       performances = excluded.performances,
                       source_url = excluded.source_url""",
                (show_id, week_ending_iso, r["gross_usd"], r["attendance"],
                 r["capacity_pct"], r["average_ticket_usd"], r["gross_diff_usd"],
                 r["capacity_diff_pct"], r["performances"], URL),
            )
            conn.commit()
            new += 1
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
