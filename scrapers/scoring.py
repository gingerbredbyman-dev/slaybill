"""
SLAYBILL — Pure scoring engine, extracted from intel_scraper.py.

Stands alone (no feedparser/requests/openai imports) so apply_scores.py can
import it without dragging the whole scraper toolchain into the runtime.

Source weights and methodology come straight from Austin's research doc
(/tmp/critic-audience.txt) and broadwayscorecard.com — no edits.

Note: Mezzanine and Reddit are present in CRITIC/AUDIENCE_SOURCES so the
upstream LLM aggregator can OPT-IN if data ever materializes. They simply
contribute zero weight when their scores are absent — the function
renormalizes by the weight of present sources.
"""
from __future__ import annotations

CRITIC_SOURCES = [
    ("NY Times",          0.20),
    ("Variety",           0.14),
    ("Hollywood Reporter", 0.10),
    ("NY Post",           0.10),
    ("The Guardian",      0.10),
    ("Time Out NY",       0.08),
    ("TheaterMania",      0.08),
    ("BroadwayWorld",     0.06),
    ("Vulture",           0.07),
    ("Associated Press",  0.07),
]

AUDIENCE_SOURCES = [
    ("Show-Score",         0.35),
    ("Broadway Scorecard", 0.25),
    ("Broadway.com",       0.20),
    ("Mezzanine",          0.12),  # iOS-only, no public data — usually absent
    ("Reddit Sentiment",   0.08),  # needs PRAW creds — usually absent
]


def compute_show_score(
    show_name: str,
    critic_scores: dict,
    audience_scores: dict,
    critic_weight: float = 0.55,
    audience_weight: float = 0.45,
) -> dict:
    """0-100 composite, Metacritic-style. Returns dict with composite_score,
    critic_score, audience_score, grade, label, and lists of sources used.
    Sources missing from the input simply drop out of the weighted average
    (their weight is excluded from the denominator)."""

    total_crit_weight = 0.0
    weighted_crit_sum = 0.0
    for src, weight in CRITIC_SOURCES:
        if src in critic_scores:
            weighted_crit_sum += critic_scores[src] * weight
            total_crit_weight += weight
    critic_score = (weighted_crit_sum / total_crit_weight) if total_crit_weight else None

    total_aud_weight = 0.0
    weighted_aud_sum = 0.0
    for src, weight in AUDIENCE_SOURCES:
        if src in audience_scores:
            weighted_aud_sum += audience_scores[src] * weight
            total_aud_weight += weight
    audience_score = (weighted_aud_sum / total_aud_weight) if total_aud_weight else None

    if critic_score is not None and audience_score is not None:
        composite = round(critic_score * critic_weight + audience_score * audience_weight, 1)
    elif critic_score is not None:
        composite = round(critic_score, 1)
    elif audience_score is not None:
        composite = round(audience_score, 1)
    else:
        composite = None

    def grade(s):
        if s is None: return "N/A", "Not enough data"
        if s >= 91:   return "A+", "Must See"
        if s >= 85:   return "A",  "Excellent"
        if s >= 80:   return "A-", "Great"
        if s >= 75:   return "B+", "Very Good"
        if s >= 70:   return "B",  "Good"
        if s >= 65:   return "B-", "Above Average"
        if s >= 55:   return "C+", "Mixed-Positive"
        if s >= 45:   return "C",  "Mixed"
        if s >= 35:   return "D",  "Weak"
        return "F", "Skip It"

    comp_grade, comp_label = grade(composite)

    return {
        "show_name": show_name,
        "composite_score": composite,
        "critic_score": round(critic_score, 1) if critic_score is not None else None,
        "audience_score": round(audience_score, 1) if audience_score is not None else None,
        "grade": comp_grade,
        "label": comp_label,
        "critic_sources_used": list(critic_scores.keys()),
        "audience_sources_used": list(audience_scores.keys()),
    }
