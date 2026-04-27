# CODEX REVIEW BRIEF — SLAYBILL

**Generated:** 2026-04-25
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
| 6 | `shows_live.json` schema MUST be `{ buckets: {coming_soon, in_previews, live, closed}, off_broadway }`. | Front-end depends on this exact shape. |
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
| 8 | Each show has a 5-color palette; Tier 2 detail pages render in those colors via `{{C1}}–{{C5}}` template tokens. |
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

| # | Repo | Path | Purpose |
|---|---|---|---|
| 1 | FAN | `web/index.html` | Home page · 3 buckets + OB row + tier chip + banners |
| 2 | FAN | `web/shows/_template.html` | Tier 2 detail page template (per-show palette via {{C1}}-{{C5}}) |
| 3 | FAN | `web/fantasy.html` | Fantasy Broadway draft game (4-show pick, weekly scoring) |
| 4 | FAN | `web/archive.html` | Generated list of closed shows |
| 5 | FAN | `web/assets/js/data-resolver.js` | Tier-aware fetch chain: Pro CDN → local → localStorage |
| 6 | FAN | `web/assets/js/upgrade-nudge.js` | Fan-only contextual upsell panels for Tier 2 pages |
| 7 | FAN | `web/config/tier.json` | Tier flags (which UI to show, where the Pro CDN lives) |
| 8 | PRO | `web/config/tier.json` | Tier flags (which UI to show, where the Pro CDN lives) |
| 9 | FAN | `builders/build_live_shows.py` | shows.json → web/data/shows_live.json (bucket assignment, OB split) |
| 10 | FAN | `builders/build_show_pages.py` | shows.json + _template.html → 52 Tier 2 pages |
| 11 | FAN | `builders/build_archive.py` | shows.json → web/archive.html for closed shows |
| 12 | FAN | `builders/classify_status.py` | Back-propagates events.table → shows.status (6-rule classifier) |
| 13 | FAN | `scrapers/playbill_grosses.py` | Weekly Broadway grosses scraper → SQLite |
| 14 | FAN | `scrapers/playbill_news.py` | Playbill news article scraper → SQLite |
| 15 | FAN | `scrapers/broadway_world.py` | BroadwayWorld scraper → SQLite |
| 16 | FAN | `tools/signal_checker.py` | Reads SQLite + flags shows trending up/down |
| 17 | FAN | `data/schema.sql` | SQLite schema for corpus.db |
| 18 | FAN | `data/status.json` | Show-status enum + transition rules |
| 19 | FAN | `Makefile` | Build/scrape/serve targets |
| 20 | FAN | `README.md` | Repo intro |
| 21 | FAN | `.gitignore` | Ignored paths (corpus.db, web/data/, .env) |

### FILE: data/shows.json (SAMPLE — full file is 92 KB / 52 shows)

```json
{
  "_doc": "FULL FILE has 52 shows (40 Broadway + 12 Off-Broadway). 2 representative entries shown.",
  "_full_size_kb": 92.4,
  "_show_count": 52,
  "shows": [
    {
      "slug": "harry-potter-and-the-cursed-child",
      "title": "Harry Potter and the Cursed Child",
      "subtitle": "",
      "tier": "broadway",
      "category": "play",
      "theatre": "Lyric Theatre",
      "theatre_capacity": 1930,
      "first_preview_date": "2022-02-22",
      "opening_date": "2022-04-22",
      "closing_date": null,
      "status": "live",
      "synopsis": "The eighth story in the Harry Potter saga follows a middle-aged Harry, now an overworked employee at the Ministry of Magic, and his younger son Albus who struggles with his famous family legacy. Together they embark on a time-traveling adventure that threatens to unravel the past and future.",
      "cast": [
        {
          "name": "_note",
          "role": "Current cast unverified \u2014 rotating leads as of April 2026"
        }
      ],
      "creatives": [
        {
          "name": "Jack Thorne",
          "role": "Playwright (based on story by J.K. Rowling, John Tiffany, Jack Thorne)"
        },
        {
          "name": "John Tiffany",
          "role": "Director"
        },
        {
          "name": "Steven Hoggett",
          "role": "Movement"
        }
      ],
      "producers": [
        "Sonia Friedman Productions",
        "Colin Callender",
        "Harry Potter Theatrical Productions"
      ],
      "avg_ticket_usd": 183.8,
      "capacity_pct": 99.74,
      "weekly_gross_usd": 2378782,
      "palette": [
        "#52c5bc",
        "#283d3b",
        "#e8eceb",
        "#a0444c",
        "#181a1a"
      ],
      "ticket_links": {
        "telecharge": "https://www.telecharge.com/Broadway/Harry-Potter-and-the-Cursed-Child/Overview",
        "todaytix": "https://www.todaytix.com/nyc/shows/harry-potter-and-the-cursed-child",
        "official": "https://www.harrypottertheplay.com/us/"
      }
    },
    {
      "slug": "heathers-the-musical",
      "title": "Heathers: The Musical",
      "subtitle": "",
      "tier": "off_broadway",
      "category": "musical",
      "theatre": "New World Stages",
      "theatre_capacity": 499,
      "first_preview_date": "2025-06-22",
      "opening_date": "2025-07-10",
      "closing_date": "2026-09-06",
      "status": "live",
      "synopsis": "Outcast Veronica Sawyer is taken under the wing of the three Heathers, the most powerful clique at Westerberg High \u2014 until she falls for the dangerous outsider J.D. and their dark pact begins. Based on the 1988 cult film, this revival transferred from London's West End where it won the WhatsOnStage Award for Best Musical Revival.",
      "cast": [
        {
          "name": "Kuhoo Verma",
          "role": "Veronica Sawyer"
        },
        {
          "name": "Casey Likes",
          "role": "J.D."
        },
        {
          "name": "Peyton List",
          "role": "Heather Chandler"
        }
      ],
      "creatives": [
        {
          "name": "Kevin Murphy & Laurence O'Keefe",
          "role": "Book, Music & Lyrics"
        },
        {
          "name": "Andy Fickman",
          "role": "Director"
        }
      ],
      "producers": [
        "Bill Kenwright Ltd.",
        "Paul Taylor-Mills"
      ],
      "avg_ticket_usd": 210,
      "capacity_pct": 95.0,
      "weekly_gross_usd": 520000,
      "palette": [
        "#3b84dc",
        "#d2872c",
        "#202c3b",
        "#7570db",
        "#eeeff1"
      ],
      "ticket_links": {
        "todaytix": "https://www.todaytix.com/nyc/shows/heathers-the-musical",
        "official": "https://heathersthemusical.com/new-york/"
      }
    }
  ]
}
```



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

Output format: a single markdown file. Title: `SLAYBILL — Codex Review 2026-04-25`. Cite every finding with `path:line`.

---

## CODE BUNDLE


### FILE: web/index.html

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SLAYBILL — Broadway, Off-Broadway, what they're worth</title>
<meta name="description" content="SLAYBILL — the Broadway guide that tracks what's opening, what's running, and what it's all grossing.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,200..900;1,9..144,200..900&family=Inter:wght@300..800&family=Instrument+Serif&display=swap">
<style>
  /* SLAYBILL design system — post-glass-liquid 2026.
   * Fraunces (display, variable opsz/wght/WONK) + Inter (UI) replace
   * Times New Roman + Courier. OKLCH tokens, edge-lit borders, no
   * backdrop-filter on cards. Three buckets get distinct themes via
   * data-theme on each <section.bucket>. */
  :root {
    color-scheme: dark light;

    --font-display: 'Fraunces', Georgia, serif;
    --font-ui:      'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    --font-stamp:   'Instrument Serif', 'Times New Roman', serif;
    --font-mono:    'Courier New', monospace;

    /* Core OKLCH palette */
    --yellow:   oklch(86% 0.22 95);
    --ink:      oklch(12% 0.01 270);
    --cream:    oklch(96% 0.01 95);
    --red:      oklch(48% 0.22 27);
    --gold:     oklch(80% 0.19 85);
    --violet:   oklch(72% 0.18 290);
    --cyan:     oklch(78% 0.13 220);

    /* Surfaces */
    --surface-0: oklch(8% 0.02 270);
    --surface-1: oklch(11% 0.025 270);
    --surface-2: oklch(15% 0.03 270);
    --surface-border: oklch(22% 0.04 270);

    /* Easing */
    --ease-out-expo:   cubic-bezier(0.16, 1, 0.3, 1);
    --ease-spring:     cubic-bezier(0.34, 1.56, 0.64, 1);
    --ease-in-out-cub: cubic-bezier(0.65, 0, 0.35, 1);

    --dur-fast:    200ms;
    --dur-medium:  350ms;
    --dur-slow:    600ms;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; }
  @media (prefers-reduced-motion: no-preference) {
    html { scroll-behavior: smooth; }
  }
  body {
    background: var(--surface-0);
    color: var(--cream);
    font-family: var(--font-ui);
    font-feature-settings: "ss01" 1, "cv05" 1;
    min-height: 100vh;
    padding: 32px 20px 80px;
    display: flex; flex-direction: column; align-items: center; gap: 56px;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
  }
  ::selection { background: color-mix(in oklch, var(--gold) 35%, transparent); color: var(--cream); }

  /* Theatrical focus rings — visible on every interactive element. */
  :focus-visible {
    outline: 2px solid var(--gold);
    outline-offset: 3px;
    border-radius: 4px;
  }
  :focus:not(:focus-visible) { outline: none; }

  /* Scroll-jostle: black text shifts opposite scroll direction, eases back. */
  .jostle {
    display: inline-block;
    will-change: transform;
    transition: transform .45s var(--ease-out-expo);
  }
  body.scroll-down .jostle { transform: translateY(-3px); }
  body.scroll-up   .jostle { transform: translateY(3px); }
  body.scroll-down .cover .jostle:nth-of-type(2n) { transform: translateY(-4px); }
  body.scroll-up   .cover .jostle:nth-of-type(2n) { transform: translateY(4px); }

  /* SLAYBILL yellow cover. */
  .cover {
    width: 100%; max-width: 480px;
    background: var(--yellow);
    color: var(--ink);
    box-shadow:
      0 30px 80px oklch(0% 0 0 / 0.6),
      0 0 0 1px oklch(0% 0 0 / 0.1);
    padding: 28px 32px 24px;
    display: grid;
    gap: 16px;
    position: relative;
    font-family: var(--font-display);
  }
  .masthead {
    border-top: 4px solid var(--ink);
    border-bottom: 4px solid var(--ink);
    padding: 12px 0 10px;
    text-align: center;
  }
  .masthead .word {
    font-family: var(--font-display);
    font-size: clamp(46px, 9.4vw + 4px, 74px);
    font-variation-settings: 'wght' 900, 'opsz' 72, 'WONK' 1;
    letter-spacing: -0.04em;
    line-height: 0.86;
    text-rendering: optimizeLegibility;
  }
  .masthead .sub {
    font-family: var(--font-ui);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.36em;
    margin-top: 8px;
    text-transform: uppercase;
    opacity: 0.78;
  }
  .tagline {
    text-align: center;
    font-family: var(--font-display);
    font-style: italic;
    font-variation-settings: 'wght' 320, 'opsz' 14, 'WONK' 0;
    font-size: clamp(14px, 1.5vw + 8px, 17px);
    line-height: 1.45;
    letter-spacing: 0.005em;
    margin: 0;
  }
  .superstition {
    border-top: 1px dashed oklch(0% 0 0 / 0.3);
    border-bottom: 1px dashed oklch(0% 0 0 / 0.3);
    padding: 10px 8px;
    text-align: center;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    line-height: 1.55;
  }
  .superstition .warn {
    /* Darkened from #c3102f to clear WCAG AA on yellow ground. */
    color: oklch(38% 0.22 27);
    font-weight: 900;
    letter-spacing: 0.32em;
  }
  footer.cover-foot {
    border-top: 2px solid var(--ink);
    padding-top: 12px;
    font-size: 10px;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    display: flex; justify-content: space-between;
    font-family: var(--font-mono);
  }
  .dog-ear {
    position: absolute; top: 0; right: 0;
    width: 38px; height: 38px;
    background: linear-gradient(225deg, oklch(0% 0 0 / 0.08) 0%, oklch(0% 0 0 / 0.08) 50%, transparent 50%);
  }

  /* Buckets — three lifecycle modules with distinct themes. */
  .bucket {
    width: 100%; max-width: 1200px;
    padding: 30px 26px 34px;
    border-radius: 18px;
    background: var(--bucket-bg, var(--surface-1));
    color: var(--bucket-ink, var(--cream));
    transition: background var(--dur-medium) var(--ease-in-out-cub);
  }
  .bucket header {
    display: flex; justify-content: space-between; align-items: baseline;
    gap: 16px;
    margin-bottom: 22px;
    flex-wrap: wrap;
  }
  .bucket h2 {
    font-family: var(--font-stamp);
    font-weight: 400;
    font-size: clamp(30px, 3.5vw + 12px, 48px);
    letter-spacing: -0.02em;
    text-transform: uppercase;
    margin: 0;
    line-height: 0.95;
    text-wrap: balance;
  }
  .bucket .bucket-note {
    font-family: var(--font-ui);
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    opacity: 0.7;
    text-align: right;
  }

  /* Theme: Coming Soon — paper, monochrome.
   * In OS dark mode, drop to a pale grey instead of pure white. */
  .bucket[data-theme="coming"] {
    --bucket-bg: oklch(96% 0.005 95);
    --bucket-ink: oklch(15% 0.01 270);
    --bucket-accent: oklch(15% 0.01 270);
    --poster-filter: grayscale(1) contrast(1.05);
  }

  /* Theme: In Previews — yellow on black, duotone posters. */
  .bucket[data-theme="previews"] {
    --bucket-bg: oklch(10% 0.01 270);
    --bucket-ink: oklch(86% 0.22 95);
    --bucket-accent: oklch(86% 0.22 95);
    --poster-filter: sepia(0.7) saturate(3) hue-rotate(-10deg) brightness(0.95);
  }

  /* Theme: Live — full color, current scheme. */
  .bucket[data-theme="live"] {
    --bucket-bg: oklch(11% 0.025 270);
    --bucket-ink: var(--cream);
    --bucket-accent: oklch(70% 0.22 350);
    --poster-filter: none;
  }

  /* Card grid. */
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;
  }
  @media (max-width: 760px) { .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  @media (max-width: 420px) { .grid { grid-template-columns: 1fr; } }

  /* Card — container query host so titles fit without mid-word wraps. */
  a.show-card {
    container-type: inline-size;
    container-name: card;
    display: flex; flex-direction: column; gap: 10px;
    text-decoration: none;
    color: inherit;
    border-radius: 14px;
    padding: 14px;
    min-width: 0;
    overflow: hidden;
    /* Edge-lit border via two-layer background — no rgba border. */
    border: 1px solid transparent;
    background-image:
      linear-gradient(color-mix(in oklch, var(--bucket-bg) 88%, var(--bucket-ink) 5%),
                      color-mix(in oklch, var(--bucket-bg) 88%, var(--bucket-ink) 5%)),
      linear-gradient(135deg,
        color-mix(in oklch, var(--bucket-accent) 50%, transparent) 0%,
        transparent 50%,
        color-mix(in oklch, var(--bucket-accent) 18%, transparent) 100%
      );
    background-origin: border-box;
    background-clip: padding-box, border-box;
    transition:
      box-shadow var(--dur-fast) var(--ease-spring),
      translate var(--dur-fast) var(--ease-spring);
  }
  a.show-card:hover, a.show-card:focus-visible {
    translate: 0 -4px;
    box-shadow:
      0 20px 48px oklch(0% 0 0 / 0.35),
      0 0 0 1px color-mix(in oklch, var(--bucket-accent) 35%, transparent);
  }

  /* Poster: palette-gradient fallback + optional real image. */
  .poster {
    aspect-ratio: 3 / 4;
    border-radius: 10px;
    overflow: hidden;
    position: relative;
    filter: var(--poster-filter);
    background: oklch(15% 0.01 270);
  }
  .poster .palette-bg {
    position: absolute; inset: 0;
    background: linear-gradient(135deg, var(--p1, oklch(45% 0.05 270)), var(--p2, oklch(30% 0.04 270)) 55%, var(--p3, oklch(20% 0.03 270)));
  }
  .poster .palette-accent {
    position: absolute; inset: 0;
    background: radial-gradient(circle at 28% 18%, var(--p4, oklch(60% 0.10 270)) 0%, transparent 55%);
    opacity: 0.55;
  }
  .poster img {
    position: absolute; inset: 0;
    width: 100%; height: 100%;
    object-fit: cover;
    display: block;
  }
  .poster .stamp {
    position: absolute; inset: auto 0 14px 0;
    text-align: center;
    font-family: var(--font-stamp);
    font-weight: 400;
    color: var(--p5, white);
    letter-spacing: -0.01em;
    padding: 0 14px;
    text-transform: uppercase;
    font-size: clamp(14px, 6cqw, 32px);
    line-height: 0.95;
    word-break: keep-all;
    overflow-wrap: break-word;
    text-wrap: balance;
    mix-blend-mode: overlay;
  }

  /* Title — container-query-sized so HADESTOWN fits without mid-word wrap. */
  .show-card .title {
    font-family: var(--font-display);
    font-variation-settings: 'wght' 800, 'opsz' 24, 'WONK' 1;
    font-size: clamp(15px, 8.5cqw, 22px);
    line-height: 1;
    letter-spacing: -0.018em;
    text-transform: uppercase;
    word-break: keep-all;
    hyphens: none;
    text-wrap: balance;
    min-height: calc(2 * 1em);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .show-card .venue {
    font-family: var(--font-ui);
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    opacity: 0.72;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .metrics {
    display: flex; flex-wrap: wrap; gap: 4px 10px;
    font-family: var(--font-ui);
    font-feature-settings: "tnum" 1;
    font-variant-numeric: tabular-nums;
    font-size: 11px;
    font-weight: 500;
    opacity: 0.85;
  }
  .metrics .m { white-space: nowrap; }
  .metrics .m.pending { opacity: 0.45; font-style: italic; font-weight: 400; }

  .scores {
    display: flex; gap: 12px;
    font-family: var(--font-ui);
    font-feature-settings: "tnum" 1;
    font-variant-numeric: tabular-nums;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.04em;
    opacity: 0.66;
  }
  .scores .s.pending { opacity: 0.45; }

  .pill {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 4px 10px;
    border-radius: 6px;
    background: color-mix(in oklch, var(--bucket-accent) 12%, transparent);
    border: 1px solid color-mix(in oklch, var(--bucket-accent) 32%, transparent);
    color: var(--bucket-accent);
    font-family: var(--font-ui);
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    width: fit-content;
  }

  /* Off-Broadway horizontal scroll row. */
  .ob-row {
    width: 100%; max-width: 1200px;
  }
  .ob-row header {
    display: flex; justify-content: space-between; align-items: baseline;
    margin: 0 4px 12px;
  }
  .ob-row h2 {
    font-family: var(--font-stamp);
    font-weight: 400;
    font-size: clamp(24px, 2.4vw + 10px, 32px);
    letter-spacing: -0.01em;
    text-transform: uppercase;
    margin: 0;
    color: var(--cream);
    opacity: 0.9;
  }
  .ob-row .note {
    font-family: var(--font-ui);
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    opacity: 0.55;
  }
  .ob-track {
    display: flex;
    gap: 12px;
    overflow-x: auto;
    padding: 4px 4px 16px;
    scroll-snap-type: x mandatory;
    scrollbar-width: thin;
    scrollbar-color: oklch(35% 0.04 270) transparent;
  }
  .ob-track::-webkit-scrollbar { height: 8px; }
  .ob-track::-webkit-scrollbar-thumb { background: oklch(35% 0.04 270); border-radius: 4px; }
  .ob-card {
    flex: 0 0 168px;
    scroll-snap-align: start;
    filter: saturate(0.5);
    container-type: inline-size;
    container-name: obcard;
    --bucket-bg: var(--surface-1);
    --bucket-ink: var(--cream);
    --bucket-accent: oklch(60% 0.06 270);
  }
  .ob-card .title { font-size: clamp(13px, 9cqw, 18px); }

  /* Skeleton loaders. */
  @property --shimmer-x {
    syntax: '<percentage>'; inherits: false; initial-value: -100%;
  }
  .skeleton-card {
    aspect-ratio: 3 / 4;
    border-radius: 12px;
    background: var(--surface-1);
    border: 1px solid var(--surface-border);
    overflow: hidden;
    position: relative;
  }
  .skeleton-card::after {
    content: '';
    position: absolute; inset: 0;
    background: linear-gradient(90deg,
      transparent 0%,
      color-mix(in oklch, var(--bucket-ink, var(--cream)) 8%, transparent) 50%,
      transparent 100%
    );
    transform: translateX(var(--shimmer-x));
    animation: shimmer 1.6s linear infinite;
  }
  @keyframes shimmer {
    from { --shimmer-x: -100%; }
    to   { --shimmer-x:  200%; }
  }

  /* Visible fetch error (CRIT a11y fix). */
  .fetch-error {
    width: 100%;
    padding: 18px 20px;
    border-radius: 12px;
    background: color-mix(in oklch, var(--red) 12%, transparent);
    border: 1px solid color-mix(in oklch, var(--red) 40%, transparent);
    color: var(--cream);
    font-family: var(--font-ui);
    font-size: 13px;
    font-weight: 500;
    line-height: 1.5;
    text-align: center;
  }

  /* Secondary nav: Fantasy + Archive. */
  .more {
    width: 100%; max-width: 1200px;
    display: flex; justify-content: center; gap: 14px;
    flex-wrap: wrap;
  }
  .more a {
    display: inline-flex; align-items: center; gap: 12px;
    padding: 14px 22px;
    background: var(--surface-1);
    border: 1px solid var(--surface-border);
    border-radius: 12px;
    color: var(--cream);
    text-decoration: none;
    font-family: var(--font-display);
    font-variation-settings: 'wght' 800, 'opsz' 24, 'WONK' 0;
    font-size: 18px;
    letter-spacing: -0.01em;
    transition: translate var(--dur-fast) var(--ease-spring), border-color var(--dur-fast) var(--ease-spring);
  }
  .more a .badge {
    font-family: var(--font-ui);
    font-size: 9px;
    font-weight: 500;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    opacity: 0.55;
  }
  .more a:hover, .more a:focus-visible {
    translate: 0 -2px;
    border-color: color-mix(in oklch, var(--gold) 60%, transparent);
    outline: none;
  }

  footer.page-foot {
    max-width: 1200px;
    color: oklch(75% 0.02 270);
    text-align: center;
    font-family: var(--font-display);
    font-style: italic;
    font-variation-settings: 'wght' 320, 'opsz' 14;
    font-size: 14px;
  }

  .empty-bucket {
    padding: 30px 10px;
    text-align: center;
    font-family: var(--font-ui);
    font-size: 12px;
    font-weight: 400;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    opacity: 0.45;
    font-style: italic;
  }

  /* Tier badge — subtle floating chip top-right showing data source. */
  .tier-chip {
    position: fixed;
    top: 16px; right: 16px;
    z-index: 50;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-radius: 999px;
    background: color-mix(in oklch, var(--surface-1) 85%, transparent);
    border: 1px solid var(--surface-border);
    font-family: var(--font-ui);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: oklch(78% 0.02 270);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
  }
  .tier-chip::before {
    content: "";
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--gold);
    box-shadow: 0 0 6px var(--gold);
  }
  .tier-chip[data-source="pro_cache"]::before { background: var(--violet); box-shadow: 0 0 6px var(--violet); }
  .tier-chip[data-source="fan_scrape"]::before { background: var(--cyan); box-shadow: 0 0 6px var(--cyan); }
  .tier-chip[data-source="cached"]::before { background: oklch(60% 0.04 270); box-shadow: none; }
  .tier-chip[data-source="error"]::before { background: var(--red); box-shadow: 0 0 6px var(--red); }
  @media (max-width: 640px) {
    .tier-chip { top: 8px; right: 8px; font-size: 9px; padding: 4px 8px; }
  }

  /* Pro spend warning + Fan upgrade banner. */
  .banner {
    width: 100%; max-width: 1200px;
    padding: 14px 18px;
    border-radius: 12px;
    font-family: var(--font-ui);
    font-size: 13px;
    line-height: 1.5;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
  }
  .banner.spend {
    background: color-mix(in oklch, var(--gold) 12%, transparent);
    border: 1px solid color-mix(in oklch, var(--gold) 40%, transparent);
    color: var(--cream);
  }
  .banner.upgrade {
    background: color-mix(in oklch, var(--violet) 14%, transparent);
    border: 1px solid color-mix(in oklch, var(--violet) 38%, transparent);
    color: var(--cream);
  }
  .banner .actions { display: flex; gap: 8px; flex-wrap: wrap; }
  .banner button, .banner a {
    padding: 6px 12px;
    border-radius: 6px;
    background: color-mix(in oklch, var(--cream) 12%, transparent);
    border: 1px solid color-mix(in oklch, var(--cream) 25%, transparent);
    color: var(--cream);
    font-family: inherit;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    text-decoration: none;
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease-out-expo);
  }
  .banner button:hover, .banner a:hover {
    background: color-mix(in oklch, var(--cream) 22%, transparent);
  }
  .banner[hidden] { display: none; }

  @media (prefers-contrast: more) {
    a.show-card {
      background-image: none !important;
      background: var(--surface-1) !important;
      border-color: var(--bucket-ink) !important;
    }
    .pill {
      background: transparent;
      border-color: currentColor;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }
</style>
</head>
<body>

<div class="tier-chip" data-slot="tier-badge" data-source="loading" role="status" aria-live="polite">Loading…</div>

<div class="banner spend" data-slot="spend-banner" hidden role="status" aria-live="polite">
  <span><strong>Editorial scrape runs Tuesday 10am ET.</strong> Estimated cost $5–8.</span>
  <div class="actions">
    <button type="button" data-action="skip-week">Skip this week</button>
    <button type="button" data-action="confirm-spend">Confirm</button>
  </div>
</div>

<div class="banner upgrade" data-slot="upgrade-banner" hidden role="status">
  <span><strong>You're on SLAYBILL Fan.</strong> Pro adds editorial verification, daily price snapshots, and the weekly story digest.</span>
  <div class="actions">
    <a href="#" data-slot="upgrade-link">Upgrade to Pro</a>
    <button type="button" data-action="dismiss-upgrade">Not now</button>
  </div>
</div>

<section class="cover" aria-label="SLAYBILL masthead">
  <div class="masthead">
    <div class="word jostle">SLAYBILL</div>
    <div class="sub jostle">Your show&rsquo;s favorite show guide &middot; Broadway Edition</div>
  </div>
  <p class="tagline jostle">What&rsquo;s on tonight, what&rsquo;s opening soon,<br>and what it&rsquo;s grossing this week.</p>
  <div class="superstition jostle">
    Break a leg &middot; No whistling &middot; Never name the Scottish Play<br>
    <span class="warn">You have been warned.</span>
  </div>
  <footer class="cover-foot">
    <span class="jostle">Vol. 1 &middot; Issue 3</span>
    <span class="jostle">26 Apr 2026</span>
  </footer>
  <div class="dog-ear" aria-hidden="true"></div>
</section>

<section class="bucket" data-theme="coming" data-bucket="coming_soon" aria-labelledby="bk-coming">
  <header>
    <h2 id="bk-coming">Coming Soon</h2>
    <div class="bucket-note">First previews within 6 weeks</div>
  </header>
  <div class="grid" data-slot="grid"></div>
</section>

<section class="bucket" data-theme="previews" data-bucket="in_previews" aria-labelledby="bk-previews">
  <header>
    <h2 id="bk-previews">In Previews</h2>
    <div class="bucket-note">Performing tonight &middot; Opening night TBA</div>
  </header>
  <div class="grid" data-slot="grid"></div>
</section>

<section class="bucket" data-theme="live" data-bucket="live" aria-labelledby="bk-live">
  <header>
    <h2 id="bk-live">Live on Broadway</h2>
    <div class="bucket-note">Curtain&rsquo;s up.</div>
  </header>
  <div class="grid" data-slot="grid"></div>
</section>

<section class="ob-row" aria-labelledby="bk-ob">
  <header>
    <h2 id="bk-ob">Off-Broadway</h2>
    <div class="note">Scroll &rarr;</div>
  </header>
  <div class="ob-track" data-slot="ob-track"></div>
</section>

<nav class="more" aria-label="More">
  <a href="fantasy.html"><span>Fantasy Broadway</span><span class="badge">Four slots &middot; Tonys</span></a>
  <a href="archive.html"><span>Archive</span><span class="badge">Closed &middot; Cancelled</span></a>
</nav>

<footer class="page-foot">SLAYBILL &middot; The boards never lied.</footer>

<template id="card-template">
  <a class="show-card" href="#">
    <span class="pill"></span>
    <div class="poster" role="img">
      <div class="palette-bg" aria-hidden="true"></div>
      <div class="palette-accent" aria-hidden="true"></div>
      <span class="stamp" aria-hidden="true"></span>
    </div>
    <div class="title"></div>
    <div class="venue"></div>
    <div class="metrics" aria-label="Box office summary"></div>
    <div class="scores" aria-label="Critic and audience scores"></div>
  </a>
</template>

<script type="module">
/* SLAYBILL hydration — uses tier-aware data resolver to choose between
 * Pro cache (Fan tier with cache fresh) → local data (Pro tier or cache
 * miss) → localStorage (offline fallback). Renders each bucket + OB row.
 * Skeleton loaders while fetching; visible <div role="alert"> on failure. */
import { resolveShowData, formatTierBadge } from './assets/js/data-resolver.js';

function fmtMoney(n) {
  if (n == null) return null;
  if (n >= 1_000_000) return '$' + (n / 1_000_000).toFixed(2) + 'M/wk';
  if (n >= 1_000)     return '$' + Math.round(n / 1_000) + 'K/wk';
  return '$' + n + '/wk';
}
function fmtPct(p) { return p == null ? null : Math.round(p) + '% cap'; }
function fmtAvg(a) { return a == null ? null : '$' + a + ' avg'; }

function heroCredit(show) {
  const c = (show.creatives || []);
  const byRole = (needle) => c.find(x => (x.role || '').toLowerCase().includes(needle));
  const pick = byRole('music') || byRole('book') || byRole('play') || byRole('director') || c[0];
  return pick ? pick.name : null;
}

function makeCard(show) {
  const tpl = document.getElementById('card-template');
  const frag = tpl.content.cloneNode(true);
  const a = frag.querySelector('a.show-card');
  a.href = `shows/${show.slug}.html`;
  a.setAttribute('aria-label', `${show.title} — ${show.theatre || 'Broadway'} — ${show.status.replace('_', ' ')}`);

  const pal = show.palette || [];
  for (let i = 0; i < 5; i++) {
    a.style.setProperty(`--p${i+1}`, pal[i] || 'oklch(40% 0.05 270)');
  }

  const pill = frag.querySelector('.pill');
  pill.textContent = ({
    coming_soon: 'Coming Soon',
    in_previews: 'In Previews',
    live:        'Live',
    closed:      'Closed',
  })[show.status] || show.status;
  pill.setAttribute('aria-hidden', 'true');

  const poster = frag.querySelector('.poster');
  poster.setAttribute('aria-label', `${show.title} poster`);
  const stamp = frag.querySelector('.poster .stamp');
  stamp.textContent = show.title;
  const img = new Image();
  img.alt = '';
  img.onload = () => { poster.appendChild(img); stamp.style.display = 'none'; };
  img.src = `shows/posters/${show.slug}.jpg`;

  frag.querySelector('.title').textContent = show.title;
  const hero = heroCredit(show);
  frag.querySelector('.venue').textContent =
    hero ? `${show.theatre || ''} · ${hero}` : (show.theatre || '');

  const metrics = frag.querySelector('.metrics');
  const parts = [
    { v: fmtMoney(show.weekly_gross_usd), label: 'Weekly gross', ok: show.weekly_gross_usd != null },
    { v: fmtAvg(show.avg_ticket_usd),     label: 'Average ticket', ok: show.avg_ticket_usd    != null },
    { v: fmtPct(show.capacity_pct),       label: 'Capacity', ok: show.capacity_pct      != null },
  ];
  for (const p of parts) {
    if (p.v == null) continue;
    const span = document.createElement('span');
    span.className = 'm' + (p.ok ? '' : ' pending');
    span.textContent = p.v;
    span.setAttribute('aria-label', `${p.label}: ${p.v}`);
    metrics.appendChild(span);
  }
  if (!metrics.children.length) {
    const span = document.createElement('span');
    span.className = 'm pending';
    span.textContent = 'data pending';
    metrics.appendChild(span);
  }

  const scores = frag.querySelector('.scores');
  const cSpan = document.createElement('span');
  cSpan.className = 's ' + (show.critic_score != null ? '' : 'pending');
  cSpan.textContent = show.critic_score != null ? `Critic ${show.critic_score}` : 'Critic —';
  cSpan.title = show.critic_score != null ? '' : 'Critic — wiring soon';
  cSpan.setAttribute('aria-label', show.critic_score != null ? `Critic score: ${show.critic_score} of 100` : 'Critic score: pending');
  const aSpan = document.createElement('span');
  aSpan.className = 's ' + (show.sentiment_score != null ? '' : 'pending');
  aSpan.textContent = show.sentiment_score != null ? `Audience ${show.sentiment_score}` : 'Audience —';
  aSpan.title = show.sentiment_score != null ? '' : 'Audience — listening soon';
  aSpan.setAttribute('aria-label', show.sentiment_score != null ? `Audience score: ${show.sentiment_score} of 100` : 'Audience score: pending');
  scores.appendChild(cSpan);
  scores.appendChild(aSpan);

  return frag;
}

function renderSkeletons(grid, count) {
  grid.innerHTML = '';
  for (let i = 0; i < count; i++) {
    const s = document.createElement('div');
    s.className = 'skeleton-card';
    s.setAttribute('aria-hidden', 'true');
    grid.appendChild(s);
  }
}

function showFetchError(grid, msg) {
  grid.innerHTML = '';
  const div = document.createElement('div');
  div.className = 'fetch-error';
  div.setAttribute('role', 'alert');
  div.textContent = msg;
  grid.appendChild(div);
}

function updateTierBadge(source, ageDays, tierLabel) {
  const badge = document.querySelector('[data-slot="tier-badge"]');
  if (!badge) return;
  badge.dataset.source = source;
  const sourceText = formatTierBadge(source, ageDays);
  badge.textContent = `${tierLabel || 'SLAYBILL'} · ${sourceText}`;
}

function setupTierUI(config) {
  // Pro tier: show spend banner Mondays (or always-on for now until Pro
  // schedule reads server-side state). Fan tier: show upgrade banner once
  // per week, dismissible.
  const isPro = config.tier === 'pro' && config.show_spend_warning;
  const isFan = config.tier === 'fan' && config.show_upgrade_nudges;

  if (isPro) {
    const banner = document.querySelector('[data-slot="spend-banner"]');
    const dayOfWeek = new Date().getDay(); // 0 Sun, 1 Mon
    if (dayOfWeek === 1) banner.hidden = false; // Mondays only
    banner.querySelector('[data-action="skip-week"]')?.addEventListener('click', () => {
      localStorage.setItem('slaybill.pro.skip_until', String(Date.now() + 7 * 86_400_000));
      banner.hidden = true;
    });
    banner.querySelector('[data-action="confirm-spend"]')?.addEventListener('click', () => {
      banner.hidden = true;
    });
  }

  if (isFan) {
    const dismissedAt = parseInt(localStorage.getItem('slaybill.fan.upgrade_dismissed_at') || '0', 10);
    const showAgainAfter = dismissedAt + 7 * 86_400_000;
    if (Date.now() > showAgainAfter) {
      const banner = document.querySelector('[data-slot="upgrade-banner"]');
      banner.hidden = false;
      const link = banner.querySelector('[data-slot="upgrade-link"]');
      if (link && config.pro_upgrade_url) link.href = config.pro_upgrade_url;
      banner.querySelector('[data-action="dismiss-upgrade"]')?.addEventListener('click', () => {
        localStorage.setItem('slaybill.fan.upgrade_dismissed_at', String(Date.now()));
        banner.hidden = true;
      });
    }
  }
}

async function hydrate() {
  // Render skeletons in every grid before fetch.
  for (const section of document.querySelectorAll('.bucket')) {
    renderSkeletons(section.querySelector('[data-slot="grid"]'), 4);
  }
  renderSkeletons(document.querySelector('[data-slot="ob-track"]'), 4);

  const { data, source, age_days, config } = await resolveShowData();
  updateTierBadge(source, age_days, config.tier_label);
  setupTierUI(config);

  if (!data) {
    for (const section of document.querySelectorAll('.bucket')) {
      showFetchError(
        section.querySelector('[data-slot="grid"]'),
        'Show data did not load. The server may be down — refresh in a moment.'
      );
    }
    showFetchError(
      document.querySelector('[data-slot="ob-track"]'),
      'Off-Broadway data did not load.'
    );
    return;
  }

  for (const section of document.querySelectorAll('.bucket')) {
    const bucket = section.dataset.bucket;
    const shows = (data.buckets && data.buckets[bucket]) || [];
    const grid = section.querySelector('[data-slot="grid"]');
    grid.innerHTML = '';
    if (!shows.length) {
      const empty = document.createElement('div');
      empty.className = 'empty-bucket';
      empty.textContent = 'Nothing in this bucket right now.';
      grid.appendChild(empty);
      continue;
    }
    for (const show of shows) grid.appendChild(makeCard(show));
  }

  const track = document.querySelector('[data-slot="ob-track"]');
  track.innerHTML = '';
  const ob = data.off_broadway || [];
  if (!ob.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-bucket';
    empty.textContent = 'No Off-Broadway shows tracked yet.';
    track.appendChild(empty);
  } else {
    for (const show of ob) {
      const card = makeCard(show);
      const a = card.querySelector('a.show-card');
      a.classList.add('ob-card');
      track.appendChild(card);
    }
  }
}

// Scroll-jostle — only enable when reduced-motion is not requested.
if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  let lastY = window.scrollY, clearTimer, raf = 0;
  window.addEventListener('scroll', () => {
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      const y = window.scrollY, delta = y - lastY;
      if (Math.abs(delta) < 2) return;
      const dir = delta > 0 ? 'down' : 'up';
      lastY = y;
      document.body.classList.remove('scroll-up', 'scroll-down');
      document.body.classList.add('scroll-' + dir);
      clearTimeout(clearTimer);
      clearTimer = setTimeout(() => {
        document.body.classList.remove('scroll-up', 'scroll-down');
      }, 240);
    });
  }, { passive: true });
}

hydrate();
</script>
</body>
</html>

```

### FILE: web/shows/_template.html

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{TITLE}} — SLAYBILL</title>
<meta name="description" content="{{SYNOPSIS}}">
<style>
  :root {
    --c1: {{C1}}; --c2: {{C2}}; --c3: {{C3}}; --c4: {{C4}}; --c5: {{C5}};
    --ink: {{INK}};
    --ink-muted: {{INK_MUTED}};
    --stage: {{STAGE}};
    --surface: {{SURFACE}};
    --accent: {{C1}};
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    background:
      radial-gradient(circle at 15% 10%, color-mix(in oklab, var(--c1) 35%, transparent), transparent 55%),
      radial-gradient(circle at 85% 90%, color-mix(in oklab, var(--c2) 30%, transparent), transparent 55%),
      var(--stage);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    min-height: 100vh;
    padding: 32px 20px 80px;
  }

  /* Top bar: back link + status pill. */
  .topbar {
    max-width: 1100px; margin: 0 auto 24px;
    display: flex; justify-content: space-between; align-items: center;
    font-family: "Courier New", monospace;
    font-size: 11px;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    color: var(--ink-muted);
  }
  .topbar a {
    color: var(--ink-muted); text-decoration: none;
    padding: 8px 12px;
    border: 1px solid color-mix(in oklab, var(--ink) 15%, transparent);
    border-radius: 999px;
    transition: border-color .3s cubic-bezier(0.2, 0.8, 0.2, 1), color .3s cubic-bezier(0.2, 0.8, 0.2, 1);
  }
  .topbar a:hover, .topbar a:focus-visible {
    color: var(--ink);
    border-color: color-mix(in oklab, var(--ink) 40%, transparent);
    outline: none;
  }
  .chip {
    padding: 6px 10px; border-radius: 999px;
    background: color-mix(in oklab, var(--c1) 18%, transparent);
    border: 1px solid color-mix(in oklab, var(--c1) 40%, transparent);
    color: var(--ink);
  }

  /* Two-column hero: poster + vitals. */
  main {
    max-width: 1100px; margin: 0 auto;
    display: grid;
    grid-template-columns: minmax(280px, 0.9fr) 1.1fr;
    gap: 40px;
    align-items: start;
  }
  @media (max-width: 820px) { main { grid-template-columns: 1fr; gap: 28px; } }

  .marquee {
    grid-column: 1 / -1;
    text-align: center;
    padding: 16px 0 8px;
    border-top: 2px solid var(--ink);
    border-bottom: 2px solid var(--ink);
    margin-bottom: 8px;
    position: relative;
  }
  .marquee .eyebrow {
    font-family: "Courier New", monospace;
    font-size: 11px; letter-spacing: 0.5em; text-transform: uppercase;
    color: var(--ink-muted); margin-bottom: 10px;
  }
  .marquee h1 {
    font-family: "Times New Roman", Georgia, serif;
    font-weight: 900;
    font-size: clamp(48px, 9vw + 12px, 120px);
    line-height: 0.92;
    letter-spacing: -0.02em;
    margin: 0;
    text-transform: uppercase;
    color: var(--ink);
    word-break: keep-all;
  }
  .marquee .subtitle {
    font-family: "Times New Roman", Georgia, serif;
    font-style: italic;
    font-size: clamp(14px, 2vw + 6px, 22px);
    color: var(--ink-muted);
    margin: 6px 0 0;
  }
  .bulbs {
    position: absolute; left: 0; right: 0; top: -6px;
    height: 10px;
    background: repeating-linear-gradient(90deg, var(--c1) 0 6px, transparent 6px 24px);
    border-radius: 4px;
    opacity: 0.75;
    filter: drop-shadow(0 0 6px var(--c1));
    animation: bulb-pulse 2.6s ease-in-out infinite;
  }
  @keyframes bulb-pulse {
    0%, 100% { opacity: 0.75; }
    50% { opacity: 1; }
  }

  .poster {
    position: relative;
    border-radius: 20px;
    aspect-ratio: 3 / 4;
    overflow: hidden;
    background: var(--surface);
    border: 1px solid color-mix(in oklab, var(--ink) 10%, transparent);
    box-shadow:
      inset 0 1px 0 color-mix(in oklab, white 18%, transparent),
      inset 0 -1px 0 color-mix(in oklab, black 25%, transparent),
      0 30px 80px color-mix(in oklab, var(--c1) 30%, transparent);
  }
  .poster img, .poster svg {
    width: 100%; height: 100%;
    object-fit: cover;
    display: block;
  }
  .poster::after {
    content: ""; position: absolute; inset: 0;
    background: linear-gradient(135deg,
      color-mix(in oklab, white 14%, transparent) 0%,
      transparent 35%,
      color-mix(in oklab, var(--c2) 10%, transparent) 100%);
    pointer-events: none;
  }

  .vitals {
    display: grid;
    gap: 18px;
  }
  .panel {
    padding: 24px 22px;
    border-radius: 18px;
    background: color-mix(in oklab, var(--surface) 92%, transparent);
    border: 1px solid color-mix(in oklab, var(--ink) 12%, transparent);
    box-shadow:
      inset 0 1px 0 color-mix(in oklab, white 10%, transparent),
      inset 0 -1px 0 color-mix(in oklab, black 18%, transparent);
    position: relative;
    overflow: hidden;
  }
  @supports ((backdrop-filter: blur(12px)) or (-webkit-backdrop-filter: blur(12px))) {
    .panel {
      background: color-mix(in oklab, var(--surface) 55%, transparent);
      -webkit-backdrop-filter: blur(14px) saturate(140%);
      backdrop-filter: blur(14px) saturate(140%);
    }
  }
  .panel .label {
    font-family: "Courier New", monospace;
    font-size: 10px; letter-spacing: 0.4em; text-transform: uppercase;
    color: var(--ink-muted);
    margin-bottom: 10px;
  }
  .panel .row {
    display: flex; justify-content: space-between; gap: 16px;
    font-family: "Times New Roman", Georgia, serif;
    font-size: 18px;
    padding: 6px 0;
    border-bottom: 1px solid color-mix(in oklab, var(--ink) 8%, transparent);
  }
  .panel .row:last-child { border-bottom: none; }
  .panel .row .k {
    color: var(--ink-muted);
    font-family: "Courier New", monospace;
    font-size: 11px; letter-spacing: 0.2em; text-transform: uppercase;
    align-self: center;
  }
  .panel .row .v { color: var(--ink); font-weight: 400; text-align: right; }
  .panel .synopsis {
    font-family: "Times New Roman", Georgia, serif;
    font-size: 17px;
    line-height: 1.55;
    color: var(--ink);
  }

  /* Who — cast + creatives + producers columns. */
  .who {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 18px;
  }
  .who .panel h3 {
    font-family: "Courier New", monospace;
    font-size: 10px;
    letter-spacing: 0.4em;
    text-transform: uppercase;
    color: var(--ink-muted);
    margin: 0 0 14px;
    font-weight: 400;
  }
  .who ul { list-style: none; padding: 0; margin: 0; }
  .who li {
    padding: 6px 0;
    border-bottom: 1px solid color-mix(in oklab, var(--ink) 6%, transparent);
    display: flex; justify-content: space-between; gap: 12px;
  }
  .who li:last-child { border-bottom: none; }
  .who .n { color: var(--ink); font-family: "Times New Roman", Georgia, serif; font-size: 16px; }
  .who .r { color: var(--ink-muted); font-family: "Courier New", monospace; font-size: 10px; letter-spacing: 0.15em; text-transform: uppercase; align-self: center; }
  .who .empty { color: var(--ink-muted); font-style: italic; font-size: 13px; }

  /* Money — weekly gross + capacity + avg ticket. */
  .money {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 14px;
  }
  .money .cell {
    padding: 22px 18px;
    border-radius: 14px;
    background: color-mix(in oklab, var(--surface) 92%, transparent);
    border: 1px solid color-mix(in oklab, var(--ink) 10%, transparent);
    text-align: center;
  }
  @supports ((backdrop-filter: blur(10px)) or (-webkit-backdrop-filter: blur(10px))) {
    .money .cell {
      background: color-mix(in oklab, var(--surface) 50%, transparent);
      -webkit-backdrop-filter: blur(10px);
      backdrop-filter: blur(10px);
    }
  }
  .money .metric {
    font-family: "Times New Roman", Georgia, serif;
    font-size: 34px;
    line-height: 1;
    color: var(--ink);
  }
  .money .metric.pending { color: color-mix(in oklab, var(--ink) 50%, transparent); font-style: italic; font-size: 28px; }
  .money .name {
    font-family: "Courier New", monospace;
    font-size: 10px; letter-spacing: 0.3em; text-transform: uppercase;
    color: var(--ink-muted); margin-top: 8px;
  }

  /* Tickets table — deep links per vendor. */
  .tickets {
    grid-column: 1 / -1;
  }
  .tickets table {
    width: 100%;
    border-collapse: collapse;
    background: color-mix(in oklab, var(--surface) 55%, transparent);
    border: 1px solid color-mix(in oklab, var(--ink) 10%, transparent);
    border-radius: 14px;
    overflow: hidden;
  }
  .tickets th, .tickets td {
    padding: 14px 16px;
    text-align: left;
    border-bottom: 1px solid color-mix(in oklab, var(--ink) 8%, transparent);
  }
  .tickets tbody tr:last-child td { border-bottom: none; }
  .tickets th {
    font-family: "Courier New", monospace;
    font-size: 10px; letter-spacing: 0.3em; text-transform: uppercase;
    color: var(--ink-muted); font-weight: 400;
  }
  .tickets td { color: var(--ink); font-family: "Times New Roman", Georgia, serif; font-size: 16px; }
  .tickets .vendor { text-transform: uppercase; letter-spacing: 0.1em; font-family: "Courier New", monospace; font-size: 12px; }
  .tickets a.go {
    display: inline-block;
    padding: 6px 14px;
    background: color-mix(in oklab, var(--c1) 22%, transparent);
    border: 1px solid color-mix(in oklab, var(--c1) 50%, transparent);
    color: var(--ink);
    border-radius: 999px;
    text-decoration: none;
    font-family: "Courier New", monospace;
    font-size: 10px;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    transition: background .3s;
  }
  .tickets a.go:hover { background: color-mix(in oklab, var(--c1) 40%, transparent); }
  .tickets .pending { color: var(--ink-muted); font-style: italic; font-size: 13px; }
  .tickets .note {
    margin: 10px 4px 0;
    font-family: "Courier New", monospace;
    font-size: 10px;
    letter-spacing: 0.15em;
    color: var(--ink-muted);
  }

  /* Critics + audience: em-dash for v1 since aggregation isn't wired yet. */
  .scores-grid {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }
  @media (max-width: 640px) { .scores-grid { grid-template-columns: 1fr; } }
  .score-card {
    padding: 24px 22px;
    border-radius: 14px;
    background: color-mix(in oklab, var(--surface) 55%, transparent);
    border: 1px solid color-mix(in oklab, var(--ink) 10%, transparent);
  }
  .score-card .big {
    font-family: "Times New Roman", Georgia, serif;
    font-size: 56px; line-height: 1;
  }
  .score-card .big.pending {
    color: color-mix(in oklab, var(--ink) 45%, transparent);
    font-style: italic;
  }
  .score-card .note { color: var(--ink-muted); font-family: "Courier New", monospace; font-size: 10px; letter-spacing: 0.2em; text-transform: uppercase; margin-top: 8px; }
  .score-card .methodology { color: var(--ink-muted); font-size: 12px; font-style: italic; margin-top: 14px; }

  /* Sources / last updated footer. */
  .sources {
    grid-column: 1 / -1;
    padding: 16px 20px;
    border-radius: 12px;
    background: color-mix(in oklab, var(--surface) 50%, transparent);
    border: 1px solid color-mix(in oklab, var(--ink) 8%, transparent);
    font-family: "Courier New", monospace;
    font-size: 10px;
    letter-spacing: 0.15em;
    color: var(--ink-muted);
    text-align: center;
  }

  footer {
    max-width: 1100px; margin: 48px auto 0;
    text-align: center;
    font-family: "Courier New", monospace;
    font-size: 10px; letter-spacing: 0.3em; text-transform: uppercase;
    color: var(--ink-muted);
  }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }
</style>
</head>
<body>
<div class="topbar">
  <a href="../index.html">&larr; SLAYBILL</a>
  <span class="chip">{{STATUS_CHIP}} &middot; {{THEATRE}}</span>
</div>

<main>
  <section class="marquee">
    <div class="bulbs"></div>
    <div class="eyebrow">SLAYBILL</div>
    <h1>{{TITLE}}</h1>
    <p class="subtitle">{{SUBTITLE}}</p>
  </section>

  <section class="poster">
    {{POSTER_MARKUP}}
  </section>

  <section class="vitals">
    <div class="panel">
      <div class="label">Synopsis</div>
      <div class="synopsis">{{SYNOPSIS}}</div>
    </div>
    <div class="panel">
      <div class="label">Vitals</div>
      <div class="row"><span class="k">Theatre</span><span class="v">{{THEATRE}}</span></div>
      <div class="row"><span class="k">Capacity</span><span class="v">{{THEATRE_CAPACITY}}</span></div>
      <div class="row"><span class="k">First Preview</span><span class="v">{{FIRST_PREVIEW_DATE}}</span></div>
      <div class="row"><span class="k">Opened</span><span class="v">{{OPENING_DATE}}</span></div>
      <div class="row"><span class="k">Status</span><span class="v">{{STATUS_CHIP}}</span></div>
    </div>
  </section>

  <section class="who" aria-label="Cast, creatives, and producers">
    <div class="panel">
      <h3>Cast</h3>
      <ul>{{CAST_LIST}}</ul>
    </div>
    <div class="panel">
      <h3>Creatives</h3>
      <ul>{{CREATIVES_LIST}}</ul>
    </div>
    <div class="panel">
      <h3>Producers</h3>
      <ul>{{PRODUCERS_LIST}}</ul>
    </div>
  </section>

  <section class="money" aria-label="Money">
    <div class="cell">
      <div class="metric {{WEEKLY_GROSS_CLASS}}">{{WEEKLY_GROSS}}</div>
      <div class="name">Weekly Gross</div>
    </div>
    <div class="cell">
      <div class="metric {{AVG_TICKET_CLASS}}">{{AVG_TICKET}}</div>
      <div class="name">Avg Ticket</div>
    </div>
    <div class="cell">
      <div class="metric {{CAPACITY_CLASS}}">{{CAPACITY_PCT}}</div>
      <div class="name">Capacity</div>
    </div>
    <div class="cell">
      <div class="metric pending">—</div>
      <div class="name">WoW Delta</div>
    </div>
  </section>

  <section class="tickets" aria-label="Tickets">
    <div class="panel">
      <div class="label">Tickets</div>
      <table>
        <thead>
          <tr>
            <th>Vendor</th>
            <th>What to expect</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {{TICKET_ROWS}}
        </tbody>
      </table>
      <div class="note">Live prices open on the vendor's page in a new tab. Daily &amp; week-over-week price history wires in once our price-sample pipeline is live.</div>
    </div>
  </section>

  <section class="scores-grid" aria-label="Critic and audience scores">
    <div class="score-card">
      <div class="label" style="font-family:'Courier New',monospace;font-size:10px;letter-spacing:0.4em;text-transform:uppercase;color:var(--ink-muted);margin-bottom:10px;">Critic Score</div>
      <div class="big {{CRITIC_CLASS}}">{{CRITIC_SCORE}}</div>
      <div class="note">{{CRITIC_NOTE}}</div>
      <div class="methodology">Aggregated from NYT, Variety, The Hollywood Reporter, Vulture, TimeOut. Normalized 0–100.</div>
    </div>
    <div class="score-card">
      <div class="label" style="font-family:'Courier New',monospace;font-size:10px;letter-spacing:0.4em;text-transform:uppercase;color:var(--ink-muted);margin-bottom:10px;">Audience Sentiment</div>
      <div class="big {{SENTIMENT_CLASS}}">{{SENTIMENT_SCORE}}</div>
      <div class="note">{{SENTIMENT_NOTE}}</div>
      <div class="methodology">Social-listening aggregate from Reddit &middot; TikTok &middot; Instagram. Updated weekly.</div>
    </div>
  </section>

  <section class="sources">
    Sources &middot; Playbill grosses &middot; Off-Broadway League &middot; BroadwayWorld &middot; editorial curation &middot; last updated {{LAST_UPDATED}}
  </section>
</main>

<footer>SLAYBILL &middot; <a href="../index.html" style="color:inherit;text-decoration:none;">home</a> &middot; <a href="../fantasy.html" style="color:inherit;text-decoration:none;">fantasy</a> &middot; <a href="../archive.html" style="color:inherit;text-decoration:none;">archive</a></footer>
<script type="module">
  import { setupUpgradeNudge } from '../assets/js/upgrade-nudge.js';
  setupUpgradeNudge('{{SLUG}}');
</script>
</body>
</html>

```

### FILE: web/fantasy.html

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fantasy Broadway — SLAYBILL</title>
<meta name="description" content="Fantasy Broadway: draft a roster of one Broadway musical, one Broadway play, and the same for off-Broadway. Score on audience sentiment, critic reviews, and weekly revenue. Season ends at the Tonys.">
<style>
  :root {
    --playbill-yellow: #f4d71e;
    --playbill-ink: #0a0a0a;
    --playbill-red: #c3102f;
    --playbill-muted: #5a5a5a;
    --bg: #05050f;
    --ink: #ecebff;
    --muted: #8a8ab0;
    --holo1: #7209b7;
    --holo2: #f72585;
    --holo3: #4cc9f0;
    --holo4: #80ffdb;
    --gold: #ffd700;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; }
  body {
    background:
      radial-gradient(circle at 20% 10%, rgba(255,215,0,0.08), transparent 55%),
      radial-gradient(circle at 85% 90%, rgba(247,37,133,0.12), transparent 55%),
      var(--bg);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    min-height: 100vh;
    padding: 32px 20px 64px;
  }

  /* Same jostle pattern as the main Playbill page for continuity. */
  .jostle {
    display: inline-block;
    will-change: transform;
    transition: transform .45s cubic-bezier(0.2, 0.8, 0.2, 1);
  }
  body.scroll-down .jostle { transform: translateY(-3px); }
  body.scroll-up   .jostle { transform: translateY(3px); }
  body.scroll-down .cover .jostle:nth-of-type(2n) { transform: translateY(-4px); }
  body.scroll-up   .cover .jostle:nth-of-type(2n) { transform: translateY(4px); }

  /* Personal SLAYBILL cover — yellow card, the user's name on top. */
  .cover {
    width: 100%; max-width: 520px;
    margin: 0 auto 40px;
    background: var(--playbill-yellow);
    color: var(--playbill-ink);
    box-shadow: 0 30px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(0,0,0,0.1);
    padding: 24px 32px 22px;
    position: relative;
    font-family: "Times New Roman", Georgia, serif;
    display: grid;
    gap: 14px;
  }
  .cover .masthead {
    border-top: 4px solid var(--playbill-ink);
    border-bottom: 4px solid var(--playbill-ink);
    padding: 10px 0;
    text-align: center;
  }
  .cover .word {
    font-size: clamp(40px, 8vw + 4px, 64px);
    letter-spacing: -0.02em; font-weight: 900;
    line-height: 0.9;
  }
  .cover .sub {
    font-size: 10px; letter-spacing: 0.3em; margin-top: 6px;
    text-transform: uppercase;
  }
  .cover .owner {
    text-align: center;
    font-family: "Courier New", monospace;
    font-size: 11px;
    letter-spacing: 0.4em;
    text-transform: uppercase;
  }
  .cover .owner input {
    font: inherit; color: inherit; letter-spacing: inherit;
    background: transparent; border: none;
    border-bottom: 1px dashed rgba(0,0,0,0.4);
    text-align: center;
    padding: 2px 4px;
    min-width: 200px;
    outline: none;
  }
  .cover .owner input:focus { border-bottom-color: var(--playbill-red); }
  .cover .tagline {
    text-align: center;
    font-style: italic;
    font-size: 15px;
    line-height: 1.4;
  }
  .cover .dog-ear {
    position: absolute; top: 0; right: 0;
    width: 38px; height: 38px;
    background: linear-gradient(225deg, rgba(0,0,0,0.08) 0%, rgba(0,0,0,0.08) 50%, transparent 50%);
  }

  /* Top nav back to Playbill. */
  .topbar {
    max-width: 1100px; margin: 0 auto 18px;
    font-family: "Courier New", monospace;
    font-size: 11px;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .topbar a {
    color: var(--muted); text-decoration: none;
    padding: 6px 10px;
    border: 1px solid rgba(232,232,255,0.15);
    border-radius: 999px;
    transition: border-color .3s, color .3s;
  }
  .topbar a:hover { color: var(--ink); border-color: rgba(232,232,255,0.35); }

  /* Roster — 4 slots. Each shows the drafted show or a "DRAFT" placeholder. */
  .roster {
    max-width: 1100px; margin: 0 auto 40px;
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
  }
  @media (max-width: 820px) { .roster { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  @media (max-width: 440px) { .roster { grid-template-columns: 1fr; } }
  .slot {
    position: relative;
    padding: 18px 18px 16px;
    border-radius: 14px;
    background: rgba(20,20,40,0.75);
    border: 1px solid rgba(232,232,255,0.12);
    display: flex; flex-direction: column; gap: 8px;
    min-height: 180px;
  }
  @supports ((backdrop-filter: blur(10px)) or (-webkit-backdrop-filter: blur(10px))) {
    .slot {
      background: rgba(20,20,40,0.5);
      -webkit-backdrop-filter: blur(12px) saturate(140%);
      backdrop-filter: blur(12px) saturate(140%);
    }
  }
  .slot .label {
    font-family: "Courier New", monospace;
    font-size: 10px;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .slot .name {
    font-family: "Times New Roman", Georgia, serif;
    font-size: clamp(18px, 1.8vw + 10px, 22px);
    font-weight: 900;
    text-transform: uppercase;
    line-height: 1.05;
    letter-spacing: -0.01em;
    overflow-wrap: break-word;
  }
  .slot .name.empty {
    color: var(--muted);
    font-family: "Courier New", monospace;
    font-size: 11px;
    letter-spacing: 0.3em;
    font-weight: 400;
  }
  .slot .venue {
    font-size: 11px;
    font-family: "Courier New", monospace;
    letter-spacing: 0.1em;
    color: var(--muted);
  }
  .slot .score {
    margin-top: auto;
    display: flex; justify-content: space-between; align-items: flex-end;
    font-family: "Courier New", monospace;
    font-size: 10px; letter-spacing: 0.2em;
    text-transform: uppercase; color: var(--muted);
  }
  .slot .score .n {
    font-family: "Times New Roman", Georgia, serif;
    font-size: 22px;
    color: var(--gold);
    letter-spacing: 0;
    text-transform: none;
  }
  .slot .clear {
    position: absolute; top: 8px; right: 10px;
    background: transparent; border: none; color: var(--muted);
    font-size: 14px; cursor: pointer;
    padding: 4px; line-height: 1;
  }
  .slot .clear:hover { color: var(--playbill-red); }

  .summary {
    max-width: 1100px; margin: 0 auto 40px;
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: center;
    gap: 18px;
    padding: 16px 22px;
    border-radius: 14px;
    border: 1px solid rgba(255,215,0,0.35);
    background: color-mix(in oklab, var(--gold) 8%, rgba(10,10,15,0.5));
  }
  .summary .lbl {
    font-family: "Courier New", monospace;
    font-size: 11px; letter-spacing: 0.3em; text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 4px;
  }
  .summary .total {
    font-family: "Times New Roman", Georgia, serif;
    font-size: 38px; font-weight: 900;
    color: var(--gold);
    line-height: 1;
  }
  .summary .note {
    font-size: 11px; color: var(--muted);
    font-family: "Courier New", monospace;
    letter-spacing: 0.1em;
    text-align: right;
  }

  /* Draft pool — 4 columns (one per roster slot category). */
  h2.section {
    max-width: 1100px; margin: 0 auto 12px;
    font-family: "Courier New", monospace;
    font-size: 11px;
    letter-spacing: 0.5em;
    text-transform: uppercase;
    color: var(--muted);
    font-weight: 400;
  }
  .pool {
    max-width: 1100px; margin: 0 auto 36px;
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
  }
  @media (max-width: 820px) { .pool { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  @media (max-width: 440px) { .pool { grid-template-columns: 1fr; } }
  .col {
    background: rgba(15,15,30,0.65);
    border: 1px solid rgba(232,232,255,0.08);
    border-radius: 12px;
    padding: 12px 12px 10px;
    display: flex; flex-direction: column; gap: 6px;
    max-height: 480px;
    overflow-y: auto;
  }
  .col h3 {
    margin: 0 0 6px;
    font-family: "Courier New", monospace;
    font-size: 10px; letter-spacing: 0.3em; text-transform: uppercase;
    color: var(--holo3);
    padding-bottom: 6px;
    border-bottom: 1px solid rgba(232,232,255,0.1);
  }
  .card {
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 9px;
    background: rgba(20,20,40,0.6);
    border: 1px solid rgba(232,232,255,0.08);
    cursor: pointer;
    /* Reset button defaults so it looks like a card, not a button. */
    width: 100%;
    text-align: left;
    color: inherit;
    font: inherit;
    appearance: none;
    -webkit-appearance: none;
    transition: transform .25s cubic-bezier(0.2, 0.8, 0.2, 1), border-color .25s, background .25s;
  }
  .card:focus-visible {
    outline: 2px solid var(--gold);
    outline-offset: 2px;
  }
  .card:hover { transform: translateX(2px); border-color: rgba(255,215,0,0.35); background: rgba(40,40,20,0.7); }
  .card.selected { border-color: var(--gold); background: color-mix(in oklab, var(--gold) 10%, rgba(20,20,40,0.6)); }
  .card .title {
    font-family: -apple-system, system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--ink);
    line-height: 1.2;
  }
  .card .sub {
    font-family: "Courier New", monospace;
    font-size: 9px; letter-spacing: 0.12em;
    color: var(--muted);
    margin-top: 2px;
  }
  .card .score {
    font-family: "Times New Roman", Georgia, serif;
    font-size: 16px;
    color: var(--gold);
    font-weight: 700;
  }
  .col .empty {
    color: var(--muted);
    font-family: "Courier New", monospace;
    font-size: 10px;
    letter-spacing: 0.15em;
    text-align: center;
    padding: 14px 8px;
    font-style: italic;
  }

  /* Tonys countdown strip. */
  .tonys {
    max-width: 1100px; margin: 0 auto 24px;
    padding: 18px 22px;
    border-radius: 14px;
    background: linear-gradient(135deg, rgba(255,215,0,0.12), rgba(195,16,47,0.08));
    border: 1px solid rgba(255,215,0,0.3);
    display: flex; justify-content: space-between; align-items: center;
    gap: 18px; flex-wrap: wrap;
  }
  .tonys .t { font-family: "Times New Roman", Georgia, serif; font-size: 22px; color: var(--gold); }
  .tonys .s { color: var(--muted); font-family: "Courier New", monospace; font-size: 11px; letter-spacing: 0.22em; text-transform: uppercase; }

  footer {
    max-width: 1100px; margin: 40px auto 0; text-align: center;
    font-family: "Courier New", monospace;
    font-size: 10px; letter-spacing: 0.3em; text-transform: uppercase;
    color: var(--muted);
  }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }
</style>
</head>
<body>
<div class="topbar">
  <a href="index.html">← SLAYBILL · All Shows</a>
</div>

<section class="cover">
  <div class="masthead">
    <div class="word jostle">FANTASY BROADWAY</div>
    <div class="sub jostle">Draft · Score · Tonys</div>
  </div>
  <p class="owner jostle">Manager · <input id="ownerName" type="text" maxlength="28" placeholder="Your name here" autocomplete="off" spellcheck="false"></p>
  <p class="tagline jostle">Like Fantasy Football — without the risk of CTEs.<br><span style="font-family:'Courier New',monospace;font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:var(--playbill-red)">Draft 4 shows · score weekly · crown the Tonys</span></p>
  <div class="dog-ear"></div>
</section>

<section class="tonys">
  <div>
    <div class="s">78th Tony Awards</div>
    <div class="t" id="tonysCountdown">calculating…</div>
  </div>
  <div>
    <div class="s">Season ends · final roster locks day of ceremony</div>
  </div>
</section>

<h2 class="section">Your roster · click a show below to draft it into a slot</h2>

<section class="roster" id="roster">
  <!-- Populated by JS -->
</section>

<section class="summary">
  <div>
    <div class="lbl">Total fantasy points</div>
    <div class="total"><span id="totalPts">0</span></div>
  </div>
  <div class="note">
    points = capacity% × 10 + gross_rank_bonus<br>
    sentiment + critic wiring next
  </div>
</section>

<h2 class="section">Draft pool · <span id="poolStatus">live from Playbill</span></h2>

<section class="pool" id="pool">
  <div class="col" data-slot="broadway-musical">
    <h3>Broadway · Musical</h3>
  </div>
  <div class="col" data-slot="broadway-play">
    <h3>Broadway · Play</h3>
  </div>
  <div class="col" data-slot="offbroadway-musical">
    <h3>Off-Broadway · Musical</h3>
  </div>
  <div class="col" data-slot="offbroadway-play">
    <h3>Off-Broadway · Play</h3>
  </div>
</section>

<footer>SLAYBILL &middot; Fantasy Broadway &middot; Data from Playbill weekly grosses</footer>

<script>
/* Fantasy Broadway page logic.
 *
 * Loads shows_live.json (generated by build_live_shows.py from the Playbill
 * grosses scrape). Lets the user assign one show to each of four slots:
 * Broadway Musical / Broadway Play / Off-Broadway Musical / Off-Broadway Play.
 * Persists the team + manager name in localStorage so refreshing doesn't
 * blow away the draft.
 *
 * Score rules (v1 — placeholder formula):
 *   per show = round(capacity_pct * 10 + rank_bonus)
 *   rank_bonus = 40 for gross rank 1, 38 for 2, ... down to 0 beyond rank 20
 *   Off-Broadway shows score 50 flat (no gross data yet).
 * Real sentiment + critic signals wire in once the Reddit/Playbill-news
 * scrapers feed per-show event aggregates. The formula is kept simple
 * enough that the ordering intuition holds: filling a stronger venue +
 * higher capacity scores better. */

const SLOTS = [
  { id: 'broadway-musical',    label: 'Broadway · Musical',     scope: 'broadway',    category: 'musical' },
  { id: 'broadway-play',       label: 'Broadway · Play',        scope: 'broadway',    category: 'play'    },
  { id: 'offbroadway-musical', label: 'Off-Broadway · Musical', scope: 'off-broadway', category: 'musical' },
  { id: 'offbroadway-play',    label: 'Off-Broadway · Play',    scope: 'off-broadway', category: 'play'    },
];

const STORAGE_KEY = 'slaybill.fantasy.team.v1';
const NAME_KEY    = 'slaybill.fantasy.name';

let data = null;
let team = {};

function rankBonus(rank) {
  if (rank == null || rank > 20) return 0;
  return Math.max(0, 42 - rank * 2);
}

function scoreOf(show, bwayRank) {
  if (!show) return 0;
  if (show.tier === 'off_broadway') return 50;
  const cap = show.capacity_pct || 90;
  return Math.round(cap * 10 + rankBonus(bwayRank));
}

function allBroadway() {
  if (!data || !data.buckets) return [];
  return [
    ...(data.buckets.live || []),
    ...(data.buckets.in_previews || []),
    ...(data.buckets.coming_soon || []),
  ];
}

function findShow(slug) {
  if (!data) return null;
  return [...allBroadway(), ...(data.off_broadway || [])].find(s => s.slug === slug) || null;
}

function rankOf(show) {
  if (!show || show.tier !== 'broadway' || !data) return null;
  const sorted = [...allBroadway()].sort((a, b) => (b.weekly_gross_usd || 0) - (a.weekly_gross_usd || 0));
  const idx = sorted.findIndex(s => s.slug === show.slug);
  return idx >= 0 ? idx + 1 : null;
}

function renderRoster() {
  const root = document.getElementById('roster');
  root.innerHTML = '';
  let total = 0;
  for (const slot of SLOTS) {
    const show = team[slot.id] ? findShow(team[slot.id]) : null;
    const rank = show ? rankOf(show) : null;
    const pts = show ? scoreOf(show, rank) : 0;
    total += pts;
    const el = document.createElement('div');
    el.className = 'slot';
    el.innerHTML = show ? `
      <button class="clear" data-slot="${slot.id}" aria-label="Drop ${show.title}">✕</button>
      <div class="label">${slot.label}</div>
      <div class="name">${escapeHTML(show.title)}</div>
      <div class="venue">${escapeHTML(show.theatre)}${rank ? ' · rank #' + rank : ''}</div>
      <div class="score"><span>points</span><span class="n">${pts}</span></div>
    ` : `
      <div class="label">${slot.label}</div>
      <div class="name empty">— DRAFT —</div>
      <div class="venue">click a ${slot.category} in the pool below</div>
      <div class="score"><span>points</span><span class="n">0</span></div>
    `;
    root.appendChild(el);
  }
  document.getElementById('totalPts').textContent = total;
  root.querySelectorAll('.clear').forEach(b => b.addEventListener('click', e => {
    e.stopPropagation();
    const slot = b.dataset.slot;
    delete team[slot];
    saveTeam();
    renderRoster();
    renderPool();
  }));
}

function renderPool() {
  if (!data) return;
  const pool = document.getElementById('pool');
  for (const slot of SLOTS) {
    const col = pool.querySelector(`[data-slot="${slot.id}"]`);
    // keep the h3, wipe the rest
    col.querySelectorAll('.card, .empty').forEach(e => e.remove());
    const sourceList = slot.scope === 'broadway' ? allBroadway() : (data.off_broadway || []);
    let filtered = sourceList.filter(s => s.category === slot.category);
    if (slot.scope === 'broadway') {
      filtered.sort((a, b) => (b.weekly_gross_usd || 0) - (a.weekly_gross_usd || 0));
    } else {
      filtered.sort((a, b) => a.title.localeCompare(b.title));
    }
    if (!filtered.length) {
      const e = document.createElement('div');
      e.className = 'empty';
      e.textContent = 'no shows tagged yet';
      col.appendChild(e);
      continue;
    }
    for (const show of filtered) {
      const rank = rankOf(show);
      const pts = scoreOf(show, rank);
      const picked = team[slot.id] === show.slug;
      // Use a real <button> so keyboard + screen-reader users can draft.
      const c = document.createElement('button');
      c.type = 'button';
      c.className = 'card' + (picked ? ' selected' : '');
      c.setAttribute('aria-pressed', picked ? 'true' : 'false');
      c.setAttribute('aria-label',
        `Draft ${show.title} into ${slot.label} — ${pts} points`);
      c.innerHTML = `
        <div>
          <div class="title">${escapeHTML(show.title)}</div>
          <div class="sub">${escapeHTML(show.theatre)}${show.capacity_pct ? ' · ' + show.capacity_pct.toFixed(0) + '%' : ''}</div>
        </div>
        <div class="score">${pts}</div>
      `;
      const draft = () => {
        team[slot.id] = show.slug;
        saveTeam();
        renderRoster();
        renderPool();
      };
      c.addEventListener('click', draft);
      // Enter/Space already trigger click on <button>; keep handler for clarity.
      col.appendChild(c);
    }
  }
  const bway = allBroadway();
  const untagged = bway.filter(s => s.category === 'unknown').length;
  const obCount = (data.off_broadway || []).length;
  document.getElementById('poolStatus').textContent =
    `${bway.length} Broadway + ${obCount} Off-Broadway${untagged ? ` · ${untagged} untagged` : ''}`;
}

function loadTeam() {
  try { team = JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; }
  catch { team = {}; }
}
function saveTeam() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(team));
}

function wireOwnerName() {
  const input = document.getElementById('ownerName');
  const saved = localStorage.getItem(NAME_KEY);
  // URL param takes precedence — so sharing ?name=Austin works as a preset
  const params = new URLSearchParams(location.search);
  const fromUrl = params.get('name');
  input.value = fromUrl || saved || '';
  input.addEventListener('input', () => localStorage.setItem(NAME_KEY, input.value));
}

function wireTonysCountdown() {
  // 78th Tony Awards — airing June 7 2026 per current calendar.
  // Placeholder; update to CBS/League-confirmed air date when announced.
  const target = new Date('2026-06-07T20:00:00-04:00');
  const el = document.getElementById('tonysCountdown');
  function tick() {
    const now = new Date();
    const ms = target - now;
    if (ms <= 0) { el.textContent = 'TONIGHT'; return; }
    const d = Math.floor(ms / 86_400_000);
    const h = Math.floor((ms % 86_400_000) / 3_600_000);
    el.textContent = `${d} days · ${h}h · to ceremony`;
  }
  tick();
  setInterval(tick, 60_000);
}

function escapeHTML(s) {
  return (s || '').replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
}

// Scroll-jostle — same pattern as the main SLAYBILL page.
(function(){
  let lastY = window.scrollY, clearTimer, raf = 0;
  function onScroll(){
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      const y = window.scrollY, delta = y - lastY;
      if (Math.abs(delta) < 2) return;
      const dir = delta > 0 ? 'down' : 'up';
      lastY = y;
      document.body.classList.remove('scroll-up', 'scroll-down');
      document.body.classList.add('scroll-' + dir);
      clearTimeout(clearTimer);
      clearTimer = setTimeout(() => {
        document.body.classList.remove('scroll-up', 'scroll-down');
      }, 240);
    });
  }
  window.addEventListener('scroll', onScroll, { passive: true });
})();

(async function init() {
  loadTeam();
  wireOwnerName();
  wireTonysCountdown();
  try {
    const r = await fetch('data/shows_live.json', { cache: 'no-store' });
    data = await r.json();
  } catch (e) {
    data = { buckets: {}, off_broadway: [] };
    document.getElementById('poolStatus').textContent = 'shows_live.json not loaded — run builders/build_live_shows.py';
  }
  renderRoster();
  renderPool();
})();
</script>
</body>
</html>

```

### FILE: web/archive.html

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Archive — SLAYBILL</title>
<style>
  :root {
    --bg: #0a0a0a;
    --ink: #e8e8e8;
    --muted: #8a8a8a;
    --accent: #f4c842;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; }
  body {
    background: var(--bg);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    min-height: 100vh;
    padding: 48px 24px 80px;
  }
  .wrap { max-width: 900px; margin: 0 auto; }
  .back {
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
  }
  .back:hover { color: var(--ink); border-color: rgba(232,232,232,0.35); }
  h1 {
    font-family: "Times New Roman", Georgia, serif;
    font-weight: 900;
    font-size: clamp(48px, 6vw + 10px, 80px);
    letter-spacing: -0.02em;
    line-height: 0.95;
    margin: 0 0 6px;
    text-transform: uppercase;
  }
  .sub {
    color: var(--muted);
    font-family: "Courier New", monospace;
    font-size: 11px;
    letter-spacing: 0.4em;
    text-transform: uppercase;
    margin-bottom: 48px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
  }
  th, td {
    text-align: left;
    padding: 16px 12px;
    border-bottom: 1px solid rgba(232,232,232,0.1);
  }
  th {
    font-family: "Courier New", monospace;
    font-size: 10px;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    color: var(--muted);
    font-weight: 400;
  }
  td.title {
    font-family: "Times New Roman", Georgia, serif;
    font-size: 20px;
  }
  td.title a { color: var(--ink); text-decoration: none; }
  td.title a:hover { color: var(--accent); }
  td.status { color: var(--muted); font-family: "Courier New", monospace; font-size: 11px; letter-spacing: 0.18em; text-transform: uppercase; }
  .empty {
    padding: 80px 20px;
    text-align: center;
    color: var(--muted);
    font-style: italic;
  }
  footer {
    margin-top: 60px;
    text-align: center;
    color: var(--muted);
    font-family: "Courier New", monospace;
    font-size: 10px;
    letter-spacing: 0.3em;
    text-transform: uppercase;
  }
</style>
</head>
<body>
<div class="wrap">
  <a class="back" href="index.html">&larr; SLAYBILL</a>
  <h1>Archive</h1>
  <div class="sub">Closed &middot; Cancelled &middot; Off the boards</div>
  <div class="empty">No shows in the archive yet.</div>
  <footer>Generated 2026-04-25T13:41:23+00:00</footer>
</div>
</body>
</html>

```

### FILE: web/assets/js/data-resolver.js

```javascript
/**
 * SLAYBILL data resolver — tier-aware data fetcher.
 *
 * Resolves show data by trying, in order:
 *   1. Pro cache (https://slaybill-pro-cache.<domain>/shows_live.json)
 *      Used by Fan tier when pro_cache_url is set in config/tier.json
 *      and the cache is fresh (within pro_cache_max_age_days).
 *   2. Local data/shows_live.json
 *      Always tried as a fallback. Pro tier reads this directly (it generates it).
 *   3. localStorage cache
 *      Last-known-good data, persisted from any successful prior load.
 *
 * Returns { data, source, age_days } where source is one of:
 *   'pro_cache' | 'local' | 'cached' | 'error'
 *
 * Usage:
 *   import { resolveShowData, formatTierBadge } from './data-resolver.js';
 *   const { data, source, age_days } = await resolveShowData();
 *   document.getElementById('tier-badge').textContent =
 *     formatTierBadge(source, age_days);
 */

const CACHE_KEY = 'slaybill.shows_live.cached.v1';
const CACHE_TIMESTAMP_KEY = 'slaybill.shows_live.cached_at.v1';

async function loadConfig() {
  try {
    const r = await fetch('config/tier.json', { cache: 'no-store' });
    if (!r.ok) throw new Error(`config/tier.json: ${r.status}`);
    return await r.json();
  } catch (e) {
    console.warn('[data-resolver] config/tier.json missing, defaulting to fan tier', e);
    return {
      tier: 'fan',
      tier_label: 'SLAYBILL',
      pro_cache_url: null,
      pro_cache_max_age_days: 7,
      show_upgrade_nudges: true,
    };
  }
}

function ageInDays(iso) {
  if (!iso) return Infinity;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return Infinity;
  return (Date.now() - t) / 86_400_000;
}

async function tryProCache(url) {
  if (!url) return null;
  try {
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) return null;
    return await r.json();
  } catch (e) {
    console.info('[data-resolver] Pro cache unreachable:', e.message);
    return null;
  }
}

async function tryLocal() {
  try {
    const r = await fetch('data/shows_live.json', { cache: 'no-store' });
    if (!r.ok) return null;
    return await r.json();
  } catch (e) {
    console.info('[data-resolver] Local shows_live.json unreachable:', e.message);
    return null;
  }
}

function tryCached() {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (e) {
    return null;
  }
}

function persistCache(data) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(data));
    localStorage.setItem(CACHE_TIMESTAMP_KEY, new Date().toISOString());
  } catch (e) {
    /* quota — non-fatal */
  }
}

export async function resolveShowData() {
  const config = await loadConfig();
  const isFan = config.tier === 'fan';
  const proUrl = config.pro_cache_url;
  const maxAge = config.pro_cache_max_age_days || 7;

  // 1. Fan tier with a configured Pro cache: try cache first.
  if (isFan && proUrl) {
    const cacheData = await tryProCache(proUrl);
    if (cacheData) {
      const age = ageInDays(cacheData.generated_at);
      if (age <= maxAge) {
        persistCache(cacheData);
        return { data: cacheData, source: 'pro_cache', age_days: age, config };
      }
      console.info(`[data-resolver] Pro cache stale (${age.toFixed(1)}d > ${maxAge}d) — falling through`);
    }
  }

  // 2. Local shows_live.json (Pro tier always uses this; Fan tier falls here when cache misses).
  const localData = await tryLocal();
  if (localData) {
    persistCache(localData);
    const age = ageInDays(localData.generated_at);
    return {
      data: localData,
      source: isFan ? 'fan_scrape' : 'local',
      age_days: age,
      config,
    };
  }

  // 3. localStorage cached fallback (offline, server down, etc.).
  const cached = tryCached();
  if (cached) {
    const age = ageInDays(cached.generated_at);
    return { data: cached, source: 'cached', age_days: age, config };
  }

  return { data: null, source: 'error', age_days: Infinity, config };
}

/** Format a human-readable badge string for the source + age. */
export function formatTierBadge(source, ageDays) {
  if (source === 'pro_cache') {
    const age = formatAge(ageDays);
    return `Austin Verified · ${age}`;
  }
  if (source === 'fan_scrape') {
    const age = formatAge(ageDays);
    return `Fan scrape · ${age}`;
  }
  if (source === 'local') {
    const age = formatAge(ageDays);
    return `Pro · ${age}`;
  }
  if (source === 'cached') {
    return 'Cached · offline';
  }
  return 'Data unavailable';
}

function formatAge(days) {
  if (!Number.isFinite(days)) return 'unknown';
  if (days < 1) {
    const h = Math.max(1, Math.round(days * 24));
    return `${h}h ago`;
  }
  if (days < 14) return `${Math.round(days)}d ago`;
  return `${Math.round(days / 7)}w ago`;
}

```

### FILE: web/assets/js/upgrade-nudge.js

```javascript
// SLAYBILL — upgrade-nudge.js
// Injects contextual Pro upsell panels into Tier 2 detail pages on Fan tier only.
// Reads /config/tier.json (loaded by data-resolver) and quietly no-ops on Pro.
//
// Used by: web/shows/_template.html
// Pairs with: web/assets/js/data-resolver.js

const NUDGE_CTAS = [
  {
    id: 'editorial',
    headline: 'Pro tracks the story behind this show',
    body: 'Weekly editorial digest with multi-source verification, critic-vs-audience deltas, and producer signal.',
    cta: 'See Pro',
  },
  {
    id: 'grosses',
    headline: 'Pro charts 8 weeks of grosses for this show',
    body: 'Week-over-week capacity, average ticket, and the moment a show pivots.',
    cta: 'See Pro',
  },
  {
    id: 'cast',
    headline: 'Pro tracks rotating leads + standby calls',
    body: 'Know who is on for tonight before you walk to the box office.',
    cta: 'See Pro',
  },
];

const DISMISS_KEY = 'slaybill:nudge:dismissed';
const SESSION_SHOWN_KEY = 'slaybill:nudge:shown-this-session';

function pickNudge(slug) {
  const dismissed = JSON.parse(localStorage.getItem(DISMISS_KEY) || '[]');
  const candidates = NUDGE_CTAS.filter((n) => !dismissed.includes(n.id));
  if (candidates.length === 0) return null;
  // Stable pick per show: hash slug to index.
  let h = 0;
  for (let i = 0; i < slug.length; i++) h = (h * 31 + slug.charCodeAt(i)) >>> 0;
  return candidates[h % candidates.length];
}

function buildNudge(nudge, upgradeUrl) {
  const wrap = document.createElement('aside');
  wrap.className = 'upgrade-nudge';
  wrap.setAttribute('aria-label', 'SLAYBILL Pro upgrade');
  wrap.innerHTML = `
    <button class="upgrade-nudge__dismiss" aria-label="Dismiss">×</button>
    <h3 class="upgrade-nudge__headline">${nudge.headline}</h3>
    <p class="upgrade-nudge__body">${nudge.body}</p>
    <a class="upgrade-nudge__cta" href="${upgradeUrl}" rel="noopener">${nudge.cta} →</a>
  `;
  wrap.querySelector('.upgrade-nudge__dismiss').addEventListener('click', () => {
    const dismissed = JSON.parse(localStorage.getItem(DISMISS_KEY) || '[]');
    if (!dismissed.includes(nudge.id)) dismissed.push(nudge.id);
    localStorage.setItem(DISMISS_KEY, JSON.stringify(dismissed));
    wrap.remove();
  });
  return wrap;
}

function injectStyles() {
  if (document.getElementById('upgrade-nudge-styles')) return;
  const style = document.createElement('style');
  style.id = 'upgrade-nudge-styles';
  style.textContent = `
    .upgrade-nudge {
      position: relative;
      max-width: 1100px;
      margin: 32px auto;
      padding: 20px 24px;
      background: color-mix(in oklch, var(--c1, #888) 12%, transparent);
      border: 1px solid color-mix(in oklch, var(--c1, #888) 35%, transparent);
      border-radius: 14px;
      backdrop-filter: blur(6px);
      -webkit-backdrop-filter: blur(6px);
    }
    .upgrade-nudge__dismiss {
      position: absolute; top: 8px; right: 12px;
      background: none; border: 0;
      color: var(--ink-muted, #888);
      font-size: 20px; line-height: 1; cursor: pointer;
      padding: 4px 8px;
    }
    .upgrade-nudge__dismiss:hover { color: var(--ink, #000); }
    .upgrade-nudge__headline {
      margin: 0 0 8px;
      font-family: Fraunces, Georgia, serif;
      font-size: 18px; font-weight: 500;
      color: var(--ink, #000);
    }
    .upgrade-nudge__body {
      margin: 0 0 12px;
      color: var(--ink-muted, #555);
      font-size: 14px; line-height: 1.5;
    }
    .upgrade-nudge__cta {
      display: inline-block;
      padding: 8px 14px;
      background: var(--c1, #000);
      color: var(--stage, #fff);
      text-decoration: none;
      border-radius: 999px;
      font-size: 13px; font-weight: 500;
      letter-spacing: 0.04em;
      transition: transform .2s ease;
    }
    .upgrade-nudge__cta:hover { transform: translateY(-1px); }
    @media (prefers-reduced-motion: reduce) {
      .upgrade-nudge__cta { transition: none; }
    }
  `;
  document.head.appendChild(style);
}

export async function setupUpgradeNudge(slug, mountSelector = 'main') {
  let cfg;
  try {
    cfg = await fetch('../config/tier.json').then((r) => r.json());
  } catch {
    return; // No config = no nudge.
  }
  if (cfg.tier !== 'fan' || cfg.show_upgrade_nudges === false) return;
  if (sessionStorage.getItem(SESSION_SHOWN_KEY) === slug) return;
  const nudge = pickNudge(slug);
  if (!nudge) return;
  injectStyles();
  const mount = document.querySelector(mountSelector);
  if (!mount) return;
  mount.appendChild(buildNudge(nudge, cfg.pro_upgrade_url || 'https://slaybill.app/pro'));
  sessionStorage.setItem(SESSION_SHOWN_KEY, slug);
}

```

### FILE: web/config/tier.json

```json
{
  "_doc": "SLAYBILL tier config. The front-end reads this at load time and adjusts what shows: data sources, badges, upgrade nudges. To switch a deploy from Fan to Pro, change `tier` and provide pro_cache_url.",
  "tier": "fan",
  "tier_label": "SLAYBILL Fan",
  "pro_cache_url": null,
  "pro_cache_max_age_days": 7,
  "show_upgrade_nudges": true,
  "pro_upgrade_url": "https://slaybill.app/pro",
  "support_email": "hello@slaybill.app"
}

```

### FILE: slaybill-pro/web/config/tier.json

```json
{
  "_doc": "SLAYBILL Pro tier config. Pro tier does not show upgrade nudges (user is already paying); does NOT read from Pro cache (it generates the cache); shows the spend-warning UI for scheduled editorial runs.",
  "tier": "pro",
  "tier_label": "SLAYBILL Pro",
  "pro_cache_url": "https://slaybill-pro-cache.s3.amazonaws.com/shows_live.json",
  "pro_cache_max_age_days": 7,
  "show_upgrade_nudges": false,
  "show_spend_warning": true,
  "pro_owner": "Austin",
  "support_email": "austin@slaybill.app"
}

```

### FILE: builders/build_live_shows.py

```python
"""
SLAYBILL — emit shows_live.json from the curated shows.json source of truth.

v1 strategy: shows.json is authoritative. This builder normalizes it into the
format the front-end expects (split by tier + status bucket, computed rank
fields, safe defaults for missing metrics).

v1.5 will layer DB grosses + news-event overlays on top (date refresh + live
capacity_pct from the latest grosses row).

Run:
    python builders/build_live_shows.py

Output shape:
    {
      "_doc": "...",
      "generated_at": "...",
      "buckets": {
        "coming_soon":   [show, ...],   # previews start within 42 days
        "in_previews":   [show, ...],   # currently previewing
        "live":          [show, ...],   # officially opened
        "closed":        [show, ...]    # archived, shown only on archive page
      },
      "off_broadway":    [show, ...]    # ALL off-Broadway regardless of bucket
    }

Rationale for splitting off-Broadway from the buckets: the UI renders it as a
separate horizontal-scroll row, not inside the bucket stacks. Easier to emit
once here than to filter client-side.
"""

import json
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
SHOWS_JSON = PROJECT_ROOT / "data" / "shows.json"
# Write the generated JSON into web/data/ so the static server can reach it
# via a sibling path (fetch('data/shows_live.json') from web/index.html).
OUT_PATH = PROJECT_ROOT / "web" / "data" / "shows_live.json"

COMING_SOON_WINDOW_DAYS = 42  # 6 weeks


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def derive_status(show: dict, today: date) -> str:
    """If shows.json already has a status, trust it. Otherwise derive from dates."""
    if show.get("status"):
        return show["status"]
    closing = _parse_date(show.get("closing_date"))
    opening = _parse_date(show.get("opening_date"))
    first_preview = _parse_date(show.get("first_preview_date"))

    if closing and closing < today:
        return "closed"
    if opening and opening <= today:
        if not closing or closing >= today:
            return "live"
    if first_preview and first_preview <= today:
        if not opening or today < opening:
            return "in_previews"
    if first_preview and today < first_preview <= today + timedelta(days=COMING_SOON_WINDOW_DAYS):
        return "coming_soon"
    return "announced"


def normalize(show: dict, today: date) -> dict:
    """Flatten into the exact contract the front-end expects. Keeping the
    in-memory JS simple means all fields have the SAME name across every
    show, and always present (null when unknown)."""
    return {
        "slug": show["slug"],
        "title": show["title"],
        "subtitle": show.get("subtitle", ""),
        "tier": show.get("tier", "broadway"),
        "category": show.get("category", "unknown"),
        "status": derive_status(show, today),
        "theatre": show.get("theatre", ""),
        "theatre_capacity": show.get("theatre_capacity"),
        "first_preview_date": show.get("first_preview_date"),
        "opening_date": show.get("opening_date"),
        "closing_date": show.get("closing_date"),
        "synopsis": show.get("synopsis", ""),
        "cast": show.get("cast", []),
        "creatives": show.get("creatives", []),
        "producers": show.get("producers", []),
        "avg_ticket_usd": show.get("avg_ticket_usd"),
        "capacity_pct": show.get("capacity_pct"),
        "weekly_gross_usd": show.get("weekly_gross_usd"),
        "critic_score": show.get("critic_score"),
        "sentiment_score": show.get("sentiment_score"),
        "palette": show.get("palette", ["#333333", "#666666", "#999999", "#cccccc", "#ffffff"]),
        "ticket_links": show.get("ticket_links", {}),
    }


def build() -> dict:
    data = json.loads(SHOWS_JSON.read_text())
    today = date.today()

    buckets: dict[str, list[dict]] = {
        "coming_soon": [],
        "in_previews": [],
        "live": [],
        "closed": [],
    }
    off_broadway: list[dict] = []

    for show in data["shows"]:
        normalized = normalize(show, today)
        if normalized["tier"] == "off_broadway":
            off_broadway.append(normalized)
            continue
        bucket = normalized["status"]
        if bucket == "closed_early" or bucket == "cancelled":
            bucket = "closed"
        if bucket in buckets:
            buckets[bucket].append(normalized)
        # announced shows are omitted from main page; they'd live on an
        # upcoming-season view later.

    # Sort each Broadway bucket by weekly gross desc (nulls last).
    def sort_key(s):
        return (-(s["weekly_gross_usd"] or 0), s["title"].lower())

    for key in buckets:
        buckets[key].sort(key=sort_key)
    off_broadway.sort(key=lambda s: (-(s["weekly_gross_usd"] or 0), s["title"].lower()))

    out = {
        "_doc": (
            "Auto-generated by build_live_shows.py from shows.json. "
            "buckets[*] lists Broadway shows grouped by status; off_broadway "
            "is flat regardless of bucket. Do NOT edit by hand — edit "
            "shows.json and re-run the builder."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "buckets": buckets,
        "off_broadway": off_broadway,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    data = build()
    counts = {k: len(v) for k, v in data["buckets"].items()}
    counts["off_broadway"] = len(data["off_broadway"])
    print(f"Wrote {OUT_PATH.name}")
    for k, v in counts.items():
        print(f"  {k:14} {v}")

```

### FILE: builders/build_show_pages.py

```python
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
        "{{SLUG}}": slug,
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

```

### FILE: builders/build_archive.py

```python
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

```

### FILE: builders/classify_status.py

```python
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

```

### FILE: scrapers/playbill_grosses.py

```python
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
    s = re.sub(r"[^\d\-]", "", s or "")
    try:
        return int(s) if s else None
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
    cur = conn.execute("INSERT INTO shows (title, status) VALUES (?, 'open')", (title,))
    conn.commit()
    return cur.lastrowid


def run() -> None:
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

```

### FILE: scrapers/playbill_news.py

```python
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

```

### FILE: scrapers/broadway_world.py

```python
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

```

### FILE: tools/signal_checker.py

```python
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

```

### FILE: data/schema.sql

```sql
-- SLAYBILL corpus database schema (SQLite)
--
-- shows table holds canonical show records. State is driven by classify_status.py
-- which reads events + grosses and writes shows.status + the date fields.

CREATE TABLE IF NOT EXISTS shows (
    show_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ibdb_id TEXT UNIQUE,
    slug TEXT UNIQUE,
    title TEXT NOT NULL,
    tier TEXT CHECK(tier IN ('broadway', 'off_broadway')) DEFAULT 'broadway',
    category TEXT CHECK(category IN ('musical', 'play', 'unknown')) DEFAULT 'unknown',
    theatre TEXT,
    theatre_capacity INTEGER,
    first_preview_date DATE,
    opening_date DATE,
    closing_date DATE,
    status TEXT CHECK(status IN (
        'announced',
        'coming_soon',
        'in_previews',
        'live',
        'closed',
        'closed_early',
        'cancelled'
    )) DEFAULT 'announced',
    synopsis TEXT,
    cast_json TEXT,           -- JSON array of {name, role}
    creatives_json TEXT,      -- JSON array of {name, role} (composer, book, director, etc.)
    producers_json TEXT,      -- JSON array of strings
    avg_ticket_price_cents INTEGER,
    capacity_pct REAL,        -- denormalized from latest grosses row for card read speed
    weekly_gross_usd INTEGER, -- denormalized from latest grosses row
    critic_score INTEGER,     -- 0-100, NULL when not yet aggregated
    critic_sample_size INTEGER,
    critic_updated_at TIMESTAMP,
    sentiment_score INTEGER,  -- 0-100, NULL when not yet aggregated
    sentiment_sample_size INTEGER,
    sentiment_updated_at TIMESTAMP,
    parent_entity TEXT,
    public_ticker TEXT,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_shows_tier ON shows(tier);
CREATE INDEX IF NOT EXISTS idx_shows_status ON shows(status);
CREATE INDEX IF NOT EXISTS idx_shows_first_preview ON shows(first_preview_date);

-- events = raw signal detections from news scrapers. classify_status.py reads
-- this table, finds event_type='preview_change'/'closing_notice'/etc, and
-- back-propagates to shows.status + the date fields.

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    show_id INTEGER REFERENCES shows(show_id),
    event_type TEXT CHECK(event_type IN (
        'cast_change', 'creative_swap', 'closing_notice', 'extension',
        'preview_change', 'understudy_go_on', 'gross_anomaly', 'producer_change',
        'silent_pull', 'announcement', 'review', 'award_nom', 'other'
    )),
    event_date DATE,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source TEXT,
    source_url TEXT UNIQUE,
    raw_snippet TEXT,
    parsed_fields TEXT,
    severity INTEGER CHECK(severity BETWEEN 1 AND 5),
    reviewed BOOLEAN DEFAULT 0,
    review_status TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_show ON events(show_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);

CREATE TABLE IF NOT EXISTS grosses (
    gross_id INTEGER PRIMARY KEY AUTOINCREMENT,
    show_id INTEGER REFERENCES shows(show_id),
    week_ending DATE,
    gross_usd INTEGER,
    attendance INTEGER,
    capacity_pct REAL,
    average_ticket_usd REAL,
    source_url TEXT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(show_id, week_ending)
);

CREATE INDEX IF NOT EXISTS idx_grosses_show_week ON grosses(show_id, week_ending);

-- ticket_links: one row per vendor per show. classify_status (or a later
-- builder) populates canonical search URLs so Tier 2 can deep-link without a
-- live scrape.

CREATE TABLE IF NOT EXISTS ticket_links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    show_id INTEGER REFERENCES shows(show_id),
    vendor TEXT CHECK(vendor IN ('telecharge', 'todaytix', 'tkts', 'seatgeek', 'broadway_direct', 'official')),
    url TEXT NOT NULL,
    last_verified_at TIMESTAMP,
    UNIQUE(show_id, vendor)
);

CREATE INDEX IF NOT EXISTS idx_ticket_links_show ON ticket_links(show_id);

-- price_points: daily price samples per vendor. Empty in v1; v1.5 adds a
-- scraper that populates this from TodayTix / TKTS daily pulls.

CREATE TABLE IF NOT EXISTS price_points (
    point_id INTEGER PRIMARY KEY AUTOINCREMENT,
    show_id INTEGER REFERENCES shows(show_id),
    sample_date DATE NOT NULL,
    vendor TEXT,
    min_cents INTEGER,
    median_cents INTEGER,
    max_cents INTEGER,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(show_id, sample_date, vendor)
);

CREATE INDEX IF NOT EXISTS idx_price_points_show_date ON price_points(show_id, sample_date);

-- critic_reviews: one row per outlet per show. Empty in v1; v2 aggregates
-- these into shows.critic_score.

CREATE TABLE IF NOT EXISTS critic_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    show_id INTEGER REFERENCES shows(show_id),
    outlet TEXT,
    reviewer TEXT,
    score_normalized INTEGER CHECK(score_normalized BETWEEN 0 AND 100),
    url TEXT,
    pull_quote TEXT,
    published_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_critic_reviews_show ON critic_reviews(show_id);

CREATE TABLE IF NOT EXISTS anomalies (
    anomaly_id INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pattern_type TEXT CHECK(pattern_type IN (
        'clustered_creative_departures',
        'preview_extension_cascade',
        'gross_divergence',
        'understudy_heavy_run',
        'closing_cluster_earnings_window',
        'silent_pull',
        'sudden_creative_lead_change',
        'cross_show_pattern'
    )),
    related_event_ids TEXT,
    related_show_ids TEXT,
    affected_ticker TEXT,
    confidence REAL CHECK(confidence BETWEEN 0 AND 1),
    summary TEXT,
    reviewed_by_editor BOOLEAN DEFAULT 0,
    action_taken TEXT
);

CREATE INDEX IF NOT EXISTS idx_anomalies_ticker ON anomalies(affected_ticker);
CREATE INDEX IF NOT EXISTS idx_anomalies_detected ON anomalies(detected_at);

CREATE TABLE IF NOT EXISTS scrape_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    status TEXT CHECK(status IN ('running', 'success', 'error', 'partial')),
    items_ingested INTEGER DEFAULT 0,
    new_events INTEGER DEFAULT 0,
    error_message TEXT
);

```

### FILE: data/status.json

```json
{
  "last_run_iso": "2026-04-24T05:19:40.386810+00:00",
  "verdict": "preview",
  "label": "In Previews",
  "subline": "Corpus not yet created.",
  "events_24h_total": 0,
  "events_24h_high_severity": 0
}
```

### FILE: Makefile

```makefile
.PHONY: build serve scrape classify all clean help

help:
	@echo "SLAYBILL — make targets"
	@echo "  build      regenerate shows_live.json + show detail pages + archive"
	@echo "  serve      start local dev server on :8000"
	@echo "  scrape     run all scrapers (Playbill grosses + news + BroadwayWorld)"
	@echo "  classify   back-propagate events -> shows.status"
	@echo "  all        scrape + classify + build"
	@echo "  clean      remove generated files"

build:
	uv run --with Pillow python builders/build_live_shows.py
	uv run --with Pillow python builders/build_show_pages.py
	python builders/build_archive.py

serve:
	python -m http.server 8000 --directory web

scrape:
	uv run --with requests --with beautifulsoup4 python scrapers/playbill_grosses.py
	uv run --with requests --with beautifulsoup4 python scrapers/playbill_news.py
	uv run --with requests --with beautifulsoup4 python scrapers/broadway_world.py

classify:
	python builders/classify_status.py

all: scrape classify build

clean:
	rm -f data/shows_live.json
	rm -f web/archive.html
	find web/shows -maxdepth 1 -name '*.html' ! -name '_template.html' -delete

```

### FILE: README.md

```markdown
# SLAYBILL

*Your shows' favorite show guide.*

A standalone Broadway + Off-Broadway tracking app. Three lifecycle buckets on the home page — Coming Soon (previews within 6 weeks), In Previews (performing but not opened), Live on Broadway (officially open) — plus an Off-Broadway row and a Fantasy Broadway draft game.

Static HTML + JSON + Python renderers + SQLite. No framework, no build step beyond the Python builders.

## Quickstart

```bash
# 1. Regenerate shows_live.json + all show detail pages + archive.html.
#    Uses Pillow for poster palette extraction.
uv run --with Pillow python builders/build_live_shows.py
uv run --with Pillow python builders/build_show_pages.py
python builders/build_archive.py

# 2. Serve the app locally.
python -m http.server 8000 --directory web
# open http://localhost:8000/
```

## Data flow

```
shows.json  (curated source of truth — edit by hand for v1)
    │
    ├─▶ build_live_shows.py ─▶ shows_live.json ─▶ web/index.html hydration
    ├─▶ build_show_pages.py ─▶ web/shows/<slug>.html (Tier 2 detail pages)
    └─▶ build_archive.py    ─▶ web/archive.html

corpus.db  (scraper output — v1.5 onwards)
    │
    └─▶ classify_status.py ─▶ shows.status back-propagation
```

## Data model

| Field | Source (v1) | Source (v1.5+) |
|---|---|---|
| Title, theatre, dates, synopsis | `shows.json` (hand-curated) | `scrapers/offbroadway_league.py` authenticated fetch |
| Weekly gross, capacity %, avg ticket | `shows.json` or `grosses` table | `scrapers/playbill_grosses.py` weekly |
| Status (coming_soon / in_previews / live / closed) | `classify_status.py` from dates + `events` | same, refined by news-event signals |
| Cast, creatives, producers | `shows.json` | future scrapers |
| Ticket links | `shows.json` (Telecharge / TodayTix / TKTS search URLs) | daily price snapshots into `price_points` |
| Critic score | — (shows em-dash "coming soon") | `scrapers/critic_aggregator.py` in v2 |
| Audience sentiment | — (shows em-dash "coming soon") | social-listening pipeline in v2 |

## Layout

```
slaybill/
├── web/              ← served by any static file server
│   ├── index.html          main SLAYBILL page (three buckets + OB row)
│   ├── fantasy.html        Fantasy Broadway (draft + score + Tonys countdown)
│   ├── archive.html        closed & cancelled shows (generated)
│   └── shows/
│       ├── _template.html  Tier 2 detail page template
│       └── <slug>.html     generated detail pages
├── data/
│   ├── shows.json          curated source of truth (edit here)
│   ├── shows_live.json     generated for the front-end
│   ├── schema.sql          SQLite schema
│   └── corpus.db           scraper output (gitignored)
├── scrapers/
│   ├── playbill_grosses.py weekly Broadway grosses
│   ├── playbill_news.py    event detection (closings, casting, previews)
│   └── broadway_world.py   supplementary news feed
├── builders/
│   ├── build_live_shows.py emit shows_live.json
│   ├── build_show_pages.py emit web/shows/<slug>.html
│   ├── build_archive.py    emit web/archive.html
│   └── classify_status.py  back-propagate events → shows.status
├── tools/
│   └── signal_checker.py   (misc utilities)
└── README.md
```

## Adding a show

1. Open `data/shows.json`.
2. Append a new entry. Required fields: `slug`, `title`, `tier`, `category`, `theatre`, dates, `status`.
3. Drop a poster image into `web/shows/posters/<slug>.jpg` (optional — palette auto-extracts).
4. Re-run `builders/build_live_shows.py` + `builders/build_show_pages.py`.
5. Hard-refresh the browser.

## Closing a show

Set `"status": "closed"` and populate `closing_date` in `shows.json`, then re-run the builders. The show disappears from the main grid and appears in `archive.html`.

## Roadmap

- **v1** (shipped) — three-bucket layout, off-Broadway row, HADESTOWN card fit fix, Tier 2 detail pages, Fantasy Broadway, archive.
- **v1.5** — real off-Broadway scrapers (offbroadway.com, Off-Broadway League member portal, BroadwayWorld OB), daily ticket price snapshots, automated cron.
- **v2** — critic aggregation (NYT / Variety / THR / Vulture / TimeOut, normalized 0–100) and audience sentiment (Reddit / TikTok / Instagram social listening, likely via a paid aggregator).

```

### FILE: .gitignore

```
# OS
.DS_Store
Thumbs.db

# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.pytest_cache/
.mypy_cache/

# Data (regeneratable, can be large)
data/corpus.db
data/*.db-journal
data/STOP
*.log

# Generated JSON consumed by the front-end (rebuild via Makefile)
web/data/shows_live.json

# Editor
.vscode/
.idea/
*.swp

# Node (in case we add toolchain later)
node_modules/

```
