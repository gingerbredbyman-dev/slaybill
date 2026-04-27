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

-- marketing_credits: which marketing firms hold which shows in which roles.
-- One row per (show, firm, role). is_primary = 1 marks the agency-of-record
-- (gold-sparkles treatment). Curated entries override scraped: confidence 1.0
-- when source = 'curated', lower for press-release / Playbill credit scrape.
-- v1: hand-curated via shows.json.marketing_firms[]; v2 Pro: automated press
-- release ingestion writes here with source != 'curated'.
CREATE TABLE IF NOT EXISTS marketing_credits (
    credit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    show_id INTEGER REFERENCES shows(show_id),
    firm_name TEXT NOT NULL,
    role TEXT CHECK(role IN (
        'lead_agency', 'press', 'digital', 'creative',
        'oo_h', 'social', 'pr', 'media_buy'
    )) NOT NULL,
    is_primary BOOLEAN DEFAULT 0,
    source TEXT CHECK(source IN (
        'curated', 'press_release', 'playbill_credit', 'editorial_verification'
    )) DEFAULT 'curated',
    source_url TEXT,
    start_date DATE,
    end_date DATE,
    confidence REAL DEFAULT 1.0 CHECK(confidence BETWEEN 0 AND 1),
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_marketing_credits_show ON marketing_credits(show_id, end_date);
CREATE INDEX IF NOT EXISTS idx_marketing_credits_firm ON marketing_credits(firm_name);
CREATE INDEX IF NOT EXISTS idx_marketing_credits_primary ON marketing_credits(show_id, is_primary);
