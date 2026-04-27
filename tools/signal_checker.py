"""
SLAYBILL — event signal checker (editorial utility).

Reads corpus.db populated by the scrapers. Counts last-24h events by severity
and emits a one-line verdict into data/status.json. Useful as a cheap
editorial signal ("is today a high-activity news day?"). Not wired into the
front-end — classify_status.py is the one that drives bucket membership.
"""

import html
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
DB = PROJECT_ROOT / "data" / "corpus.db"
INDEX_HTML = PROJECT_ROOT / "web" / "index.html"
STATUS_JSON = PROJECT_ROOT / "data" / "status.json"

MUSICAL_THRESHOLD = 5  # severity>=4 events in last 24h to declare "musical"
PLAY_THRESHOLD = 1     # at least this many events to say "straight play", else "preview"


def _count_recent(conn: sqlite3.Connection, min_severity: int = 0) -> int:
    try:
        q = """SELECT COUNT(*) FROM events
               WHERE detected_at >= datetime('now','-1 day')
               AND severity >= ?"""
        return conn.execute(q, (min_severity,)).fetchone()[0]
    except sqlite3.OperationalError as e:
        # Schema missing or drifted — surface rather than silently return 0.
        print(f"[signal_checker] events table unavailable: {e}", file=sys.stderr)
        return 0


def run() -> dict:
    """Generate editorial signal verdict from recent events in corpus.db.

    Counts events from the last 24 hours, classifies as musical/play/preview
    based on severity thresholds, and writes the verdict to data/status.json
    and updates web/index.html.

    Returns:
        dict: Verdict summary with label, subline, and event counts.
    """
    if not DB.exists():
        return _write_verdict("preview", "Corpus not yet created.", 0, 0)
    with sqlite3.connect(DB) as conn:
        total = _count_recent(conn, 0)
        high = _count_recent(conn, 4)
    if total == 0:
        verdict = "preview"
        subline = "Corpus empty. First scrape cycle pending."
    elif high >= MUSICAL_THRESHOLD:
        verdict = "musical"
        subline = f"{high} high-severity events in last 24h. Pattern forming — pitch candidate."
    elif total >= PLAY_THRESHOLD:
        verdict = "play"
        subline = f"{total} events tracked, {high} high-severity. No pitch-worthy pattern yet."
    else:
        verdict = "preview"
        subline = "Sparse data. Need more scrape cycles."
    return _write_verdict(verdict, subline, total, high)


def _write_verdict(verdict: str, subline: str, total: int, high: int) -> dict:
    verdict_map = {
        "musical": ("Tonight is", "The Musical", "musical"),
        "play": ("Tonight is", "The Straight Play", "play"),
        "preview": ("Tonight is", "In Previews", "preview"),
    }
    kicker, label, css_class = verdict_map[verdict]
    summary = {
        "last_run_iso": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "label": label,
        "subline": subline,
        "events_24h_total": total,
        "events_24h_high_severity": high,
    }
    STATUS_JSON.write_text(json.dumps(summary, indent=2))

    if INDEX_HTML.exists():
        page = INDEX_HTML.read_text()
        block = f"""<!-- STATUS-BEGIN -->
    <div class="venue">Broadway &amp; Off-Broadway · Tonight's Read</div>
    <h1 class="verdict {css_class}">
      <span class="kicker">{html.escape(kicker)}</span>
      {html.escape(label)}
    </h1>
    <p class="subverdict">{html.escape(subline)}</p>
    <!-- STATUS-END -->"""
        page = re.sub(
            r"<!-- STATUS-BEGIN -->.*?<!-- STATUS-END -->",
            block,
            page,
            count=1,
            flags=re.DOTALL,
        )
        INDEX_HTML.write_text(page)
    return summary


if __name__ == "__main__":
    s = run()
    print(json.dumps(s, indent=2))
