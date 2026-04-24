"""
SLAYBILL — status classifier.

Back-propagates data from the events + grosses tables into shows.status and
the show date fields. Run after every scrape. First matching rule wins:

    1. closing_date < today OR 'closing_notice' event with past date      -> closed
    2. 'cancelled' event                                                  -> cancelled
    3. opening_date <= today AND (closing_date IS NULL OR >= today)       -> live
    4. first_preview_date <= today < opening_date                         -> in_previews
    5. first_preview_date > today AND <= today + 42 days                  -> coming_soon
    6. otherwise                                                          -> announced

Secondary: a grosses row for the current week promotes the show to 'live'
when its dates are missing. This catches newly-scraped shows that haven't
had their opening_date populated yet.

Usage:
    python builders/classify_status.py

This does NOT set dates from events — it only reads whatever dates are already
on shows rows, plus uses event signals as modifiers. Date population is the
scrapers' job; when they don't have it, status stays conservative.
"""

import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
DB_PATH = PROJECT_ROOT / "data" / "corpus.db"

COMING_SOON_WINDOW_DAYS = 42  # 6 weeks


def classify_one(row: dict, today: date, had_closing_notice: bool, had_cancelled: bool,
                 had_recent_gross: bool) -> str:
    """Return the correct status string for a single show."""
    closing = row["closing_date"]
    opening = row["opening_date"]
    first_preview = row["first_preview_date"]

    # 1 + 2 — closed/cancelled short-circuits everything.
    if had_cancelled:
        return "cancelled"
    if had_closing_notice or (closing and _d(closing) < today):
        return "closed"

    # 3 — opened and not past closing.
    if opening and _d(opening) <= today:
        if not closing or _d(closing) >= today:
            return "live"

    # Secondary: grosses this week + no dates means we can still call it live.
    if had_recent_gross and not opening and not first_preview:
        return "live"

    # 4 — in previews.
    if first_preview and _d(first_preview) <= today:
        if not opening or today < _d(opening):
            return "in_previews"

    # 5 — coming soon (previews start within the window).
    if first_preview and today < _d(first_preview) <= today + timedelta(days=COMING_SOON_WINDOW_DAYS):
        return "coming_soon"

    # 6 — fallback.
    return "announced"


def _d(v) -> date:
    """Coerce a SQLite TEXT date to a datetime.date."""
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def run() -> dict:
    if not DB_PATH.exists():
        raise SystemExit(f"No DB at {DB_PATH}. Run scrapers first.")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    today = date.today()
    today_minus_14 = today - timedelta(days=14)

    rows = conn.execute(
        "SELECT show_id, title, status, first_preview_date, opening_date, closing_date FROM shows"
    ).fetchall()

    changed = 0
    tallies: dict[str, int] = {}
    for r in rows:
        show_id = r["show_id"]

        # Event-based short-circuits.
        had_closing_notice = conn.execute(
            "SELECT 1 FROM events WHERE show_id = ? AND event_type = 'closing_notice' LIMIT 1",
            (show_id,),
        ).fetchone() is not None
        had_cancelled = conn.execute(
            "SELECT 1 FROM events WHERE show_id = ? AND event_type = 'silent_pull' "
            "AND raw_snippet LIKE '%cancelled%' LIMIT 1",
            (show_id,),
        ).fetchone() is not None
        had_recent_gross = conn.execute(
            "SELECT 1 FROM grosses WHERE show_id = ? AND week_ending >= ? LIMIT 1",
            (show_id, today_minus_14.isoformat()),
        ).fetchone() is not None

        new_status = classify_one(dict(r), today, had_closing_notice, had_cancelled,
                                  had_recent_gross)

        tallies[new_status] = tallies.get(new_status, 0) + 1

        if new_status != r["status"]:
            conn.execute(
                "UPDATE shows SET status = ?, last_updated_at = CURRENT_TIMESTAMP "
                "WHERE show_id = ?",
                (new_status, show_id),
            )
            changed += 1

    conn.commit()
    conn.close()

    return {"rows_seen": len(rows), "rows_changed": changed, "by_status": tallies}


if __name__ == "__main__":
    summary = run()
    print(
        f"classify_status: {summary['rows_seen']} shows, "
        f"{summary['rows_changed']} status changes"
    )
    for status, n in sorted(summary["by_status"].items(), key=lambda kv: -kv[1]):
        print(f"  {status:14} {n}")
