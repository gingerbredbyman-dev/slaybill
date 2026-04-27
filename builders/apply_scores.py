"""
SLAYBILL — Apply critic + audience scores to shows.json.

Reads per-show cached LLM aggregator output from scrapers/cache/scores_<slug>.json,
computes weighted composites via the canonical compute_show_score() from
intel_scraper.py, and writes back into data/shows.json under flat per-show fields.

Field contract written per live show:
  critic_score          (int, 0-100, weighted)
  sentiment_score       (int, 0-100, weighted)   [renamed from "audience" for FE compat]
  composite_score       (float, 0-100)
  grade                 (str, "A+" .. "F" | "N/A")
  score_label           (str, "Must See" .. "Skip It")
  critic_sources_used   (list[str])
  audience_sources_used (list[str])
  critic_updated_at     (ISO ts; only updated when all_critics_in flips true once)
  sentiment_updated_at  (ISO ts; updated every run)
  scores_meta           ({"confidence": "high|medium|low", "method": "llm-aggregated", ...})
  flags                 ({"gross_warning": bool, "sentiment_warning": bool})

Flag triggers (per Austin's research doc):
  gross_warning = weekly_gross_usd is not None AND weekly_gross_usd < 499_000
  sentiment_warning = sentiment_score is not None AND sentiment_score < 60

Run:
    uv run --with openai python scrapers/llm_aggregator.py --all-live   # populate cache
    python builders/apply_scores.py --live-only                          # apply to shows.json
    python builders/build_live_shows.py                                  # regen FE feed
    uv run --with Pillow python builders/build_show_pages.py             # regen Tier 2
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
SHOWS_JSON = PROJECT_ROOT / "data" / "shows.json"
CACHE_DIR = PROJECT_ROOT / "scrapers" / "cache"

# Make the scrapers package importable.
sys.path.insert(0, str(PROJECT_ROOT))
from scrapers.scoring import compute_show_score  # noqa: E402

GROSS_FLAG_THRESHOLD = 499_000
SENTIMENT_FLAG_THRESHOLD = 60


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_cache(slug: str) -> dict | None:
    p = CACHE_DIR / f"scores_{slug}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def apply_to_show(show: dict, cache: dict, prev_critic_updated: str | None) -> dict:
    """Returns a dict of field updates to merge into the show."""
    critic_scores = cache.get("critic_scores", {}) or {}
    audience_scores = cache.get("audience_scores", {}) or {}

    result = compute_show_score(
        show_name=show["title"],
        critic_scores=critic_scores,
        audience_scores=audience_scores,
    )

    sentiment_score = result.get("audience_score")
    weekly_gross = show.get("weekly_gross_usd")

    flags = {
        "gross_warning": bool(weekly_gross is not None and weekly_gross < GROSS_FLAG_THRESHOLD),
        "sentiment_warning": bool(sentiment_score is not None and sentiment_score < SENTIMENT_FLAG_THRESHOLD),
    }

    # Critic timestamp: set once when LLM reports all_critics_in=true; preserve afterward.
    all_in = bool(cache.get("all_critics_in"))
    if all_in and not prev_critic_updated:
        critic_updated_at = _now_iso()
    elif all_in and prev_critic_updated:
        critic_updated_at = prev_critic_updated  # frozen
    else:
        critic_updated_at = None  # still gathering

    return {
        "critic_score": int(round(result["critic_score"])) if result["critic_score"] is not None else None,
        "sentiment_score": int(round(sentiment_score)) if sentiment_score is not None else None,
        "composite_score": result["composite_score"],
        "grade": result["grade"],
        "score_label": result["label"],
        "critic_sources_used": result["critic_sources_used"],
        "audience_sources_used": result["audience_sources_used"],
        "critic_updated_at": critic_updated_at,
        "sentiment_updated_at": _now_iso(),
        "scores_meta": {
            "confidence": cache.get("confidence", "unknown"),
            "method": "llm-aggregated",
            "model": (cache.get("_meta") or {}).get("model"),
        },
        "flags": flags,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live-only", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    data = json.loads(SHOWS_JSON.read_text())
    shows = data["shows"]
    targets = [s for s in shows if s.get("status") == "live"] if args.live_only else shows

    applied = 0
    skipped = 0
    for show in targets:
        cache = _load_cache(show["slug"])
        if not cache:
            skipped += 1
            if args.verbose:
                print(f"  skip (no cache): {show['slug']}")
            continue
        prev = show.get("critic_updated_at")
        update = apply_to_show(show, cache, prev)
        show.update(update)
        applied += 1
        if args.verbose:
            grade = update.get("grade", "?")
            comp = update.get("composite_score")
            flag_marks = []
            if update["flags"]["gross_warning"]: flag_marks.append("$")
            if update["flags"]["sentiment_warning"]: flag_marks.append("⚠")
            flag_str = "".join(flag_marks) or " "
            print(f"  {show['slug']:30} grade={grade:3}  composite={comp}  {flag_str}")

    # Atomic write.
    tmp = SHOWS_JSON.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(SHOWS_JSON)
    print(f"\napplied={applied} skipped={skipped} of {len(targets)} target(s)")


if __name__ == "__main__":
    main()
