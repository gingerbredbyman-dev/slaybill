"""
Merge marketing_firms_research.json into shows.json.

Strategy: research data is authoritative — REPLACE existing marketing_firms[]
on each show wherever the staging file has entries for that slug. Strips the
`_stub: true` flags from earlier hand-curated guesses. Preserves
`_confidence` and `_source` fields on each entry for transparency.

Run:
    uv run python tools/merge_firm_research.py
    uv run python tools/merge_firm_research.py --dry-run   # show diff only
"""

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
SHOWS_JSON = PROJECT_ROOT / "data" / "shows.json"
RESEARCH_JSON = PROJECT_ROOT / "data" / "marketing_firms_research.json"

VALID_ROLES = {
    "lead_agency", "press", "digital", "creative",
    "oo_h", "social", "pr", "media_buy",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    shows = json.loads(SHOWS_JSON.read_text())
    research = json.loads(RESEARCH_JSON.read_text())
    research_shows = research.get("shows", {})

    replaced = 0
    cleared_stubs = 0
    aka_aor_count = 0
    untouched = 0

    for show in shows["shows"]:
        slug = show["slug"]
        had_stub = any(
            entry.get("_stub")
            for entry in (show.get("marketing_firms") or [])
        )

        if slug not in research_shows:
            untouched += 1
            continue

        new_firms = research_shows[slug].get("marketing_firms", [])
        # Validate roles + dedupe identical (firm, role) pairs.
        cleaned = []
        seen = set()
        for entry in new_firms:
            firm = (entry.get("firm") or "").strip()
            role = entry.get("role")
            if not firm or role not in VALID_ROLES:
                continue
            key = (firm.lower(), role)
            if key in seen:
                continue
            seen.add(key)
            cleaned.append({
                "firm": firm,
                "role": role,
                "is_primary": bool(entry.get("is_primary")),
                **{k: v for k, v in entry.items() if k.startswith("_")},
            })

        if cleaned:
            show["marketing_firms"] = cleaned
            replaced += 1
            if any(f["is_primary"] and "AKA" in f["firm"].upper() for f in cleaned):
                aka_aor_count += 1
        else:
            # Research returned empty → drop the field entirely if it was a stub
            if had_stub:
                show.pop("marketing_firms", None)
            else:
                show["marketing_firms"] = []

        if had_stub:
            cleared_stubs += 1

    if args.dry_run:
        print(f"[dry-run] would replace marketing_firms on {replaced} shows")
        print(f"[dry-run] would clear stub flags on {cleared_stubs} shows")
        print(f"[dry-run] AKA-AOR shows after merge: {aka_aor_count}")
        print(f"[dry-run] shows untouched: {untouched}")
        return

    SHOWS_JSON.write_text(json.dumps(shows, indent=2))
    print(f"Merged. Replaced marketing_firms on {replaced} shows.")
    print(f"Cleared stub flags on {cleared_stubs} shows.")
    print(f"AKA-AOR shows after merge: {aka_aor_count}")
    print(f"Shows untouched (no research data): {untouched}")


if __name__ == "__main__":
    main()
