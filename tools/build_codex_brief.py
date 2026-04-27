"""Build a self-contained Codex review brief that bundles all SLAYBILL code-to-date.

Output: CODEX-REVIEW-BRIEF.md at the repo root.
Run from repo root: python3 tools/build_codex_brief.py
"""

from datetime import date
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
PRO_ROOT = ROOT.parent / "slaybill-pro"
OUT = ROOT / "CODEX-REVIEW-BRIEF.md"

# Files to include in full. Order matters — review order matches this.
INCLUDE = [
    # Front-end
    ("FAN", "web/index.html"),
    ("FAN", "web/shows/_template.html"),
    ("FAN", "web/fantasy.html"),
    ("FAN", "web/archive.html"),
    ("FAN", "web/assets/js/data-resolver.js"),
    ("FAN", "web/assets/js/upgrade-nudge.js"),
    ("FAN", "web/config/tier.json"),
    ("PRO", "web/config/tier.json"),
    # Builders (data → static pages)
    ("FAN", "builders/build_live_shows.py"),
    ("FAN", "builders/build_show_pages.py"),
    ("FAN", "builders/build_archive.py"),
    ("FAN", "builders/classify_status.py"),
    # Scrapers (web → SQLite)
    ("FAN", "scrapers/playbill_grosses.py"),
    ("FAN", "scrapers/playbill_news.py"),
    ("FAN", "scrapers/broadway_world.py"),
    # Tools
    ("FAN", "tools/signal_checker.py"),
    # Data layer
    ("FAN", "data/schema.sql"),
    ("FAN", "data/status.json"),
    # Project meta
    ("FAN", "Makefile"),
    ("FAN", "README.md"),
    ("FAN", ".gitignore"),
]

LANG_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".json": "json",
    ".html": "html",
    ".sql": "sql",
    ".md": "markdown",
}


def fence_lang(path: str) -> str:
    suffix = Path(path).suffix
    if Path(path).name == "Makefile":
        return "makefile"
    if Path(path).name == ".gitignore":
        return ""
    return LANG_MAP.get(suffix, "")


def read_file(repo: str, rel: str) -> str:
    base = ROOT if repo == "FAN" else PRO_ROOT
    return (base / rel).read_text()


def shows_sample() -> str:
    """Return a compact sample of shows.json: schema + 2 entries (1 Broadway + 1 OB)."""
    full = json.loads((ROOT / "data" / "shows.json").read_text())
    shows = full["shows"]
    bway = next(s for s in shows if s.get("tier") == "broadway")
    ob = next(s for s in shows if s.get("tier") == "off_broadway")
    sample = {
        "_doc": "FULL FILE has 52 shows (40 Broadway + 12 Off-Broadway). 2 representative entries shown.",
        "_full_size_kb": round((ROOT / "data" / "shows.json").stat().st_size / 1024, 1),
        "_show_count": len(shows),
        "shows": [bway, ob],
    }
    return json.dumps(sample, indent=2)


PREAMBLE = f"""# CODEX REVIEW BRIEF — SLAYBILL

**Generated:** {date.today().isoformat()}
**Repo:** `~/AI-Workspace/01_Projects/slaybill/` (Fan tier) + `slaybill-pro/` (Pro tier, identical except `web/config/tier.json`)
**Reviewer mission:** Find bugs, security issues, missing data, broken contracts, and unreviewed assumptions across the codebase below.

---

## What this is

A static Broadway + Off-Broadway show tracker. Vanilla HTML/CSS/JS front-end, Python scrapers + builders, SQLite for raw scraped data, JSON for the curated source of truth. No framework, no bundler. v3 splits into two repos:
- **Fan** — free, for the user's marketing-firm teammates. Reads from local data only, with optional fallback to Pro's published cache.
- **Pro** — paid (single user — Austin). Same code; reads/writes a public CDN cache and runs LLM-driven editorial agents (not yet implemented).

## What you (Codex) need to do

1. **Read every file in the bundle below.** Treat them as a single project.
2. **Surface bugs.** Logic errors, runtime crashes, race conditions, edge cases unhandled. Cite file + line.
3. **Surface security issues.** Hardcoded secrets, SSRF risk in scrapers, unsanitized HTML injection in builders, XSS in front-end, command injection in subprocess calls.
4. **Surface contract violations.** When file A produces data that file B consumes, flag any mismatch in shape, types, or assumptions.
5. **Surface missing-information gaps.** What data does the app *promise* (in HTML/template) that isn't actually being supplied by the data layer? What error states would crash the page silently?
6. **Surface design-rule violations** (the rules below).
7. **Be specific.** "Could be cleaner" is noise. "Line 47 of build_show_pages.py crashes when palette has fewer than 5 colors" is signal.

## Design rules to enforce

These are explicit decisions. Flag any code that violates them.

| # | Rule | Why |
|---|---|---|
| 1 | Palette format in `data/shows.json` MUST be 5 hex strings (`#rrggbb`). NOT OKLCH strings. | `build_show_pages.py::_parse_hex` chokes on `oklch(...)` syntax. |
| 2 | `web/data/shows_live.json` is generated and gitignored. Never commit it. | It's regenerated from `data/shows.json` on every build. |
| 3 | Scrapers use `PROJECT_ROOT = Path(__file__).resolve().parents[1]`. NOT `parents[2]`. | Old `parents[2]` was the ACLI-nested layout; the standalone repo uses `parents[1]`. |
| 4 | Front-end fetches `config/tier.json` relative to served tree. NOT from repo root. | Static-host friendly. |
| 5 | `<script type="module">` is required wherever `data-resolver.js` or `upgrade-nudge.js` is imported. | They use ES module syntax. |
| 6 | `shows_live.json` schema MUST be `{{ buckets: {{coming_soon, in_previews, live, closed}}, off_broadway }}`. | Front-end depends on this exact shape. |
| 7 | Brand-severance: zero references to `chorus`, `acli`, `archer`, `tier3-playbill-scraper`, `writesprague`. | This was extracted from a private parent repo; brand must stay severed. |
| 8 | Container queries on `.show-card` (`container-type: inline-size`) MUST stay. | HADESTOWN-fits-no-mid-word-wrap depends on it. |
| 9 | `BROADWAY_VENUES` list in `build_live_shows.py` is longest-first match. | Adding a venue means inserting at correct position. |
| 10 | API keys live in macOS Keychain, never in code. | Scrapers/notifiers must use `security find-generic-password` to fetch. |
| 11 | Pro tier never shows the upgrade-nudge UI; Fan tier never shows the spend-warning UI. | Per `web/config/tier.json` flags. |
| 12 | OS dark mode + Coming Soon bucket: bg shifts to `oklch(96% 0.005 95)` paper-cream. | Don't break that. |

## Decisions already made (do NOT suggest reverting these)

| # | Decision |
|---|---|
| 1 | Vanilla static site. No React/Vue/Svelte. No build step beyond Python. |
| 2 | Three lifecycle buckets on home page (Coming Soon · In Previews · Live), each with its own bucket color theme. |
| 3 | Off-Broadway shown as a horizontal-scroll row at 50% saturation, below the three buckets. |
| 4 | Fan/Pro split is two separate repos, NOT a feature flag in one repo. |
| 5 | Pro pushes `shows_live.json` to a public CDN; Fan pulls from CDN OR falls back to local scrape. |
| 6 | `data-resolver.js` is the only path the front-end uses to fetch shows data. |
| 7 | `upgrade-nudge.js` injects ONE nudge per session per show, dismissible, localStorage-tracked. |
| 8 | Each show has a 5-color palette; Tier 2 detail pages render in those colors via `{{{{C1}}}}–{{{{C5}}}}` template tokens. |
| 9 | post-glass-liquid design: Fraunces+Inter, OKLCH color tokens in CSS (not in shows.json), edge-lit borders, no backdrop-filter on the home page. |
| 10 | `<button>` (not `<div>`) is used for keyboard-accessible interactive elements (e.g., Fantasy Broadway draft picks). |

## Known gaps (find OTHER gaps, not these)

These are tracked in the session handoff. You don't need to surface them; surface what's NOT here.

- No `poster_url` field on shows — palettes were LLM-set, not extracted from real poster art. Per-show poster-skin pipeline is unbuilt.
- `slaybill/digest/build_fan_digest.py` does not exist yet (Fan weekly digest builder).
- `slaybill-pro/pro/cache/publish.py` does not exist yet (CDN upload).
- `slaybill-pro/pro/agents/editorial_research.py` + `editorial_digest.py` do not exist yet (LLM editorial pipeline).
- `slaybill-pro/pro/notify/spend_warning.py` does not exist yet (Mon 10am ET pre-spend notification).
- Pro repo is not yet `git init`'d.
- No remote configured on either repo (no GitHub push yet).
- No Cloudflare/Vercel/Netlify deploy configured.
- No CI.
- Fan v3 changes are uncommitted on `main` branch of Fan repo.

## Architecture (text diagram)

```
Source of truth (curated):  data/shows.json (52 shows, hand-curated)
                                   |
                                   v
                  python builders/build_live_shows.py
                                   |
                                   v
                        web/data/shows_live.json   ← gitignored, served
                                   |
                                   v
                        web/index.html  (3 buckets + OB row)
                              + per-show Tier 2 pages from build_show_pages.py
                              + web/archive.html for closed shows

Live data (scrapers, future):
   playbill.com/grosses   ─┐
   playbill.com/news       ├─→  scrapers/*.py  →  data/corpus.db (SQLite, gitignored)
   broadwayworld.com      ─┘                        │
                                                    │
                                          tools/signal_checker.py
                                                    │
                                                    v
                                       (eventually merges into shows.json refresh)

Tier resolution (run-time, browser):
   web/config/tier.json
        │
        v
   web/assets/js/data-resolver.js
        ├─→ if Pro: skip CDN, read web/data/shows_live.json directly
        └─→ if Fan: try Pro CDN → fall back to web/data/shows_live.json → fall back to localStorage
```

## File index (what's in the bundle below, in review order)

The code bundle below contains these files in order. Each is delimited by a `### FILE: <path>` header.

"""

# Build the file index table
file_index_lines = ["| # | Repo | Path | Purpose |", "|---|---|---|---|"]
purposes = {
    "web/index.html": "Home page · 3 buckets + OB row + tier chip + banners",
    "web/shows/_template.html": "Tier 2 detail page template (per-show palette via {{C1}}-{{C5}})",
    "web/fantasy.html": "Fantasy Broadway draft game (4-show pick, weekly scoring)",
    "web/archive.html": "Generated list of closed shows",
    "web/assets/js/data-resolver.js": "Tier-aware fetch chain: Pro CDN → local → localStorage",
    "web/assets/js/upgrade-nudge.js": "Fan-only contextual upsell panels for Tier 2 pages",
    "web/config/tier.json": "Tier flags (which UI to show, where the Pro CDN lives)",
    "builders/build_live_shows.py": "shows.json → web/data/shows_live.json (bucket assignment, OB split)",
    "builders/build_show_pages.py": "shows.json + _template.html → 52 Tier 2 pages",
    "builders/build_archive.py": "shows.json → web/archive.html for closed shows",
    "builders/classify_status.py": "Back-propagates events.table → shows.status (6-rule classifier)",
    "scrapers/playbill_grosses.py": "Weekly Broadway grosses scraper → SQLite",
    "scrapers/playbill_news.py": "Playbill news article scraper → SQLite",
    "scrapers/broadway_world.py": "BroadwayWorld scraper → SQLite",
    "tools/signal_checker.py": "Reads SQLite + flags shows trending up/down",
    "data/schema.sql": "SQLite schema for corpus.db",
    "data/status.json": "Show-status enum + transition rules",
    "Makefile": "Build/scrape/serve targets",
    "README.md": "Repo intro",
    ".gitignore": "Ignored paths (corpus.db, web/data/, .env)",
}
for i, (repo, rel) in enumerate(INCLUDE, 1):
    purpose = purposes.get(rel, "—")
    file_index_lines.append(f"| {i} | {repo} | `{rel}` | {purpose} |")

file_index_md = "\n".join(file_index_lines)

# Build the data sample section
data_sample_md = f"""

### FILE: data/shows.json (SAMPLE — full file is 92 KB / 52 shows)

```json
{shows_sample()}
```

"""

# Build code bundle
bundle_parts = []
for repo, rel in INCLUDE:
    try:
        body = read_file(repo, rel)
    except FileNotFoundError:
        body = f"<<<MISSING FILE: {repo}/{rel}>>>"
    lang = fence_lang(rel)
    label = f"slaybill-pro/{rel}" if repo == "PRO" else rel
    bundle_parts.append(f"\n### FILE: {label}\n\n```{lang}\n{body}\n```\n")

ACCEPTANCE = """

---

## Acceptance criteria (what a good Codex review looks like)

A good review is a markdown report with these sections:

1. **CRITICAL bugs** — runtime crashes, security holes, data loss. Each item: file:line, what fails, what to do.
2. **HIGH-confidence bugs** — wrong logic, broken contracts, edge cases that will hit real users.
3. **MEDIUM** — likely problems where you want a human eye.
4. **LOW / nits** — style, dead code, minor cleanups (keep this section short).
5. **Missing information / data gaps** — fields the app uses that aren't supplied; templates with no data path; scrapers that don't write what builders read.
6. **Contract violations** — A produces, B consumes, they disagree.
7. **Design-rule violations** — anything that breaks the table above.
8. **Open questions for Austin** — things that aren't bugs but where the intent is unclear.

Do NOT include:
- Generic "consider adding tests" advice (we know).
- Suggestions to add a framework (we won't).
- Comments on the empty Pro `agents/cache/notify/digest/` dirs (those are tracked gaps).
- Style nits on the HTML inline `<style>` blocks (intentional — no build step).
- Suggestions to revert any of the "Decisions already made" above.

Output format: a single markdown file. Title: `SLAYBILL — Codex Review {date_today}`. Cite every finding with `path:line`.

---

## CODE BUNDLE

""".replace("{date_today}", date.today().isoformat())

# Compose the full document
full = PREAMBLE + file_index_md + data_sample_md + ACCEPTANCE + "".join(bundle_parts)
OUT.write_text(full)

print(f"Wrote {OUT}")
print(f"Size: {OUT.stat().st_size / 1024:.1f} KB")
print(f"Lines: {len(full.splitlines())}")
print(f"Files bundled: {len(INCLUDE)}")
