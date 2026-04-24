"""
SLAYBILL — build web/archive.html from shows.json.

Lists every show with status in {closed, closed_early, cancelled}. Simple
chronological view with a row per show and a link to each show's Tier 2
detail page (if still generated).

Run:
    python builders/build_archive.py
"""

import html
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
SHOWS_JSON = PROJECT_ROOT / "data" / "shows.json"
OUT_PATH = PROJECT_ROOT / "web" / "archive.html"

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Archive — SLAYBILL</title>
<style>
  :root {{
    --bg: #0a0a0a;
    --ink: #e8e8e8;
    --muted: #8a8a8a;
    --accent: #f4c842;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; }}
  body {{
    background: var(--bg);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    min-height: 100vh;
    padding: 48px 24px 80px;
  }}
  .wrap {{ max-width: 900px; margin: 0 auto; }}
  .back {{
    display: inline-block;
    font-family: "Courier New", monospace;
    font-size: 11px;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: var(--muted);
    text-decoration: none;
    padding: 6px 10px;
    border: 1px solid rgba(232,232,232,0.15);
    border-radius: 999px;
    margin-bottom: 32px;
  }}
  .back:hover {{ color: var(--ink); border-color: rgba(232,232,232,0.35); }}
  h1 {{
    font-family: "Times New Roman", Georgia, serif;
    font-weight: 900;
    font-size: clamp(48px, 6vw + 10px, 80px);
    letter-spacing: -0.02em;
    line-height: 0.95;
    margin: 0 0 6px;
    text-transform: uppercase;
  }}
  .sub {{
    color: var(--muted);
    font-family: "Courier New", monospace;
    font-size: 11px;
    letter-spacing: 0.4em;
    text-transform: uppercase;
    margin-bottom: 48px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
  }}
  th, td {{
    text-align: left;
    padding: 16px 12px;
    border-bottom: 1px solid rgba(232,232,232,0.1);
  }}
  th {{
    font-family: "Courier New", monospace;
    font-size: 10px;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: var(--muted);
    font-weight: 400;
  }}
  td.title {{
    font-family: "Times New Roman", Georgia, serif;
    font-size: 20px;
  }}
  td.title a {{ color: var(--ink); text-decoration: none; }}
  td.title a:hover {{ color: var(--accent); }}
  td.status {{ color: var(--muted); font-family: "Courier New", monospace; font-size: 11px; letter-spacing: 0.18em; text-transform: uppercase; }}
  .empty {{
    padding: 80px 20px;
    text-align: center;
    color: var(--muted);
    font-style: italic;
  }}
  footer {{
    margin-top: 60px;
    text-align: center;
    color: var(--muted);
    font-family: "Courier New", monospace;
    font-size: 10px;
    letter-spacing: 0.3em;
    text-transform: uppercase;
  }}
</style>
</head>
<body>
<div class="wrap">
  <a class="back" href="index.html">&larr; SLAYBILL</a>
  <h1>Archive</h1>
  <div class="sub">Closed &middot; Cancelled &middot; Off the boards</div>
{BODY}
  <footer>Generated {GENERATED}</footer>
</div>
</body>
</html>
"""


def build() -> None:
    data = json.loads(SHOWS_JSON.read_text())
    closed = [
        s for s in data["shows"]
        if s.get("status") in ("closed", "closed_early", "cancelled")
    ]
    closed.sort(key=lambda s: s.get("closing_date") or "9999-99-99", reverse=True)

    if not closed:
        body = '  <div class="empty">No shows in the archive yet.</div>'
    else:
        rows = [
            "  <table>",
            "    <thead><tr>"
            "<th>Show</th><th>Theatre</th><th>Opened</th><th>Closed</th><th>Status</th>"
            "</tr></thead>",
            "    <tbody>",
        ]
        for s in closed:
            rows.append(
                "      <tr>"
                f'<td class="title"><a href="shows/{html.escape(s["slug"])}.html">{html.escape(s["title"])}</a></td>'
                f'<td>{html.escape(s.get("theatre", "—"))}</td>'
                f'<td>{html.escape(s.get("opening_date") or "—")}</td>'
                f'<td>{html.escape(s.get("closing_date") or "—")}</td>'
                f'<td class="status">{html.escape(s["status"])}</td>'
                "</tr>"
            )
        rows.append("    </tbody>")
        rows.append("  </table>")
        body = "\n".join(rows)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        PAGE.format(
            BODY=body,
            GENERATED=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
    )
    print(f"archive.html written: {len(closed)} row(s)")


if __name__ == "__main__":
    build()
