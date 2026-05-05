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
| Audience sentiment | Show-Score / Broadway Scorecard / Broadway.com cache when available | social-listening pipeline in v2 |

## Layout

```
slaybill/
├── web/              ← served by any static file server
│   ├── index.html          main SLAYBILL page (three buckets + OB row)
│   ├── fantasy.html        Fantasy Broadway (draft + score + Tonys countdown)
│   ├── archive.html        closed & cancelled shows (generated)
│   ├── news.html           news aggregation page
│   ├── gossip.html         gossip/buzz feed page
│   ├── assets/             static assets (CSS, JS, images)
│   ├── config/             client-side config
│   ├── data/               generated JSON (shows_live.json, news_feed.json, etc.)
│   └── shows/
│       ├── _template.html  Tier 2 detail page template
│       ├── posters/        show poster images
│       └── <slug>.html     generated detail pages
├── data/
│   ├── shows.json                     curated source of truth (edit here)
│   ├── marketing_firms_research.json  marketing agency data
│   ├── status.json                    editorial signal verdict
│   ├── schema.sql                     SQLite schema
│   └── corpus.db                      scraper output (gitignored)
├── scrapers/
│   ├── playbill_grosses.py     weekly Broadway grosses
│   ├── playbill_news.py        event detection (closings, casting, previews)
│   ├── broadway_world.py       supplementary news feed
│   ├── news_aggregator.py      unified news feed builder
│   ├── gossip_aggregator.py    social buzz / gossip feed
│   ├── llm_aggregator.py       LLM-powered content aggregation
│   ├── intel_scraper.py        competitive intelligence gathering
│   └── scoring.py              scoring algorithms for shows
├── builders/
│   ├── build_live_shows.py     emit shows_live.json
│   ├── build_show_pages.py     emit web/shows/<slug>.html
│   ├── build_archive.py        emit web/archive.html
│   ├── classify_status.py      back-propagate events → shows.status
│   ├── apply_scores.py         apply critic + sentiment scores to shows
│   └── build_firms.py          marketing firms data builder
├── tools/
│   ├── signal_checker.py       editorial signal detector
│   ├── poster_fetcher.py       automated poster image downloader
│   ├── merge_firm_research.py  merge marketing firm research data
│   └── build_codex_brief.py    generate codebase documentation
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
- **v2** — critic aggregation (NYT / Variety / THR / Vulture / TimeOut, normalized 0–100) and audience sentiment anchored by Show-Score plus Reddit / TikTok / Instagram social listening.
