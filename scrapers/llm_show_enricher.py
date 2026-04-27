"""
SLAYBILL — Live Broadway show enrichment.

Fills in two specific gaps the audit surfaced:
  1. Cast depth — shows with ≤1 named principal get expanded to 4-6
  2. Socials — shows missing the socials block get IG/TikTok/X/Threads/FB

Uses Claude Haiku (Anthropic SDK) — same one-call pattern as the score
aggregator. Honest model — it omits sources it doesn't know rather than
hallucinating. Output is cached per-show so repeat runs are cheap.

Run:
    uv run --with anthropic python scrapers/llm_show_enricher.py
    uv run --with anthropic python scrapers/llm_show_enricher.py --apply
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
SHOWS_JSON = PROJECT_ROOT / "data" / "shows.json"
CACHE_DIR = HERE / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def keychain_get(name: str) -> str:
    try:
        out = subprocess.check_output(
            ["security", "find-generic-password", "-a", "austinsprague", "-s", name, "-w"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except subprocess.CalledProcessError:
        return ""


SYSTEM = (
    "You are a Broadway data assistant. Return valid JSON only — no prose, "
    "no markdown fences. Only include fields you have confident knowledge of. "
    "OMIT sources rather than guess. Honesty > completeness."
)

PROMPT_TEMPLATE = """For each Broadway show below, return what you know about its current Broadway run.

For EACH show return a JSON object keyed by slug, with these optional fields:
  cast: list of up to 6 {{ name, role }} principals (current cast — leads only)
  socials: dict with optional keys: instagram, tiktok, x, threads, facebook (full URLs to OFFICIAL handles only — never guess a handle that may not exist)

Shows:
{shows_block}

Return shape:
{{
  "<slug>": {{
    "cast": [...],
    "socials": {{ "instagram": "https://...", "tiktok": "https://...", ... }}
  }},
  ...
}}"""


def needs_enrichment(show: dict) -> tuple[bool, bool]:
    """Returns (needs_cast, needs_socials)."""
    needs_cast = len(show.get("cast") or []) <= 1
    needs_socials = not show.get("socials")
    return needs_cast, needs_socials


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="Merge enriched data back into shows.json (additive only).")
    ap.add_argument("--cache-only", action="store_true",
                    help="Use cached results, skip API call.")
    args = ap.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY") or keychain_get("ANTHROPIC_API_KEY")
    if not api_key and not args.cache_only:
        sys.exit("ANTHROPIC_API_KEY not in env or Keychain")

    data = json.loads(SHOWS_JSON.read_text())
    shows = data["shows"]
    live = [s for s in shows if s.get("status") == "live" and s.get("tier") != "off_broadway"]

    # Identify gaps
    targets = []
    for s in live:
        nc, ns = needs_enrichment(s)
        if nc or ns:
            targets.append((s, nc, ns))
    print(f"{len(targets)} live shows need enrichment ({sum(1 for _,nc,_ in targets if nc)} cast, {sum(1 for _,_,ns in targets if ns)} socials)")

    cache_path = CACHE_DIR / "show_enrichment.json"
    enriched = {}
    if cache_path.exists():
        enriched = json.loads(cache_path.read_text())

    if not args.cache_only and targets:
        # Build prompt with all gap-shows
        shows_block = []
        for s, nc, ns in targets:
            line = f"- {s['slug']}: \"{s['title']}\" at {s.get('theatre','?')}"
            wants = []
            if nc: wants.append("cast")
            if ns: wants.append("socials")
            line += f"  [need: {', '.join(wants)}]"
            shows_block.append(line)
        prompt = PROMPT_TEMPLATE.format(shows_block="\n".join(shows_block))

        try:
            from anthropic import Anthropic
        except ImportError:
            sys.exit("anthropic not installed — run with: uv run --with anthropic python scrapers/llm_show_enricher.py ...")
        client = Anthropic(api_key=api_key)
        print(f"Calling Claude Haiku 4.5 with {len(targets)} shows...")
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8000,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        raw = resp.content[0].text.strip() if resp.content else "{}"
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()
        try:
            enriched = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"JSON parse failed: {e}")
            print(raw[:1000])
            sys.exit(1)
        cache_path.write_text(json.dumps(enriched, indent=2, ensure_ascii=False))
        print(f"  cached {len(enriched)} entries to {cache_path.relative_to(PROJECT_ROOT)}")

    # Report what we got
    cast_added = 0
    socials_added = 0
    for s, nc, ns in targets:
        e = enriched.get(s["slug"], {})
        c = e.get("cast") or []
        sc = e.get("socials") or {}
        bits = []
        if nc and c: bits.append(f"cast={len(c)}")
        if ns and sc: bits.append(f"socials={len(sc)}")
        if not bits: bits.append("(model returned nothing)")
        print(f"  {s['slug']:38} {' '.join(bits)}")
        if nc and c: cast_added += 1
        if ns and sc: socials_added += 1
    print(f"\nWill enrich: cast={cast_added}, socials={socials_added}")

    if not args.apply:
        print("\nDry run — pass --apply to merge into shows.json")
        return

    # Apply: additive only — never overwrite existing non-empty fields.
    by_slug = {s["slug"]: s for s in shows}
    n_cast, n_soc = 0, 0
    for slug, e in enriched.items():
        target = by_slug.get(slug)
        if not target:
            continue
        nc, ns = needs_enrichment(target)
        if nc and e.get("cast"):
            target["cast"] = e["cast"]
            n_cast += 1
        if ns and e.get("socials"):
            target["socials"] = e["socials"]
            n_soc += 1
    tmp = SHOWS_JSON.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(SHOWS_JSON)
    print(f"\nApplied: cast={n_cast}, socials={n_soc} → {SHOWS_JSON.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
