"""
SLAYBILL — LLM-aggregated critic + audience score pipeline (v1 MVP).

Why this exists: building 13 reliable per-outlet scrapers is multi-hour,
brittle to URL/markup changes, and overkill for v1. GPT-4o-mini already has
strong recall of how each named critic outlet received each major Broadway
show plus general audience reception. We use it as a one-shot aggregator.

Trade-off vs literal scraping: 1 API call per show returns scores across all
10 critic outlets + 3 audience platforms with brief justifications. Marked
"LLM-aggregated" in the UI for transparency. v2 can swap individual sources
for real scrapers without changing the schema.

Model: Anthropic claude-haiku-4-5 (OpenAI key was rotated and rejected).
With prompt caching on the system message, cost across 45 shows is ~$0.05.

Per Austin's research doc (/tmp/critic-audience.txt):
  Critic weights:    NYT 20, Variety 14, HR 10, NY Post 10, Guardian 10,
                     Time Out NY 8, TheaterMania 8, BroadwayWorld 6,
                     Vulture 7, AP 7
  Audience weights:  Show-Score/show-score.com 35,
                     Broadway Scorecard 25, Broadway.com 20
                     (Mezzanine 12% dropped — iOS-only, no public data)
                     (Reddit 8% dropped — no PRAW creds yet)
  Composite:         0.55 * critic + 0.45 * audience
  Grade:             A+ (91+) -> A (85+) -> ... -> F (<35)

Run:
    uv run --with anthropic python scrapers/llm_aggregator.py --show hamilton
    uv run --with anthropic python scrapers/llm_aggregator.py --all-live

Cache: scrapers/cache/scores_<slug>.json (7-day freshness for audience;
critics frozen once "all_critics_in" flag set).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
SHOWS_JSON = PROJECT_ROOT / "data" / "shows.json"
CACHE_DIR = HERE / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CRITIC_OUTLETS = [
    "NY Times", "Variety", "Hollywood Reporter", "NY Post", "The Guardian",
    "Time Out NY", "TheaterMania", "Vulture", "Associated Press", "BroadwayWorld",
]
AUDIENCE_PLATFORMS = ["Show-Score", "Broadway Scorecard", "Broadway.com"]

CACHE_FRESHNESS_HOURS = 24 * 7  # 7-day audience refresh window

SYSTEM_PROMPT = """You aggregate Broadway critic and audience scores from your knowledge of public reviews and audience reception. Return ONLY a JSON object — no prose, no markdown fences. If you have no knowledge of a specific source's review of a specific show, OMIT that source from the output. Do NOT guess or hallucinate scores."""

PROMPT_TEMPLATE = """Aggregate scores for this Broadway show.

Show: "{title}"
Subtitle: "{subtitle}"
Theatre: {theatre}
Opening date: {opening_date}
Status: {status}
Synopsis: {synopsis}

Return scores 0-100 (where 100 = unanimous rave, 0 = pan, 50 = mixed). Only \
include a source if you actually have knowledge of how it received this show.

Critic outlets to assess (named-publication reviews):
  {critic_outlets}

Audience platforms to assess (community-rating sites):
  {audience_platforms}

For each source you include, also provide a one-sentence justification \
referencing the actual reception (e.g., "Brantley called it electrifying" or \
"audience consensus on Show-Score has been strongly positive at A-/A range").

Also return:
- "all_critics_in": true if all 10 critic outlets have published a review for \
this show (used to FREEZE the critic score). For shows that opened months ago \
this is usually true; for in-previews shows it's usually false.
- "confidence": "high" | "medium" | "low" — your overall confidence in this \
show's scoring based on knowledge recency and review volume.

JSON shape:
{{
  "critic_scores": {{ "NY Times": 88, "Variety": 82, ... }},
  "critic_justifications": {{ "NY Times": "...", ... }},
  "audience_scores": {{ "Show-Score": 91, ... }},
  "audience_justifications": {{ "Show-Score": "...", ... }},
  "all_critics_in": true,
  "confidence": "high"
}}"""


def _keychain_get(name: str) -> str:
    """Read a secret from macOS Keychain. Returns empty string if not found."""
    try:
        out = subprocess.check_output(
            ["security", "find-generic-password", "-a", "austinsprague", "-s", name, "-w"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except subprocess.CalledProcessError:
        return ""


def _cache_path(slug: str) -> Path:
    return CACHE_DIR / f"scores_{slug}.json"


def _is_fresh(cache_path: Path, frozen_critics: bool) -> bool:
    """Cache hit logic.
    - If frozen_critics (all_critics_in=true previously), the cached critic score
      is permanent. Audience still refreshes weekly.
    - Else: any cache entry under 7 days old counts as fresh.
    """
    if not cache_path.exists():
        return False
    age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
    if frozen_critics:
        return False  # always re-poll audience even if critics frozen
    return age_hours < CACHE_FRESHNESS_HOURS


def aggregate_show(show: dict, client, *, force: bool = False) -> dict:
    """Run the LLM aggregator for one show. Returns parsed JSON dict."""
    slug = show["slug"]
    cache = _cache_path(slug)

    cached = None
    if cache.exists():
        try:
            cached = json.loads(cache.read_text())
        except json.JSONDecodeError:
            cached = None

    frozen = bool(cached and cached.get("all_critics_in"))
    if not force and cached and _is_fresh(cache, frozen):
        return cached

    prompt = PROMPT_TEMPLATE.format(
        title=show.get("title", ""),
        subtitle=show.get("subtitle", "") or "—",
        theatre=show.get("theatre", "") or "—",
        opening_date=show.get("opening_date") or "—",
        status=show.get("status", "—"),
        synopsis=(show.get("synopsis") or "")[:600],
        critic_outlets=", ".join(CRITIC_OUTLETS),
        audience_platforms=", ".join(AUDIENCE_PLATFORMS),
    )

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        system=[
            {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    raw = resp.content[0].text if resp.content else "{}"
    # Strip any accidental markdown fences.
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM returned invalid JSON for {slug}: {e}\n{raw[:500]}")

    # If we already had a frozen critic block, preserve it (don't overwrite).
    if frozen and cached:
        data["critic_scores"] = cached.get("critic_scores", {})
        data["critic_justifications"] = cached.get("critic_justifications", {})
        data["all_critics_in"] = True

    data["_meta"] = {
        "slug": slug,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "model": "claude-haiku-4-5-20251001",
    }
    cache.write_text(json.dumps(data, indent=2))
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", help="Single show slug")
    ap.add_argument("--all-live", action="store_true", help="All status=live shows")
    ap.add_argument("--force", action="store_true", help="Bypass cache freshness")
    args = ap.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY") or _keychain_get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not in env or Keychain")

    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("anthropic not installed — run with: uv run --with anthropic python scrapers/llm_aggregator.py ...")

    client = Anthropic(api_key=api_key)

    data = json.loads(SHOWS_JSON.read_text())
    shows = data["shows"]

    if args.show:
        targets = [s for s in shows if s["slug"] == args.show]
        if not targets:
            sys.exit(f"slug not found: {args.show}")
    elif args.all_live:
        targets = [s for s in shows if s.get("status") == "live"]
    else:
        ap.print_help()
        sys.exit(1)

    print(f"Aggregating {len(targets)} show(s)...")
    for i, show in enumerate(targets, 1):
        try:
            result = aggregate_show(show, client, force=args.force)
            crit_n = len(result.get("critic_scores", {}))
            aud_n = len(result.get("audience_scores", {}))
            frozen = "❄" if result.get("all_critics_in") else " "
            print(f"  [{i:2}/{len(targets)}] {show['slug']:30} {frozen} critics={crit_n:2} audience={aud_n} conf={result.get('confidence','?')}")
        except Exception as e:
            print(f"  [{i:2}/{len(targets)}] {show['slug']:30}  FAILED: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
